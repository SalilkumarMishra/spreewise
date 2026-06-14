"""
Accounts Views
==============
Endpoints:
  POST /api/auth/register/      - Create account + return JWT tokens
  POST /api/auth/logout/        - Invalidate (client-side) + acknowledge
  GET  /api/auth/me/            - Return current user profile
  GET  /api/auth/dashboard/     - Personalized dashboard summary
  GET  /api/users/search/       - Search users by username/email/name
"""
from django.contrib.auth import get_user_model
from django.db.models import Q, Sum
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.serializers import RegisterSerializer, UserMeSerializer, UserSearchSerializer
from groups.models import Group, GroupMembership

User = get_user_model()


def _get_tokens_for_user(user):
    """Generate JWT access + refresh tokens for a given user."""
    refresh = RefreshToken.for_user(user)
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }


class RegisterView(APIView):
    """
    POST /api/auth/register/
    Creates a new user account and returns JWT tokens immediately so
    the user is logged in right after registration.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        tokens = _get_tokens_for_user(user)
        return Response(
            {
                'user': UserMeSerializer(user).data,
                **tokens,
            },
            status=status.HTTP_201_CREATED,
        )


class LogoutView(APIView):
    """
    POST /api/auth/logout/
    Accepts the refresh token and blacklists it (if blacklisting is enabled).
    With BLACKLIST_AFTER_ROTATION=False, this is a client-side logout acknowledgment.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get('refresh')
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()
        except Exception:
            pass  # Tolerate already-expired or invalid tokens
        return Response({'detail': 'Successfully logged out.'}, status=status.HTTP_200_OK)


class MeView(APIView):
    """
    GET /api/auth/me/
    Returns the currently authenticated user's profile.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserMeSerializer(request.user)
        return Response(serializer.data)


class UserSearchView(APIView):
    """
    GET /api/users/search/?q=<query>
    Searches users by username, email, first_name, or last_name.
    Returns up to 10 results. Excludes the requesting user from results.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        query = request.query_params.get('q', '').strip()
        if len(query) < 2:
            return Response([], status=status.HTTP_200_OK)

        users = User.objects.filter(
            Q(username__icontains=query) |
            Q(email__icontains=query) |
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query)
        ).exclude(id=request.user.id).order_by('username')[:10]

        return Response(UserSearchSerializer(users, many=True).data)


class DashboardView(APIView):
    """
    GET /api/auth/dashboard/
    Returns a personalized dashboard summary for the logged-in user:
    - my_groups: list of groups the user is an active member of
    - net_balance: aggregated you_owe / you_are_owed across all groups
    - recent_expenses: last 5 expenses across all the user's groups
    - recent_settlements: last 5 settlements across all the user's groups
    - pending_import_reviews: count of import jobs awaiting review
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        # ── My active group memberships ──────────────────────────────────
        memberships = GroupMembership.objects.filter(
            user=user, is_active=True
        ).select_related('group').order_by('group__name')

        my_groups = []
        for m in memberships:
            my_groups.append({
                'id': m.group.id,
                'name': m.group.name,
                'currency': m.group.currency,
                'role': m.role,
                'is_archived': m.group.is_archived,
            })

        # ── IDs of groups the user belongs to ────────────────────────────
        group_ids = [m['id'] for m in my_groups]

        # ── Net balance across all groups ─────────────────────────────────────
        you_owe = 0.0
        you_are_owed = 0.0
        try:
            from balance_engine.services import balance_service
            for group_dict in my_groups:
                try:
                    grp = Group.objects.get(id=group_dict['id'])
                    balances = balance_service.calculate_group_balances(grp)
                    for b in balances:
                        if b.get('user_id') == user.id:
                            net = float(b.get('balance', 0) or 0)
                            if net < 0:
                                you_owe += abs(net)
                            else:
                                you_are_owed += net
                except Exception:
                    pass
        except Exception:
            pass

        # ── Recent Expenses ───────────────────────────────────────────────
        from expenses.models import Expense
        recent_expenses = []
        try:
            expenses_qs = Expense.objects.filter(
                group_id__in=group_ids, is_archived=False
            ).select_related('paid_by', 'group').order_by('-expense_date')[:5]
            for e in expenses_qs:
                recent_expenses.append({
                    'id': e.id,
                    'title': e.title,
                    'amount': str(e.amount),
                    'currency': e.currency,
                    'paid_by': e.paid_by.username,
                    'group': e.group.name,
                    'expense_date': str(e.expense_date),
                })
        except Exception:
            pass

        # ── Recent Settlements ────────────────────────────────────────────
        from settlements.models import Settlement
        recent_settlements = []
        try:
            settlements_qs = Settlement.objects.filter(
                group_id__in=group_ids, is_archived=False
            ).select_related('payer', 'receiver', 'group').order_by('-payment_date')[:5]
            for s in settlements_qs:
                recent_settlements.append({
                    'id': s.id,
                    'amount': str(s.amount),
                    'currency': s.currency,
                    'payer': s.payer.username,
                    'receiver': s.receiver.username,
                    'group': s.group.name,
                    'payment_date': str(s.payment_date),
                })
        except Exception:
            pass

        # ── Pending Import Reviews ─────────────────────────────────────────
        from imports.models import ImportJob
        pending_reviews = ImportJob.objects.filter(
            uploaded_by=user, status='review_required'
        ).count()

        return Response({
            'my_groups': my_groups,
            'group_count': len(my_groups),
            'net_balance': {
                'you_owe': round(you_owe, 2),
                'you_are_owed': round(you_are_owed, 2),
                'net': round(you_are_owed - you_owe, 2),
            },
            'recent_expenses': recent_expenses,
            'recent_settlements': recent_settlements,
            'pending_import_reviews': pending_reviews,
        })
