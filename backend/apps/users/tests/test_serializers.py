"""Tests for User serializers."""

import pytest

from apps.users.factories import InstructorFactory, UserFactory
from apps.users.serializers import (
    UserRegistrationSerializer,
    UserUpdateSerializer,
)


@pytest.mark.django_db
class TestUserRegistrationSerializer:
    """Tests for UserRegistrationSerializer validation logic."""

    def _valid_payload(self, **overrides):
        data = {
            "email": "new@test.com",
            "username": "newuser",
            "password": "StrongPass123!",
            "password_confirm": "StrongPass123!",
            "first_name": "New",
            "last_name": "User",
        }
        data.update(overrides)
        return data

    def test_valid_data_is_valid(self):
        """Serializer is valid with correct data."""
        serializer = UserRegistrationSerializer(data=self._valid_payload())
        assert serializer.is_valid(), serializer.errors

    def test_password_mismatch_is_invalid(self):
        """Mismatched passwords raise validation error."""
        payload = self._valid_payload(password_confirm="WrongPass!")
        serializer = UserRegistrationSerializer(data=payload)
        assert not serializer.is_valid()
        assert "non_field_errors" in serializer.errors

    def test_weak_password_is_invalid(self):
        """Password '12345678' is rejected by Django validators."""
        payload = self._valid_payload(
            password="12345678", password_confirm="12345678"
        )
        serializer = UserRegistrationSerializer(data=payload)
        assert not serializer.is_valid()
        assert "password" in serializer.errors

    def test_duplicate_email_is_invalid(self):
        """Email already in use raises validation error."""
        UserFactory(email="taken@test.com")
        payload = self._valid_payload(email="taken@test.com")
        serializer = UserRegistrationSerializer(data=payload)
        assert not serializer.is_valid()

    def test_password_not_in_output(self):
        """Password field is write_only — not present in serializer data."""
        serializer = UserRegistrationSerializer(data=self._valid_payload())
        assert serializer.is_valid()
        user = serializer.save()
        # Confirmed via field definition (write_only=True)
        assert "password" not in serializer.data

    def test_create_user_password_is_hashed(self):
        """save() creates user with hashed password."""
        serializer = UserRegistrationSerializer(data=self._valid_payload())
        assert serializer.is_valid()
        user = serializer.save()
        assert user.check_password("StrongPass123!")

    def test_email_field_required(self):
        """Email is required."""
        payload = self._valid_payload()
        del payload["email"]
        serializer = UserRegistrationSerializer(data=payload)
        assert not serializer.is_valid()
        assert "email" in serializer.errors


@pytest.mark.django_db
class TestUserUpdateSerializer:
    """Tests for UserUpdateSerializer."""

    def test_can_update_name(self):
        """Updating first_name and last_name is allowed."""
        user = UserFactory(first_name="Old", last_name="Name")
        serializer = UserUpdateSerializer(
            user,
            data={"first_name": "New", "last_name": "Name"},
            partial=True,
        )
        assert serializer.is_valid(), serializer.errors
        updated = serializer.save()
        assert updated.first_name == "New"

    def test_cannot_demote_instructor(self):
        """Cannot set is_instructor=False once True."""
        instructor = InstructorFactory()
        serializer = UserUpdateSerializer(
            instructor,
            data={"is_instructor": False},
            partial=True,
        )
        assert not serializer.is_valid()
        assert "is_instructor" in serializer.errors
