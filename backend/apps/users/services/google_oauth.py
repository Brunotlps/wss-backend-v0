"""Google OAuth 2.0 + OIDC service."""

import logging
import secrets
from typing import Any
from urllib.parse import urlencode

import requests as http_requests
from django.conf import settings
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

from apps.users.models import SocialAccount, User

logger = logging.getLogger(__name__)

_GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
_SCOPES = "openid email profile"


class GoogleOAuthService:
    """Handles the Authorization Code flow for Google OAuth 2.0 + OIDC.

    Flow:
        1. get_authorization_url → redirects user to Google
        2. handle_callback → validates state, exchanges code, validates
           id_token, and finds or creates the local User.
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_authorization_url(self, request: Any) -> str:
        """Build the Google authorization URL and persist state/nonce.

        Args:
            request: Django request. Must have a mutable .session.

        Returns:
            Full Google authorization URL with all required parameters.
        """
        state = secrets.token_urlsafe(32)
        nonce = secrets.token_urlsafe(32)

        request.session["google_oauth_state"] = state
        request.session["google_oauth_nonce"] = nonce

        params = {
            "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
            "redirect_uri": settings.GOOGLE_OAUTH_REDIRECT_URI,
            "response_type": "code",
            "scope": _SCOPES,
            "state": state,
            "nonce": nonce,
            "access_type": "online",
        }
        return f"{_GOOGLE_AUTH_URL}?{urlencode(params)}"

    def handle_callback(self, request: Any, code: str, state: str) -> User:
        """Process the OAuth callback after Google redirects back.

        Args:
            request: Django request containing the session with stored state/nonce.
            code: Authorization code from Google.
            state: State parameter returned by Google.

        Returns:
            The authenticated (or newly created) User instance.

        Raises:
            ValueError: On state mismatch, invalid id_token, or unverified email.
        """
        self._validate_state(request, state)

        nonce = request.session.get("google_oauth_nonce", "")
        tokens = self._exchange_code(code)
        claims = self._validate_id_token(tokens["id_token"], nonce)
        user, created = self._find_or_create_user(claims)

        if created:
            logger.info("New user created via Google OAuth: %s", user.email)
        else:
            logger.info("Existing user authenticated via Google OAuth: %s", user.email)

        return user

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _validate_state(self, request: Any, state: str) -> None:
        """Verify the state parameter matches the session value (anti-CSRF).

        Raises:
            ValueError: If state is missing from session or does not match.
        """
        session_state = request.session.get("google_oauth_state")
        if not session_state or session_state != state:
            raise ValueError("Invalid or missing OAuth state parameter.")

    def _exchange_code(self, code: str) -> dict:
        """Exchange the authorization code for tokens via server-to-server POST.

        Args:
            code: Authorization code received from Google.

        Returns:
            Token response dict containing at minimum 'id_token'.

        Raises:
            ValueError: If the token exchange fails.
        """
        payload = {
            "code": code,
            "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
            "client_secret": settings.GOOGLE_OAUTH_CLIENT_SECRET,
            "redirect_uri": settings.GOOGLE_OAUTH_REDIRECT_URI,
            "grant_type": "authorization_code",
        }
        response = http_requests.post(_GOOGLE_TOKEN_URL, data=payload, timeout=10)

        if not response.ok:
            logger.error("Google token exchange failed: %s", response.text)
            raise ValueError("Failed to exchange authorization code with Google.")

        return response.json()

    def _validate_id_token(self, raw_id_token: str, nonce: str) -> dict:
        """Validate the Google id_token and return its claims.

        Verifies signature via Google's JWKS, plus iss, aud, exp (handled by
        the library), email_verified, and nonce.

        Args:
            raw_id_token: JWT string from the token response.
            nonce: Nonce stored in the session before the redirect.

        Returns:
            Verified claims dict.

        Raises:
            ValueError: On any validation failure.
        """
        request_adapter = google_requests.Request()
        claims = id_token.verify_oauth2_token(
            raw_id_token,
            request_adapter,
            settings.GOOGLE_OAUTH_CLIENT_ID,
        )

        if not claims.get("email_verified"):
            raise ValueError("Google account email_verified is False.")

        if claims.get("nonce") != nonce:
            raise ValueError("id_token nonce mismatch — possible replay attack.")

        return claims

    def _find_or_create_user(self, claims: dict) -> tuple[User, bool]:
        """Find an existing user or create a new one from Google claims.

        Lookup priority:
            1. SocialAccount with matching provider uid (Google 'sub').
            2. User with matching verified email → link a new SocialAccount.
            3. Create a new User + SocialAccount.

        Args:
            claims: Verified id_token claims dict.

        Returns:
            Tuple of (User instance, created: bool).
        """
        uid = claims["sub"]
        email = claims["email"]
        extra_data = {
            "email": email,
            "name": claims.get("name", ""),
            "picture": claims.get("picture", ""),
            "email_verified": claims.get("email_verified", False),
        }

        # 1. Known Google account → return linked user
        try:
            account = SocialAccount.objects.select_related("user").get(
                provider=SocialAccount.Provider.GOOGLE,
                uid=uid,
            )
            account.extra_data = extra_data
            account.save(update_fields=["extra_data", "updated_at"])
            return account.user, False
        except SocialAccount.DoesNotExist:
            pass

        # 2. Existing user with same verified email → link new SocialAccount
        try:
            user = User.objects.get(email=email)
            SocialAccount.objects.create(
                user=user,
                provider=SocialAccount.Provider.GOOGLE,
                uid=uid,
                extra_data=extra_data,
            )
            return user, False
        except User.DoesNotExist:
            pass

        # 3. Brand new user
        user = self._create_user_from_claims(claims, extra_data, uid)
        return user, True

    def _create_user_from_claims(
        self, claims: dict, extra_data: dict, uid: str
    ) -> User:
        """Create a User + SocialAccount from Google claims.

        Args:
            claims: Verified id_token claims.
            extra_data: Prepared extra_data dict for SocialAccount.
            uid: Google 'sub' claim.

        Returns:
            Newly created User (Profile auto-created via signal).
        """
        email = claims["email"]
        base_username = email.split("@")[0]
        username = self._unique_username(base_username)

        user = User.objects.create_user(
            username=username,
            email=email,
            first_name=claims.get("given_name", ""),
            last_name=claims.get("family_name", ""),
            password=None,  # unusable password — login only via Google
        )

        SocialAccount.objects.create(
            user=user,
            provider=SocialAccount.Provider.GOOGLE,
            uid=uid,
            extra_data=extra_data,
        )

        return user

    @staticmethod
    def _unique_username(base: str) -> str:
        """Return a unique username derived from base, appending a counter if needed."""
        username = base
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base}{counter}"
            counter += 1
        return username
