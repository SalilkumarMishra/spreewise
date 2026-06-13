from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from groups.models import Group, GroupMembership

User = get_user_model()

class GroupMembershipSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(source="user.id", read_only=True)
    username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = GroupMembership
        fields = ["id", "user_id", "username", "joined_at", "left_at", "is_active", "role"]


class GroupSerializer(serializers.ModelSerializer):
    created_by_username = serializers.CharField(source="created_by.username", read_only=True)

    class Meta:
        model = Group
        fields = [
            "id",
            "name",
            "description",
            "currency",
            "is_archived",
            "created_by",
            "created_by_username",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "is_archived", "created_by", "created_at", "updated_at"]


class GroupDetailSerializer(serializers.ModelSerializer):
    created_by_username = serializers.CharField(source="created_by.username", read_only=True)
    members = GroupMembershipSerializer(source="memberships", many=True, read_only=True)
    active_member_count = serializers.SerializerMethodField()
    total_member_count = serializers.SerializerMethodField()

    class Meta:
        model = Group
        fields = [
            "id",
            "name",
            "description",
            "currency",
            "is_archived",
            "created_by",
            "created_by_username",
            "created_at",
            "updated_at",
            "active_member_count",
            "total_member_count",
            "members",
        ]
        read_only_fields = ["id", "is_archived", "created_by", "created_at", "updated_at"]

    def get_active_member_count(self, obj):
        return obj.memberships.filter(is_active=True).count()

    def get_total_member_count(self, obj):
        return obj.memberships.count()


class GroupMemberCreateSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    joined_at = serializers.DateField()

    def validate_user_id(self, value):
        if not User.objects.filter(id=value).exists():
            raise serializers.ValidationError("User with this ID does not exist.")
        return value


class GroupLeaveSerializer(serializers.Serializer):
    left_at = serializers.DateField()
