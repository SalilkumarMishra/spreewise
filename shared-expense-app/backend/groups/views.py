"""
Groups Views
============
GroupViewSet — CRUD + invite-code join + member management
  - get_queryset() is now membership-scoped: users only see their own groups
  - Role-based permission checks on destructive / admin operations
  - JoinGroupView: POST /api/groups/join/
  - GroupMembershipLeaveView: POST /api/groups/{id}/members/{mid}/leave/
"""
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.core.exceptions import ValidationError as DjangoValidationError
from django.contrib.auth import get_user_model

from groups.models import Group, GroupMembership
from groups.serializers import (
    GroupSerializer,
    GroupDetailSerializer,
    GroupMembershipSerializer,
    GroupMemberCreateSerializer,
    GroupLeaveSerializer,
    JoinGroupSerializer,
)
from groups.services import membership_service

User = get_user_model()


# ── Permission helpers ─────────────────────────────────────────────────────

def _get_user_membership(group, user):
    """Returns the active GroupMembership for (group, user) or None."""
    return GroupMembership.objects.filter(group=group, user=user, is_active=True).first()


def _require_role(group, user, allowed_roles, action_name="perform this action"):
    """
    Raises PermissionError if the user does not have one of the allowed roles
    in the given group.
    """
    membership = _get_user_membership(group, user)
    if not membership or membership.role not in allowed_roles:
        from rest_framework.exceptions import PermissionDenied
        raise PermissionDenied(
            f"You must be a {' or '.join(allowed_roles)} to {action_name}."
        )
    return membership


# ── ViewSet ────────────────────────────────────────────────────────────────

