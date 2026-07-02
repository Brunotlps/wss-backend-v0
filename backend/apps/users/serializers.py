"""
Serializers for User authentication and profile management.

This module contains serializers for:
- User registration and authentication
- Profile management
- User data serialization for API responses

All serializers include proper validation and follow DRF best practices.
"""

from django.contrib.auth.password_validation import validate_password

from rest_framework import serializers

from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import Profile, User


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """JWT login serializer that treats the email case-insensitively.

    User emails are stored lowercase (see ``User.save``), so the login email
    is normalized here to keep authentication working regardless of casing.
    """

    def validate(self, attrs: dict) -> dict:
        """Lowercase the email before delegating to the default validation."""
        attrs[self.username_field] = attrs.get(self.username_field, "").lower()
        return super().validate(attrs)


class UserRegistrationSerializer(serializers.ModelSerializer):
    """
    Serializer for user registration.

    Handles new user creation with password validation and automatic
    profile creation via signals.
    """

    password = serializers.CharField(
        write_only=True,
        validators=[validate_password],
        help_text="Password must meet Django's validation requirements",
    )

    password_confirm = serializers.CharField(
        write_only=True, help_text="Must match password field"
    )

    class Meta:
        model = User
        fields = [
            "email",
            "username",
            "password",
            "password_confirm",
            "first_name",
            "last_name",
            "phone",
        ]
        extra_kwargs = {
            "email": {"required": True},
            "username": {"required": True},
        }

    def validate_email(self, value: str) -> str:
        """Normalize email to lowercase and enforce case-insensitive uniqueness.

        DRF's auto-generated UniqueValidator already rejects an exact-case
        duplicate; this adds the case-insensitive layer (``email__iexact``) so
        ``User@x`` cannot register when ``user@x`` exists.
        """
        value = value.lower()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("A user with that email already exists.")
        return value

    def validate(self, data: dict) -> dict:
        """Ensure the password and its confirmation match."""
        if data["password"] != data["password_confirm"]:
            raise serializers.ValidationError("Password does not match.")
        return data

    def create(self, validated_data: dict) -> User:
        """Create the user with a hashed password (drops password_confirm)."""
        validated_data.pop("password_confirm")
        password = validated_data.pop("password")

        user = User(**validated_data)
        user.set_password(password)  # Hash password
        user.save()

        return user


class ProfileSerializer(serializers.ModelSerializer):
    """Serializer for user profile information"""

    class Meta:
        model = Profile
        fields = [
            "bio",
            "avatar",
            "birth_date",
            "website",
            "linkedin",
            "instagram",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]


class UserDetailSerializer(serializers.ModelSerializer):
    """
    Detailed user serializer for authenticated requests.

    Includes nested profile information and computed fields.
    """

    profile = ProfileSerializer(read_only=True)
    full_name = serializers.CharField(source="get_full_name", read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "username",
            "first_name",
            "last_name",
            "phone",
            "is_instructor",
            "full_name",
            "profile",
            "date_joined",
            "last_login",
        ]
        read_only_fields = [
            "id",
            "date_joined",
            "last_login",
            "created_at",
            "updated_at",
        ]


class UserUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating user informations.

    ``is_instructor`` is intentionally excluded: instructor status is an
    administrative action and must not be self-assignable via the API
    (privilege escalation — see security.md, Prevent Mass Assignment).
    """

    class Meta:
        model = User
        fields = ["first_name", "last_name", "phone"]


class UserListSerializer(serializers.ModelSerializer):
    """Minimal user serializer for list views."""

    full_name = serializers.CharField(source="get_full_name", read_only=True)

    class Meta:
        model = User
        fields = ["id", "email", "username", "full_name", "is_instructor"]
