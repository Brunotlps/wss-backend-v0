"""Tests for GoogleOAuthService — authorization URL and callback handling."""

import pytest
from unittest.mock import MagicMock, patch

from django.test import RequestFactory

from apps.users.factories import SocialAccountFactory, UserFactory
from apps.users.models import SocialAccount, User
from apps.users.services.google_oauth import GoogleOAuthService


# ---------------------------------------------------------------------------
# Etapa 2 — get_authorization_url
# ---------------------------------------------------------------------------


class TestGetAuthorizationUrl:
    """Test URL generation and session state storage."""

    def setup_method(self):
        self.factory = RequestFactory()
        self.service = GoogleOAuthService()

    def _make_request(self):
        request = self.factory.get("/api/auth/google/")
        request.session = {}
        return request

    def test_returns_google_accounts_url(self):
        """Authorization URL must point to accounts.google.com."""
        request = self._make_request()
        url = self.service.get_authorization_url(request)
        assert "accounts.google.com" in url

    def test_url_contains_response_type_code(self):
        """URL must include response_type=code (Authorization Code flow)."""
        request = self._make_request()
        url = self.service.get_authorization_url(request)
        assert "response_type=code" in url

    def test_url_contains_openid_scope(self):
        """URL must request openid, email and profile scopes."""
        request = self._make_request()
        url = self.service.get_authorization_url(request)
        assert "openid" in url
        assert "email" in url

    def test_stores_state_in_session(self):
        """State token must be saved in the session."""
        request = self._make_request()
        self.service.get_authorization_url(request)
        assert "google_oauth_state" in request.session

    def test_stores_nonce_in_session(self):
        """Nonce must be saved in the session."""
        request = self._make_request()
        self.service.get_authorization_url(request)
        assert "google_oauth_nonce" in request.session

    def test_state_is_random_between_calls(self):
        """Two consecutive calls must produce different state values."""
        req1 = self._make_request()
        req2 = self._make_request()
        self.service.get_authorization_url(req1)
        self.service.get_authorization_url(req2)
        assert req1.session["google_oauth_state"] != req2.session["google_oauth_state"]

    def test_nonce_is_random_between_calls(self):
        """Two consecutive calls must produce different nonce values."""
        req1 = self._make_request()
        req2 = self._make_request()
        self.service.get_authorization_url(req1)
        self.service.get_authorization_url(req2)
        assert req1.session["google_oauth_nonce"] != req2.session["google_oauth_nonce"]

    def test_state_minimum_entropy(self):
        """State must have at least 32 characters (secrets.token_urlsafe)."""
        request = self._make_request()
        self.service.get_authorization_url(request)
        assert len(request.session["google_oauth_state"]) >= 32

    def test_url_contains_state_parameter(self):
        """The generated state must appear in the authorization URL."""
        request = self._make_request()
        url = self.service.get_authorization_url(request)
        state = request.session["google_oauth_state"]
        assert state in url


# ---------------------------------------------------------------------------
# Etapa 3 — handle_callback: state validation
# ---------------------------------------------------------------------------


class TestHandleCallbackStateValidation:
    """Test CSRF state validation in callback handling."""

    def setup_method(self):
        self.factory = RequestFactory()
        self.service = GoogleOAuthService()

    def _make_callback_request(self, session_state="valid-state", session_nonce="valid-nonce"):
        request = self.factory.get("/api/auth/google/callback/")
        request.session = {
            "google_oauth_state": session_state,
            "google_oauth_nonce": session_nonce,
        }
        return request

    def test_mismatched_state_raises_value_error(self):
        """Callback with wrong state must raise ValueError (CSRF protection)."""
        request = self._make_callback_request(session_state="expected-state")
        with pytest.raises(ValueError, match="state"):
            self.service.handle_callback(request, code="any-code", state="wrong-state")

    def test_missing_state_in_session_raises_value_error(self):
        """Callback when session has no state must raise ValueError."""
        request = self.factory.get("/api/auth/google/callback/")
        request.session = {}  # empty session — no state stored
        with pytest.raises(ValueError, match="state"):
            self.service.handle_callback(request, code="any-code", state="some-state")


# ---------------------------------------------------------------------------
# Etapa 3 — handle_callback: id_token validation
# ---------------------------------------------------------------------------