class GroupViewSet(viewsets.ModelViewSet):
    """
    ViewSet for viewing, creating, updating, and soft-deleting groups.
    Queryset is scoped to groups where the authenticated user is an active member.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """
        Return only groups where the current user has an active membership.
        Optionally include archived groups with ?include_archived=true.
        """
        user = self.request.user
        # Get IDs of groups the user actively belongs to
        member_group_ids = GroupMembership.objects.filter(
            user=user, is_active=True
        ).values_list('group_id', flat=True)

        queryset = Group.objects.filter(id__in=member_group_ids)

        include_archived = self.request.query_params.get("include_archived", "false").lower() == "true"
        if not include_archived:
            queryset = queryset.filter(is_archived=False)
        return queryset

    def get_serializer_class(self):
        if self.action == "retrieve":
            return GroupDetailSerializer
        return GroupSerializer

    def perform_create(self, serializer):
        # Automatically set creator to the current user
        group = serializer.save(created_by=self.request.user)
        # Automatically add the creator as an owner member joining today
        membership_service.add_member(
            group=group,
            user=self.request.user,
            joined_at=timezone.now().date(),
            role="owner"
        )

    def destroy(self, request, *args, **kwargs):
        """Soft delete — only owner can archive a group."""
        instance = self.get_object()
        _require_role(instance, request.user, ["owner"], "archive this group")
        instance.delete()
        return Response(
            {"detail": f"Group '{instance.name}' has been archived."},
            status=status.HTTP_200_OK
        )

    @action(detail=True, methods=["get", "post"], url_path="members", url_name="members")
    def members(self, request, pk=None):
        """
        GET: List all memberships of a group (supports ?active=true filter)
        POST: Add a member to a group (owner or admin only)
        """
        group = self.get_object()

        if request.method == "POST":
            # Only owner or admin can add members
            _require_role(group, request.user, ["owner", "admin"], "add members")

            serializer = GroupMemberCreateSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            user_id = serializer.validated_data["user_id"]
            joined_at = serializer.validated_data["joined_at"]
            user = get_object_or_404(User, id=user_id)

            try:
                membership = membership_service.add_member(
                    group=group,
                    user=user,
                    joined_at=joined_at,
                    role="member"
                )
            except DjangoValidationError as e:
                return Response(
                    {"detail": e.messages if hasattr(e, "messages") else str(e)},
                    status=status.HTTP_400_BAD_REQUEST
                )

            return Response(
                GroupMembershipSerializer(membership).data,
                status=status.HTTP_201_CREATED
            )

        elif request.method == "GET":
            memberships = group.memberships.all()

            active_param = request.query_params.get("active")
            if active_param is not None:
                is_active = active_param.lower() == "true"
                memberships = memberships.filter(is_active=is_active)

            serializer = GroupMembershipSerializer(memberships, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["delete"], url_path=r"members/(?P<membership_id>\d+)/remove",
            url_name="members-remove")
    def remove_member(self, request, pk=None, membership_id=None):
        """
        DELETE /api/groups/{id}/members/{membership_id}/remove/
        Owners and admins can remove members (admins cannot remove other admins/owners).
        """
        group = self.get_object()
        _require_role(group, request.user, ["owner", "admin"], "remove members")

        membership = get_object_or_404(GroupMembership, id=membership_id, group=group)

        # Admins cannot remove owners or other admins
        requester_membership = _get_user_membership(group, request.user)
        if requester_membership.role == "admin" and membership.role in ["owner", "admin"]:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Admins cannot remove owners or other admins.")

        # Prevent removing the sole owner
        if membership.role == "owner":
            owner_count = group.memberships.filter(role="owner", is_active=True).count()
            if owner_count <= 1:
                return Response(
                    {"detail": "Cannot remove the sole owner of a group."},
                    status=status.HTTP_400_BAD_REQUEST
                )

        try:
            membership_service.leave_membership(membership, timezone.now().date())
        except DjangoValidationError as e:
            return Response(
                {"detail": e.messages if hasattr(e, "messages") else str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response({"detail": "Member removed successfully."}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path=r"members/(?P<membership_id>\d+)/role",
            url_name="members-role")
    def update_member_role(self, request, pk=None, membership_id=None):
        """
        POST /api/groups/{id}/members/{membership_id}/role/
        Body: { "role": "admin" | "member" }
        Only owners can manage admin assignments.
        """
        group = self.get_object()
        _require_role(group, request.user, ["owner"], "manage admin roles")

        membership = get_object_or_404(GroupMembership, id=membership_id, group=group)
        new_role = request.data.get("role")
        if new_role not in ["admin", "member"]:
            return Response(
                {"detail": "Role must be 'admin' or 'member'."},
                status=status.HTTP_400_BAD_REQUEST
            )
        membership.role = new_role
        membership.save(update_fields=["role"])
        return Response(GroupMembershipSerializer(membership).data, status=status.HTTP_200_OK)


class GroupMembershipLeaveView(APIView):
    """
    POST /api/groups/{group_id}/members/{membership_id}/leave/
    Marks a group membership as inactive (user leaves the group).
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, group_id, membership_id):
        group = get_object_or_404(Group, id=group_id)

        # Users can only leave their own membership (or owners can remove others)
        membership = get_object_or_404(GroupMembership, id=membership_id, group=group)
        if membership.user != request.user:
            _require_role(group, request.user, ["owner", "admin"], "remove other members")

        serializer = GroupLeaveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        left_at = serializer.validated_data["left_at"]

        try:
            membership_service.leave_membership(membership, left_at)
        except DjangoValidationError as e:
            return Response(
                {"detail": e.messages if hasattr(e, "messages") else str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response(
            GroupMembershipSerializer(membership).data,
            status=status.HTTP_200_OK
        )


class JoinGroupByInviteCodeView(APIView):
    """
    POST /api/groups/join/
    Body: { "invite_code": "SPW-AB12CD34" }

    Adds the authenticated user as a member of the matching group.
    Records the audit trail (joined_via_invite, invite_code_used).
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = JoinGroupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        invite_code = serializer.validated_data["invite_code"]

        group = get_object_or_404(Group, invite_code=invite_code, is_archived=False)

        # Check if already a member
        existing = GroupMembership.objects.filter(
            group=group, user=request.user, is_active=True
        ).first()
        if existing:
            return Response(
                {"detail": "You are already a member of this group.", "group_id": group.id},
                status=status.HTTP_200_OK
            )

        try:
            membership = membership_service.add_member(
                group=group,
                user=request.user,
                joined_at=timezone.now().date(),
                role="member",
                joined_via_invite=True,
                invite_code_used=invite_code,
            )
        except DjangoValidationError as e:
            return Response(
                {"detail": e.messages if hasattr(e, "messages") else str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response(
            {
                "detail": f"Successfully joined '{group.name}'.",
                "group_id": group.id,
                "membership": GroupMembershipSerializer(membership).data,
            },
            status=status.HTTP_201_CREATED
        )
