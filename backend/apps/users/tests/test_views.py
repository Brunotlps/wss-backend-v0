"""Tests for User API views."""

import pytest
from rest_framework import status

from apps.users.factories import InstructorFactory, UserFactory


@pytest.mark.django_db
class TestUserRegistrationView:
    """Tests for POST /api/auth/register/."""

    URL = "/api/auth/register/"

    def _payload(self, **overrides):
        data = {
            "email": "register@test.com",
            "username": "registeruser",
            "password": "StrongPass123!",
            "password_confirm": "StrongPass123!",
            "first_name": "Test",
            "last_name": "User",
        }
        data.update(overrides)
        return data

    def test_register_returns_201(self, api_client):
        """Successful registration returns 201 with user data."""
        response = api_client.post(self.URL, self._payload())
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["email"] == "register@test.com"

    def test_register_does_not_expose_password(self, api_client):
        """Response does not contain password field."""
        response = api_client.post(self.URL, self._payload())
        assert "password" not in response.data

    def test_register_creates_user_in_db(self, api_client):
        """User is persisted in the database after registration."""
        from apps.users.models import User

        api_client.post(self.URL, self._payload())
        assert User.objects.filter(email="register@test.com").exists()

    def test_register_duplicate_email_returns_400(self, api_client):
        """Duplicate email returns 400."""
        UserFactory(email="dup@test.com")
        response = api_client.post(self.URL, self._payload(email="dup@test.com"))
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_register_password_mismatch_returns_400(self, api_client):
        """Password mismatch returns 400."""
        payload = self._payload(password_confirm="WrongPass!")
        response = api_client.post(self.URL, payload)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_register_missing_email_returns_400(self, api_client):
        """Missing email field returns 400."""
        payload = self._payload()
        del payload["email"]
        response = api_client.post(self.URL, payload)
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestTokenView:
    """Tests for JWT login/refresh/blacklist."""

    LOGIN_URL = "/api/auth/token/"
    REFRESH_URL = "/api/auth/token/refresh/"
    BLACKLIST_URL = "/api/auth/token/blacklist/"

    def test_login_valid_credentials_returns_tokens(self, api_client):
        """Valid credentials return access + refresh tokens."""
        user = UserFactory()
        response = api_client.post(
            self.LOGIN_URL,
            {"email": user.email, "password": "testpass123!"},
        )
        assert response.status_code == status.HTTP_200_OK
        assert "access" in response.data
        assert "refresh" in response.data

    def test_login_invalid_password_returns_401(self, api_client):
        """Wrong password returns 401."""
        user = UserFactory()
        response = api_client.post(
            self.LOGIN_URL,
            {"email": user.email, "password": "wrongpass"},
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_login_nonexistent_user_returns_401(self, api_client):
        """Non-existent email returns 401."""
        response = api_client.post(
            self.LOGIN_URL,
            {"email": "ghost@test.com", "password": "pass"},
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_refresh_token_returns_new_access(self, api_client):
        """Valid refresh token returns new access token."""
        user = UserFactory()
        login_response = api_client.post(
            self.LOGIN_URL,
            {"email": user.email, "password": "testpass123!"},
        )
        refresh = login_response.data["refresh"]
        response = api_client.post(self.REFRESH_URL, {"refresh": refresh})
        assert response.status_code == status.HTTP_200_OK
        assert "access" in response.data

    def test_blacklist_logs_out(self, api_client):
        """Blacklisting refresh token returns 200."""
        user = UserFactory()
        login_response = api_client.post(
            self.LOGIN_URL,
            {"email": user.email, "password": "testpass123!"},
        )
        refresh = login_response.data["refresh"]
        response = api_client.post(self.BLACKLIST_URL, {"refresh": refresh})
        assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestCurrentUserView:
    """Tests for GET/PATCH /api/users/me/."""

    URL = "/api/users/me/"

    def test_get_me_authenticated_returns_200(self, auth_client):
        """Authenticated user gets their profile."""
        response = auth_client.get(self.URL)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["email"] == auth_client.user.email

    def test_get_me_unauthenticated_returns_401(self, api_client):
        """Unauthenticated request returns 401."""
        response = api_client.get(self.URL)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_patch_me_updates_name(self, auth_client):
        """PATCH updates first_name successfully."""
        response = auth_client.patch(self.URL, {"first_name": "Updated"})
        assert response.status_code == status.HTTP_200_OK
        assert response.data["first_name"] == "Updated"

    def test_patch_me_unauthenticated_returns_401(self, api_client):
        """Unauthenticated PATCH returns 401."""
        response = api_client.patch(self.URL, {"first_name": "X"})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_response_includes_nested_profile(self, auth_client):
        """Response includes nested profile object."""
        response = auth_client.get(self.URL)
        assert "profile" in response.data

    def test_patch_me_invalid_data_returns_400(self, auth_client):
        """PATCH with invalid data (demoting instructor) returns 400."""
        auth_client.user.is_instructor = True
        auth_client.user.save()
        response = auth_client.patch(self.URL, {"is_instructor": False})
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestUserViewSet:
    """Tests for /api/users/ CRUD."""

    LIST_URL = "/api/users/"

    def test_list_users_is_public(self, api_client):
        """Unauthenticated users can list users (IsOwnerOrReadOnly allows reads)."""
        UserFactory.create_batch(3)
        response = api_client.get(self.LIST_URL)
        assert response.status_code == status.HTTP_200_OK

    def test_retrieve_user_is_public(self, api_client):
        """Any user can retrieve a user profile."""
        user = UserFactory()
        response = api_client.get(f"{self.LIST_URL}{user.pk}/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["email"] == user.email

    def test_update_own_user_returns_200(self, auth_client):
        """User can update their own record."""
        url = f"{self.LIST_URL}{auth_client.user.pk}/"
        response = auth_client.patch(url, {"first_name": "Changed"})
        assert response.status_code == status.HTTP_200_OK

    def test_update_other_user_returns_403(self, auth_client):
        """User cannot update another user's record."""
        other = UserFactory()
        response = auth_client.patch(
            f"{self.LIST_URL}{other.pk}/", {"first_name": "Hacked"}
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_delete_by_non_staff_returns_403(self, auth_client):
        """Non-staff users cannot delete records."""
        other = UserFactory()
        response = auth_client.delete(f"{self.LIST_URL}{other.pk}/")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_delete_by_staff_returns_204(self, staff_client):
        """Staff users can delete records."""
        user = UserFactory()
        response = staff_client.delete(f"{self.LIST_URL}{user.pk}/")
        assert response.status_code == status.HTTP_204_NO_CONTENT
