from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError as DjangoValidationError

from settlements.models import Settlement
from settlements.serializers import (
    SettlementSerializer,
    SettlementDetailSerializer,
    SettlementCreateSerializer,
)
from settlements.services import settlement_service
from groups.models import Group

User = get_user_model()


class SettlementViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        from groups.models import GroupMembership
        user = self.request.user

        # Scope to groups the user is actively a member of
        member_group_ids = GroupMembership.objects.filter(
            user=user, is_active=True
        ).values_list('group_id', flat=True)

        qs = Settlement.objects.select_related(
            "group", "payer", "receiver", "created_by"
        ).prefetch_related("snapshots")
        qs = qs.filter(group_id__in=member_group_ids)

        include_archived = self.request.query_params.get("include_archived", "false").lower() == "true"
        if not include_archived:
            qs = qs.filter(is_archived=False)

        # Filters
        group_id = self.request.query_params.get("group_id")
        if group_id:
            qs = qs.filter(group_id=group_id)

        filter_status = self.request.query_params.get("status")
        if filter_status:
            qs = qs.filter(status=filter_status)
            
        source = self.request.query_params.get("source")
        if source:
            qs = qs.filter(source=source)

        return qs


    def get_serializer_class(self):
        if self.action == "retrieve":
            return SettlementDetailSerializer
        if self.action in ("create", "update", "partial_update"):
            return SettlementCreateSerializer
        return SettlementSerializer

    def create(self, request, *args, **kwargs):
        serializer = SettlementCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        group = get_object_or_404(Group, id=data["group_id"])
        payer = get_object_or_404(User, id=data["payer_id"])
        receiver = get_object_or_404(User, id=data["receiver_id"])

        try:
            settlement = settlement_service.create_settlement(
                group=group,
                payer=payer,
                receiver=receiver,
                amount=data["amount"],
                currency=data["currency"],
                payment_date=data["payment_date"],
                creator=request.user,
                original_amount=data.get("original_amount"),
                original_currency=data.get("original_currency"),
                notes=data.get("notes", ""),
                settlement_category=data.get("settlement_category", "direct_payment"),
                source=data.get("source", "manual"),
                status=data.get("status", "active"),
            )
        except DjangoValidationError as e:
            return Response(
                {"detail": e.messages if hasattr(e, "messages") else str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response(
            SettlementDetailSerializer(settlement).data,
            status=status.HTTP_201_CREATED
        )

    def update(self, request, *args, **kwargs):
        settlement = self.get_object()
        serializer = SettlementCreateSerializer(data=request.data, partial=kwargs.get("partial", False))
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        payer = get_object_or_404(User, id=data["payer_id"]) if "payer_id" in data else None
        receiver = get_object_or_404(User, id=data["receiver_id"]) if "receiver_id" in data else None

        try:
            settlement = settlement_service.update_settlement(
                settlement=settlement,
                amount=data.get("amount"),
                currency=data.get("currency"),
                payment_date=data.get("payment_date"),
                payer=payer,
                receiver=receiver,
                original_amount=data.get("original_amount"),
                original_currency=data.get("original_currency"),
                notes=data.get("notes"),
                settlement_category=data.get("settlement_category"),
                source=data.get("source"),
                status=data.get("status"),
            )
        except DjangoValidationError as e:
            return Response(
                {"detail": e.messages if hasattr(e, "messages") else str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response(SettlementDetailSerializer(settlement).data, status=status.HTTP_200_OK)

    def destroy(self, request, *args, **kwargs):
        settlement = self.get_object()
        settlement.delete()  # Triggers soft delete
        return Response(
            {"detail": f"Settlement '{settlement.reference_id}' has been archived."},
            status=status.HTTP_200_OK
        )
