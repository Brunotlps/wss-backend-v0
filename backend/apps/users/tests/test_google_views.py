"""Tests for Google OAuth views."""

from unittest.mock import MagicMock, patch

from django.test import override_settings
from django.urls import reverse

from rest_framework.test import APIClient

import pytest

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
    def test_successful_callback_redirects_with_code_in_fragment(
        self, mock_service_cls, client, google_callback_url
    ):
        """Successful callback redirects with a single-use code in the fragment,
        never the JWT tokens themselves (#43)."""
        user = UserFactory()
        mock_service = MagicMock()
        mock_service.handle_callback.return_value = user
        mock_service.issue_exchange_code.return_value = "single-use-code"
        mock_service_cls.return_value = mock_service

        response = client.get(
            google_callback_url, {"code": "valid-code", "state": "valid-state"}
        )
        assert response.status_code == 302
        location = response["Location"]
        assert "#code=single-use-code" in location
        assert "access=" not in location
        assert "refresh=" not in location
        mock_service.issue_exchange_code.assert_called_once_with(user)

    @patch("apps.users.views.GoogleOAuthService")
    def test_successful_callback_puts_no_tokens_in_url(
        self, mock_service_cls, client, google_callback_url
    ):
        """No access/refresh token appears anywhere in the redirect URL, and the
        code lives in the fragment (#), not the query string (#43)."""
        user = UserFactory()
        mock_service = MagicMock()
        mock_service.handle_callback.return_value = user
        mock_service.issue_exchange_code.return_value = "single-use-code"
        mock_service_cls.return_value = mock_service

        response = client.get(
            google_callback_url, {"code": "valid-code", "state": "valid-state"}
        )
        location = response["Location"]
        assert "access=" not in location
        assert "refresh=" not in location
        fragment_start = location.index("#") if "#" in location else len(location)
        assert "code=" not in location[:fragment_start]

    @patch("apps.users.views.GoogleOAuthService")
    def test_successful_callback_redirects_to_frontend_url(
        self, mock_service_cls, client, google_callback_url
    ):
        """Redirect location must start with FRONTEND_URL."""
        from django.conf import settings

        user = UserFactory()
        mock_service = MagicMock()
        mock_service.handle_callback.return_value = user
        mock_service.issue_exchange_code.return_value = "single-use-code"
        mock_service_cls.return_value = mock_service

        response = client.get(
            google_callback_url, {"code": "valid-code", "state": "valid-state"}
        )
        assert response["Location"].startswith(settings.FRONTEND_URL)

    @override_settings(FRONTEND_URL="https://front.example/")
    @patch("apps.users.views.GoogleOAuthService")
    def test_success_redirect_strips_trailing_slash(
        self, mock_service_cls, client, google_callback_url
    ):
        """A trailing slash in FRONTEND_URL must not produce a double slash in
        the redirect (e.g. //auth/callback), which breaks SPA routing (#43)."""
        user = UserFactory()
        mock_service = MagicMock()
        mock_service.handle_callback.return_value = user
        mock_service.issue_exchange_code.return_value = "thecode"
        mock_service_cls.return_value = mock_service

        response = client.get(
            google_callback_url, {"code": "valid-code", "state": "valid-state"}
        )
        assert (
            response["Location"] == "https://front.example/auth/callback#code=thecode"
        )

    @override_settings(FRONTEND_URL="https://front.example/")
    def test_error_redirect_strips_trailing_slash(self, client, google_callback_url):
        """Error redirects must also avoid the double slash (#43)."""
        response = client.get(google_callback_url, {"state": "only-state"})
        assert (
            response["Location"]
            == "https://front.example/auth/error?reason=missing_params"
        )


# ---------------------------------------------------------------------------
# GoogleTokenExchangeView (#43, step 1)
# ---------------------------------------------------------------------------


@pytest.fixture
def google_exchange_url():
    return reverse("google-token-exchange")


@pytest.mark.django_db
class TestGoogleTokenExchangeView:
    """POST /api/auth/google/exchange/ — redeem a single-use code for tokens."""

    def test_valid_code_returns_token_pair(self, client, google_exchange_url):
        """A valid code returns an access + refresh pair in the body (#43)."""
        from apps.users.services.google_oauth import GoogleOAuthService

        user = UserFactory()
        code = GoogleOAuthService().issue_exchange_code(user)

        response = client.post(google_exchange_url, {"code": code}, format="json")

        assert response.status_code == 200
        assert "access" in response.data
        assert "refresh" in response.data

    def test_invalid_code_returns_400(self, client, google_exchange_url):
        """An unknown/expired code is rejected with 400."""
        response = client.post(google_exchange_url, {"code": "bogus"}, format="json")
        assert response.status_code == 400

    def test_missing_code_returns_400(self, client, google_exchange_url):
        """A request without a code is rejected with 400."""
        response = client.post(google_exchange_url, {}, format="json")
        assert response.status_code == 400

    def test_code_is_single_use(self, client, google_exchange_url):
        """The same code cannot be exchanged twice (#43)."""
        from apps.users.services.google_oauth import GoogleOAuthService

        user = UserFactory()
        code = GoogleOAuthService().issue_exchange_code(user)

        first = client.post(google_exchange_url, {"code": code}, format="json")
        second = client.post(google_exchange_url, {"code": code}, format="json")

        assert first.status_code == 200
        assert second.status_code == 400

    def test_no_auth_required(self, client, google_exchange_url):
        """The endpoint is public — the code itself authenticates (#43)."""
        response = client.post(google_exchange_url, {"code": "bogus"}, format="json")
        assert response.status_code != 401

    def test_exchange_ignores_stale_bearer_header(self, client, google_exchange_url):
        """A stale/expired Authorization header must not 401 the public exchange:
        it runs no JWT authentication and is authenticated by the code (#43).

        Without this, the SPA's axios interceptor attaching an old token would
        make the global JWTAuthentication reject a perfectly valid exchange.
        """
        from apps.users.services.google_oauth import GoogleOAuthService

        user = UserFactory()
        code = GoogleOAuthService().issue_exchange_code(user)

        response = client.post(
            google_exchange_url,
            {"code": code},
            format="json",
            HTTP_AUTHORIZATION="Bearer invalid.stale.token",
        )

        assert response.status_code == 200
        assert "access" in response.data
