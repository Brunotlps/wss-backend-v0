"""Tests for Google OAuth views."""

import pytest
from unittest.mock import MagicMock, patch

from django.urls import reverse

from rest_framework.test import APIClient

from apps.users.factories import UserFactory


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def google_login_url():
    return reverse("google-login")


@pytest.fixture
def google_callback_url():
    return reverse("google-callback")


# ---------------------------------------------------------------------------
# GoogleLoginView
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestGoogleLoginView:
    """Test GET /api/auth/google/."""

    def test_redirects_to_google(self, client, google_login_url):
        """GET must redirect to accounts.google.com."""
        response = client.get(google_login_url)
        assert response.status_code == 302
        assert "accounts.google.com" in response["Location"]

    def test_redirect_contains_response_type_code(self, client, google_login_url):
        """Redirect URL must include response_type=code."""
        response = client.get(google_login_url)
        assert "response_type=code" in response["Location"]

    def test_redirect_contains_state(self, client, google_login_url):
        """Redirect URL must include a state parameter."""
        response = client.get(google_login_url)
        assert "state=" in response["Location"]

    def test_no_auth_required(self, client, google_login_url):
        """Endpoint must be public — no credentials needed."""
        response = client.get(google_login_url)
        assert response.status_code != 401
        assert response.status_code != 403


# ---------------------------------------------------------------------------
# GoogleCallbackView
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestGoogleCallbackView:
    """Test GET /api/auth/google/callback/."""

    def test_missing_code_redirects_to_error(self, client, google_callback_url):
        """Callback without code must redirect to frontend error page."""
        response = client.get(google_callback_url, {"state": "some-state"})
        assert response.status_code == 302
        assert "error" in response["Location"]

    def test_missing_state_redirects_to_error(self, client, google_callback_url):
        """Callback without state must redirect to frontend error page."""
        response = client.get(google_callback_url, {"code": "some-code"})
        assert response.status_code == 302
        assert "error" in response["Location"]

    @patch("apps.users.views.GoogleOAuthService")
    def test_invalid_state_redirects_to_error(
        self, mock_service_cls, client, google_callback_url
    ):
        """Callback with state mismatch must redirect to frontend error page."""
        mock_service = MagicMock()
        mock_service.handle_callback.side_effect = ValueError("Invalid state")
        mock_service_cls.return_value = mock_service

        response = client.get(
            google_callback_url, {"code": "some-code", "state": "bad-state"}
        )
        assert response.status_code == 302
        assert "error" in response["Location"]

    @patch("apps.users.views.GoogleOAuthService")
    def test_successful_callback_redirects_with_tokens_in_fragment(
        self, mock_service_cls, client, google_callback_url
    ):
        """Successful callback must redirect to frontend with JWT tokens in fragment."""
        user = UserFactory()
        mock_service = MagicMock()
        mock_service.handle_callback.return_value = user
        mock_service_cls.return_value = mock_service

        response = client.get(
            google_callback_url, {"code": "valid-code", "state": "valid-state"}
        )
        assert response.status_code == 302
        location = response["Location"]
        assert "#" in location
        assert "access=" in location
        assert "refresh=" in location

    @patch("apps.users.views.GoogleOAuthService")
    def test_successful_callback_does_not_expose_tokens_in_path(
        self, mock_service_cls, client, google_callback_url
    ):
        """Tokens must be in the fragment (#), not in the query string (?)."""
        user = UserFactory()
        mock_service = MagicMock()
        mock_service.handle_callback.return_value = user
        mock_service_cls.return_value = mock_service

        response = client.get(
            google_callback_url, {"code": "valid-code", "state": "valid-state"}
        )
        location = response["Location"]
        fragment_start = location.index("#") if "#" in location else len(location)
        query_part = location[:fragment_start]
        assert "access=" not in query_part
        assert "refresh=" not in query_part

    @patch("apps.users.views.GoogleOAuthService")
    def test_successful_callback_redirects_to_frontend_url(
        self, mock_service_cls, client, google_callback_url
    ):
        """Redirect location must start with FRONTEND_URL."""
        from django.conf import settings

        user = UserFactory()
        mock_service = MagicMock()
        mock_service.handle_callback.return_value = user
        mock_service_cls.return_value = mock_service

        response = client.get(
            google_callback_url, {"code": "valid-code", "state": "valid-state"}
        )
        assert response["Location"].startswith(settings.FRONTEND_URL)
