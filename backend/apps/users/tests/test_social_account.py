"""Tests for SocialAccount model."""

import pytest
from django.db import IntegrityError

from apps.users.factories import UserFactory
from apps.users.models import SocialAccount


@pytest.mark.django_db
class TestSocialAccountModel:
    """Test suite for the SocialAccount model."""

    def test_create_social_account_with_valid_data(self):
        """SocialAccount created successfully with valid data."""
        user = UserFactory()
        account = SocialAccount.objects.create(
            user=user,
            provider=SocialAccount.Provider.GOOGLE,
            uid="google-sub-12345",
            extra_data={"email": "user@gmail.com", "name": "Test User"},
        )
        assert account.pk is not None
        assert account.user == user
        assert account.provider == SocialAccount.Provider.GOOGLE
        assert account.uid == "google-sub-12345"

    def test_social_account_str_representation(self):
        """__str__ returns readable provider + user info."""
        user = UserFactory(email="test@example.com")
        account = SocialAccount.objects.create(
            user=user,
            provider=SocialAccount.Provider.GOOGLE,
            uid="google-sub-12345",
        )
        assert "google" in str(account).lower()
        assert "test@example.com" in str(account)

    def test_uid_unique_per_provider(self):
        """Two accounts cannot share the same uid for the same provider."""
        user1 = UserFactory()
        user2 = UserFactory()
        SocialAccount.objects.create(
            user=user1,
            provider=SocialAccount.Provider.GOOGLE,
            uid="same-uid",
        )
        with pytest.raises(IntegrityError):
            SocialAccount.objects.create(
                user=user2,
                provider=SocialAccount.Provider.GOOGLE,
                uid="same-uid",
            )

    def test_cascade_delete_on_user_delete(self):
        """SocialAccount is deleted when User is deleted."""
        user = UserFactory()
        SocialAccount.objects.create(
            user=user,
            provider=SocialAccount.Provider.GOOGLE,
            uid="google-sub-delete-test",
        )
        user_id = user.pk
        user.delete()
        assert not SocialAccount.objects.filter(user_id=user_id).exists()

    def test_extra_data_defaults_to_empty_dict(self):
        """extra_data defaults to empty dict when not provided."""
        user = UserFactory()
        account = SocialAccount.objects.create(
            user=user,
            provider=SocialAccount.Provider.GOOGLE,
            uid="google-sub-extra-default",
        )
        assert account.extra_data == {}

    def test_user_can_have_multiple_providers(self):
        """One user can link multiple social providers (future-proofing)."""
        user = UserFactory()
        SocialAccount.objects.create(
            user=user,
            provider=SocialAccount.Provider.GOOGLE,
            uid="google-uid-001",
        )
        # A second provider for the same user must not raise
        account2 = SocialAccount.objects.create(
            user=user,
            provider="github",
            uid="github-uid-001",
        )
        assert SocialAccount.objects.filter(user=user).count() == 2
        assert account2.pk is not None

    def test_timestamps_auto_populated(self):
        """created_at and updated_at are set automatically."""
        user = UserFactory()
        account = SocialAccount.objects.create(
            user=user,
            provider=SocialAccount.Provider.GOOGLE,
            uid="google-sub-timestamps",
        )
        assert account.created_at is not None
        assert account.updated_at is not None

    def test_user_social_accounts_reverse_relation(self):
        """User.social_accounts reverse relation returns linked accounts."""
        user = UserFactory()
        SocialAccount.objects.create(
            user=user,
            provider=SocialAccount.Provider.GOOGLE,
            uid="google-sub-reverse",
        )
        assert user.social_accounts.count() == 1
        assert user.social_accounts.first().uid == "google-sub-reverse"
