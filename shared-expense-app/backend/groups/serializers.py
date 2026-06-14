from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from groups.models import Group, GroupMembership

User = get_user_model()


class UserInlineSerializer(serializers.ModelSerializer):
    """Minimal user info embedded inside membership responses."""
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'full_name', 'first_name', 'last_name']
        read_only_fields = fields

    def get_full_name(self, obj):
        return obj.get_full_name() or obj.username


class GroupMembershipSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(source="user.id", read_only=True)
    username = serializers.CharField(source="user.username", read_only=True)
    full_name = serializers.SerializerMethodField()
    email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = GroupMembership
        fields = [
            "id", "user_id", "username", "full_name", "email",
            "joined_at", "left_at", "is_active", "role",
            "joined_via_invite", "invite_code_used",
        ]

    def get_full_name(self, obj):
        return obj.user.get_full_name() or obj.user.username


class GroupSerializer(serializers.ModelSerializer):
    created_by_username = serializers.CharField(source="created_by.username", read_only=True)
    current_user_role = serializers.SerializerMethodField()

    class Meta:
        model = Group
        fields = [
            "id",
            "name",
            "description",
            "currency",
            "is_archived",
            "invite_code",
            "created_by",
            "created_by_username",
            "current_user_role",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "is_archived", "invite_code", "created_by", "created_at", "updated_at"]

    def get_current_user_role(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.get_user_role(request.user)
        return None


class GroupDetailSerializer(serializers.ModelSerializer):
    created_by_username = serializers.CharField(source="created_by.username", read_only=True)
    members = GroupMembershipSerializer(source="memberships", many=True, read_only=True)
    active_member_count = serializers.SerializerMethodField()
    total_member_count = serializers.SerializerMethodField()
    current_user_role = serializers.SerializerMethodField()

    class Meta:
        model = Group
        fields = [
            "id",
            "name",
            "description",
            "currency",
            "is_archived",
            "invite_code",
            "created_by",
            "created_by_username",
            "current_user_role",
            "created_at",
            "updated_at",
            "active_member_count",
            "total_member_count",
            "members",
        ]
        read_only_fields = ["id", "is_archived", "invite_code", "created_by", "created_at", "updated_at"]

    def get_active_member_count(self, obj):
        return obj.memberships.filter(is_active=True).count()

    def get_total_member_count(self, obj):
        return obj.memberships.count()

    def get_current_user_role(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.get_user_role(request.user)
        return None


class GroupMemberCreateSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    joined_at = serializers.DateField()

    def validate_user_id(self, value):
        if not User.objects.filter(id=value).exists():
            raise serializers.ValidationError("User with this ID does not exist.")
        return value


class GroupLeaveSerializer(serializers.Serializer):
    left_at = serializers.DateField()


class JoinGroupSerializer(serializers.Serializer):
    invite_code = serializers.CharField(max_length=20)

    def validate_invite_code(self, value):
        if not Group.objects.filter(invite_code=value.upper(), is_archived=False).exists():
            raise serializers.ValidationError("Invalid or expired invite code.")
        return value.upper()
