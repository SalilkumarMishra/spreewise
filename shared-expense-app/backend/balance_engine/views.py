from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model

from groups.models import Group
from balance_engine.services import (
    balance_service,
    ledger_service,
    simplification_service,
    explanation_service
)

User = get_user_model()

class BalanceViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def list(self, request, group_id=None):
        """
        GET /api/balances/groups/{group_id}/
        Returns group balance summary.
        """
        group = get_object_or_404(Group, id=group_id)
        balances = balance_service.calculate_group_balances(group)
        return Response(balances, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'])
    def simplified(self, request, group_id=None):
        """
        GET /api/balances/groups/{group_id}/simplified/
        Returns minimal payback instructions.
        """
        group = get_object_or_404(Group, id=group_id)
        payments = simplification_service.simplify_debts(group)
        return Response(payments, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path=r'users/(?P<user_id>\d+)')
    def user_explanation(self, request, group_id=None, user_id=None):
        """
        GET /api/balances/groups/{group_id}/users/{user_id}/
        Returns detailed explanation for a user's balance.
        """
        group = get_object_or_404(Group, id=group_id)
        user = get_object_or_404(User, id=user_id)
        explanation = explanation_service.explain_user_balance(group, user)
        return Response(explanation, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'])
    def ledger(self, request, group_id=None):
        """
        GET /api/balances/groups/{group_id}/ledger/
        Returns chronologically sorted ledger events.
        """
        group = get_object_or_404(Group, id=group_id)
        ledger = ledger_service.get_group_ledger(group)
        return Response(ledger, status=status.HTTP_200_OK)
