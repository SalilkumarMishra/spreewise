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
)
from groups.services import membership_service

User = get_user_model()

class GroupViewSet(viewsets.ModelViewSet):
    """
    ViewSet for viewing, creating, updating, and soft-deleting groups.
    Only authenticated users are allowed access.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # By default, exclude archived groups unless 'include_archived' is passed as true.
        queryset = Group.objects.all()
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
        # Soft delete the group
        instance = self.get_object()
        instance.delete()
        return Response(
            {"detail": f"Group '{instance.name}' has been archived."},
            status=status.HTTP_200_OK
        )

    @action(detail=True, methods=["get", "post"], url_path="members", url_name="members")
    def members(self, request, pk=None):
        """
        POST: Add a member to a group (via user_id and joined_at)
        GET: List all memberships of a group (supports ?active=true filter)
        """
        group = self.get_object()

        if request.method == "POST":
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
            
            # Support ?active=true or ?active=false filter
            active_param = request.query_params.get("active")
            if active_param is not None:
                is_active = active_param.lower() == "true"
                memberships = memberships.filter(is_active=is_active)
            
            serializer = GroupMembershipSerializer(memberships, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)


class GroupMembershipLeaveView(APIView):
    """
    Endpoint for marking a group membership as inactive (leave group).
    POST /api/groups/{id}/members/{membership_id}/leave/
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, group_id, membership_id):
        group = get_object_or_404(Group, id=group_id)
        membership = get_object_or_404(GroupMembership, id=membership_id, group=group)

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
