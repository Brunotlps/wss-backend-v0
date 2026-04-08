"""Tests for User and Profile models."""

import pytest

from apps.users.factories import InstructorFactory, UserFactory
from apps.users.models import Profile, User


@pytest.mark.django_db
class TestUserModel:
    """Test suite for the User model."""

    def test_create_user_with_valid_data(self):
        """User created successfully with valid data."""
        user = UserFactory(
            email="john@test.com",
            first_name="John",
            last_name="Doe",
        )
        assert user.pk is not None
        assert user.email == "john@test.com"
        assert user.is_active is True
        assert user.is_instructor is False

    def test_user_str_returns_email(self):
        """__str__ returns email address."""
        user = UserFactory(email="jane@test.com")
        assert str(user) == "jane@test.com"

    def test_user_get_full_name(self):
        """get_full_name() returns first + last name."""
        user = UserFactory(first_name="John", last_name="Doe")
        assert user.get_full_name() == "John Doe"

    def test_user_get_full_name_falls_back_to_username(self):
        """get_full_name() falls back to username when names are empty."""
        user = UserFactory(first_name="", last_name="", username="johndoe")
        assert user.get_full_name() == "johndoe"

    def test_user_password_is_hashed(self):
        """Password is stored hashed, never plain text."""
        user = UserFactory(password="mysecretpass!")
        assert user.password != "mysecretpass!"
        assert user.check_password("mysecretpass!")

    def test_email_is_unique(self):
        """Two users cannot share the same email."""
        from django.db import IntegrityError

        UserFactory(email="unique@test.com")
        with pytest.raises(IntegrityError):
            UserFactory(email="unique@test.com")

    def test_instructor_flag(self):
        """InstructorFactory creates user with is_instructor=True."""
        instructor = InstructorFactory()
        assert instructor.is_instructor is True

    def test_profile_auto_created_on_user_save(self):
        """Profile is automatically created via signal when User is saved."""
        user = UserFactory()
        assert hasattr(user, "profile")
        assert isinstance(user.profile, Profile)

    def test_user_email_is_username_field(self):
        """Email is used as the USERNAME_FIELD (login identifier)."""
        assert User.USERNAME_FIELD == "email"


@pytest.mark.django_db
class TestProfileModel:
    """Test suite for the Profile model."""

    def test_profile_str_representation(self):
        """__str__ returns 'Profile of <full_name>'."""
        user = UserFactory(first_name="Ana", last_name="Lima")
        profile = user.profile
        assert "Ana Lima" in str(profile)

    def test_profile_created_with_empty_bio_by_default(self):
        """Profile bio is empty string by default."""
        user = UserFactory()
        assert user.profile.bio == ""

    def test_profile_linked_to_user(self):
        """Profile.user points back to the correct User."""
        user = UserFactory()
        assert user.profile.user == user
