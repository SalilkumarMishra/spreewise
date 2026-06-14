"""
Accounts Serializers
====================
Serializers for user registration, profile retrieval, and user search.
"""
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

User = get_user_model()


class RegisterSerializer(serializers.Serializer):
    """Validates and creates a new Django user account."""
    full_name = serializers.CharField(max_length=255)
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True)

    def validate_username(self, value):
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("A user with this username already exists.")
        return value.lower()

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("A user with this email address already exists.")
        return value.lower()

    def validate(self, data):
        if data['password'] != data['confirm_password']:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})
        # Run Django's built-in password validators
        validate_password(data['password'])
        return data

    def create(self, validated_data):
        full_name = validated_data['full_name'].strip()
        # Split full_name into first/last name parts
        parts = full_name.split(' ', 1)
        first_name = parts[0]
        last_name = parts[1] if len(parts) > 1 else ''

        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password'],
            first_name=first_name,
            last_name=last_name,
        )
        return user


class UserMeSerializer(serializers.ModelSerializer):
    """Returns the authenticated user's full profile."""
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'full_name', 'date_joined']
        read_only_fields = fields

    def get_full_name(self, obj):
        return obj.get_full_name() or obj.username


class UserSearchSerializer(serializers.ModelSerializer):
    """Minimal user representation for search results and member dropdowns."""
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'full_name', 'first_name', 'last_name']
        read_only_fields = fields

    def get_full_name(self, obj):
        return obj.get_full_name() or obj.username