class TestValidateIdToken:
    """Test id_token validation via Google JWKS."""

    def setup_method(self):
        self.service = GoogleOAuthService()

    @patch("apps.users.services.google_oauth.id_token.verify_oauth2_token")
    def test_invalid_token_raises_value_error(self, mock_verify):
        """A token rejected by Google must propagate as ValueError."""
        mock_verify.side_effect = ValueError("Token is invalid")
        with pytest.raises(ValueError):
            self.service._validate_id_token("bad-token", "any-nonce")

    @patch("apps.users.services.google_oauth.id_token.verify_oauth2_token")
    def test_email_not_verified_raises_value_error(self, mock_verify):
        """id_token with email_verified=False must raise ValueError."""
        mock_verify.return_value = {
            "sub": "12345",
            "email": "user@gmail.com",
            "email_verified": False,
            "nonce": "valid-nonce",
        }
        with pytest.raises(ValueError, match="email_verified"):
            self.service._validate_id_token("some-token", "valid-nonce")

    @patch("apps.users.services.google_oauth.id_token.verify_oauth2_token")
    def test_nonce_mismatch_raises_value_error(self, mock_verify):
        """id_token with wrong nonce must raise ValueError (replay protection)."""
        mock_verify.return_value = {
            "sub": "12345",
            "email": "user@gmail.com",
            "email_verified": True,
            "nonce": "wrong-nonce",
        }
        with pytest.raises(ValueError, match="nonce"):
            self.service._validate_id_token("some-token", "expected-nonce")

    @patch("apps.users.services.google_oauth.id_token.verify_oauth2_token")
    def test_valid_token_returns_claims(self, mock_verify):
        """Valid token with correct nonce returns the claims dict."""
        claims = {
            "sub": "google-sub-99",
            "email": "valid@gmail.com",
            "email_verified": True,
            "nonce": "my-nonce",
            "name": "Valid User",
        }
        mock_verify.return_value = claims
        result = self.service._validate_id_token("valid-token", "my-nonce")
        assert result == claims


# ---------------------------------------------------------------------------
# Etapa 4 — _find_or_create_user
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestFindOrCreateUser:
    """Test user lookup and creation from Google claims."""

    def setup_method(self):
        self.service = GoogleOAuthService()

    def _claims(self, **overrides):
        base = {
            "sub": "google-sub-findcreate",
            "email": "findcreate@gmail.com",
            "email_verified": True,
            "name": "Find Create",
            "given_name": "Find",
            "family_name": "Create",
            "picture": "https://lh3.googleusercontent.com/photo.jpg",
        }
        base.update(overrides)
        return base

    def test_existing_social_account_returns_linked_user(self):
        """Claims matching a SocialAccount uid must return its user."""
        account = SocialAccountFactory(uid="google-sub-findcreate")
        claims = self._claims(sub="google-sub-findcreate")
        user, created = self.service._find_or_create_user(claims)
        assert user == account.user
        assert created is False

    def test_existing_email_links_new_social_account(self):
        """Claims matching an existing User email must link a new SocialAccount."""
        existing_user = UserFactory(email="findcreate@gmail.com")
        claims = self._claims(sub="google-sub-new-link")
        user, created = self.service._find_or_create_user(claims)
        assert user == existing_user
        assert created is False
        assert SocialAccount.objects.filter(
            user=existing_user, provider="google", uid="google-sub-new-link"
        ).exists()

    def test_new_user_created_from_google_claims(self):
        """Claims with no matching user must create a new User and SocialAccount."""
        claims = self._claims(sub="google-sub-brand-new", email="brandnew@gmail.com")
        user, created = self.service._find_or_create_user(claims)
        assert created is True
        assert User.objects.filter(email="brandnew@gmail.com").exists()
        assert SocialAccount.objects.filter(uid="google-sub-brand-new").exists()

    def test_new_user_profile_created_via_signal(self):
        """New user created from Google must have a Profile (via post_save signal)."""
        claims = self._claims(sub="google-sub-profile-test", email="profiletest@gmail.com")
        user, _ = self.service._find_or_create_user(claims)
        assert hasattr(user, "profile")
        assert user.profile is not None

    def test_new_user_first_last_name_from_claims(self):
        """First and last name must be populated from Google claims."""
        claims = self._claims(
            sub="google-sub-names",
            email="names@gmail.com",
            given_name="Bruno",
            family_name="Teixeira",
        )
        user, _ = self.service._find_or_create_user(claims)
        assert user.first_name == "Bruno"
        assert user.last_name == "Teixeira"

    def test_extra_data_stored_on_social_account(self):
        """Provider data (email, name, picture) must be saved in extra_data."""
        claims = self._claims(sub="google-sub-extradata", email="extradata@gmail.com")
        user, _ = self.service._find_or_create_user(claims)
        account = SocialAccount.objects.get(uid="google-sub-extradata")
        assert account.extra_data["email"] == "extradata@gmail.com"
        assert "name" in account.extra_data

    def test_existing_social_account_extra_data_updated(self):
        """Re-authenticating with an existing SocialAccount must refresh extra_data."""
        account = SocialAccountFactory(
            uid="google-sub-refresh",
            extra_data={"email": "old@gmail.com", "name": "Old Name"},
        )
        claims = self._claims(
            sub="google-sub-refresh",
            email=account.user.email,
            name="New Name",
        )
        self.service._find_or_create_user(claims)
        account.refresh_from_db()
        assert account.extra_data["name"] == "New Name"
