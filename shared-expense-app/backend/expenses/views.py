from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError as DjangoValidationError

from expenses.models import Expense
from expenses.serializers import (
    ExpenseSerializer,
    ExpenseDetailSerializer,
    ExpenseCreateSerializer,
)
from expenses.services import expense_service
from groups.models import Group

User = get_user_model()


class ExpenseViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Expense CRUD.

    GET    /api/expenses/          -> list (non-archived)
    POST   /api/expenses/          -> create
    GET    /api/expenses/{id}/     -> retrieve (detail with participants/splits/snapshots)
    PUT    /api/expenses/{id}/     -> update
    DELETE /api/expenses/{id}/     -> soft delete (is_archived = True)
    """
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = Expense.objects.select_related(
            "group", "paid_by", "created_by"
        ).prefetch_related("participants__user", "splits__user", "snapshots")
        include_archived = self.request.query_params.get("include_archived", "false").lower() == "true"
        if not include_archived:
            qs = qs.filter(is_archived=False)

        # Optional filter by group
        group_id = self.request.query_params.get("group_id")
        if group_id:
            qs = qs.filter(group_id=group_id)

        # Optional filter by status
        filter_status = self.request.query_params.get("status")
        if filter_status:
            qs = qs.filter(status=filter_status)

        # Optional filter by category
        category = self.request.query_params.get("category")
        if category:
            qs = qs.filter(expense_category=category)

        return qs

    def get_serializer_class(self):
        if self.action == "retrieve":
            return ExpenseDetailSerializer
        if self.action in ("create", "update", "partial_update"):
            return ExpenseCreateSerializer
        return ExpenseSerializer

    def create(self, request, *args, **kwargs):
        serializer = ExpenseCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        group = get_object_or_404(Group, id=data["group_id"])
        paid_by = get_object_or_404(User, id=data["paid_by_id"])
        participant_users = list(User.objects.filter(id__in=data["participant_ids"]))

        try:
            expense = expense_service.create_expense(
                group=group,
                title=data["title"],
                amount=data["amount"],
                currency=data["currency"],
                expense_date=data["expense_date"],
                paid_by=paid_by,
                split_type=data["split_type"],
                creator=request.user,
                participant_users=participant_users,
                splits_data=data.get("splits", []),
                description=data.get("description", ""),
                notes=data.get("notes", ""),
                original_amount=data.get("original_amount"),
                original_currency=data.get("original_currency"),
                status=data.get("status", "active"),
                expense_category=data.get("expense_category", "general"),
                source=data.get("source", "manual"),
            )
        except DjangoValidationError as e:
            return Response(
                {"detail": e.messages if hasattr(e, "messages") else str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response(
            ExpenseDetailSerializer(expense).data,
            status=status.HTTP_201_CREATED
        )

    def update(self, request, *args, **kwargs):
        expense = self.get_object()
        serializer = ExpenseCreateSerializer(data=request.data, partial=kwargs.get("partial", False))
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        paid_by = get_object_or_404(User, id=data["paid_by_id"]) if "paid_by_id" in data else None
        participant_users = (
            list(User.objects.filter(id__in=data["participant_ids"]))
            if "participant_ids" in data else None
        )

        try:
            expense = expense_service.update_expense(
                expense=expense,
                title=data.get("title"),
                amount=data.get("amount"),
                currency=data.get("currency"),
                expense_date=data.get("expense_date"),
                paid_by=paid_by,
                split_type=data.get("split_type"),
                participant_users=participant_users,
                splits_data=data.get("splits"),
                description=data.get("description"),
                notes=data.get("notes"),
                original_amount=data.get("original_amount"),
                original_currency=data.get("original_currency"),
                status=data.get("status"),
                expense_category=data.get("expense_category"),
                source=data.get("source"),
            )
        except DjangoValidationError as e:
            return Response(
                {"detail": e.messages if hasattr(e, "messages") else str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response(ExpenseDetailSerializer(expense).data, status=status.HTTP_200_OK)

    def destroy(self, request, *args, **kwargs):
        expense = self.get_object()
        expense.delete()  # Triggers soft delete
        return Response(
            {"detail": f"Expense '{expense.title}' has been archived."},
            status=status.HTTP_200_OK
        )
