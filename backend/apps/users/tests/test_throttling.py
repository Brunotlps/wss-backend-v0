"""Tests for auth endpoint throttling (login, registration, OAuth)."""

from django.conf import settings
from django.core.cache import cache
from django.urls import reverse

from rest_framework import status
from rest_framework.throttling import AnonRateThrottle

import pytest

from apps.users.throttles import OAuthRateThrottle, RegistrationThrottle


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear Django cache before and after each test to reset throttle counters."""
    cache.clear()
    yield
    cache.clear()


@pytest.mark.django_db
class TestLoginThrottling:
    """Tests for rate limiting on POST /api/auth/token/."""

    URL = reverse("token_obtain_pair")

    def test_allows_up_to_5_login_attempts_per_hour(self, api_client):
        """Anonymous users can attempt login 5 times per hour before being throttled."""
        payload = {
            "email": "nonexistent@example.com",
            "password": "wrongpassword",
        }

        for _ in range(5):
            response = api_client.post(self.URL, payload, format="json")
            assert response.status_code == status.HTTP_401_UNAUTHORIZED

        response = api_client.post(self.URL, payload, format="json")
        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS

    def test_successful_login_also_counts_toward_limit(self, api_client):
        """Successful logins count toward the throttle limit (prevents enumeration)."""
        from apps.users.factories import UserFactory

        user = UserFactory(password="testpass123")
        payload = {"email": user.email, "password": "testpass123"}

        for _ in range(5):
            response = api_client.post(self.URL, payload, format="json")
            assert response.status_code == status.HTTP_200_OK

        response = api_client.post(self.URL, payload, format="json")
        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS


@pytest.mark.django_db
class TestRegistrationThrottling:
    """Rate limiting on POST /api/auth/register/ (#49)."""

    URL = reverse("register")

    def test_registration_throttle_rate_is_5_per_day(self):
        """Registration throttle is configured at 5/day."""
        assert RegistrationThrottle().rate == "5/day"

    def test_allows_up_to_5_registration_attempts_per_day(self, api_client):
        """Anonymous registration is allowed 5 times per day, then blocked.

        Invalid payloads still count toward the limit, preventing
        account-creation spam regardless of validation outcome.
        """
        payload = {}  # invalid → 400, but each request counts toward throttle

        for _ in range(5):
            response = api_client.post(self.URL, payload, format="json")
            assert response.status_code == status.HTTP_400_BAD_REQUEST

        response = api_client.post(self.URL, payload, format="json")
        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS


class TestProxyXForwardedForHandling:
    """Throttle keying behind Cloudflare + Nginx (#48).

    After Nginx is configured with ``real_ip`` (CF-Connecting-IP) and the api
    block overwrites X-Forwarded-For with the trusted ``$remote_addr``, only a
    single trusted hop reaches Django. ``NUM_PROXIES`` must be reconciled to 1
    so DRF keys throttles on the real client IP and a spoofed XFF prefix cannot
    rotate the key to bypass the limit.
    """

    def test_num_proxies_reconciled_to_one(self):
        """NUM_PROXIES is 1 (single trusted proxy hop after real_ip)."""
        assert settings.REST_FRAMEWORK["NUM_PROXIES"] == 1

    def test_spoofed_xff_prefix_cannot_rotate_throttle_key(self, rf):
        """A forged XFF prefix is ignored; the trusted last entry keys the throttle.

        This covers the DRF half (NUM_PROXIES arithmetic). The actual control is
        the Nginx ``X-Forwarded-For $remote_addr`` overwrite, which discards any
        client-forged XFF before it reaches Django (infra config, not unit-tested).
        """
        request = rf.get(
            "/",
            HTTP_X_FORWARDED_FOR="1.2.3.4, 203.0.113.7",
            REMOTE_ADDR="10.0.0.1",
        )
        ident = AnonRateThrottle().get_ident(request)
        # With NUM_PROXIES=1, only the last (proxy-appended) entry counts, so the
        # attacker-controlled "1.2.3.4" prefix cannot change the throttle bucket.
        assert ident == "203.0.113.7"

    def test_single_entry_xff_keys_on_real_client(self, rf):
        """The upload path (one trusted hop) keys on the single XFF entry."""
        request = rf.get(
            "/",
            HTTP_X_FORWARDED_FOR="203.0.113.7",
            REMOTE_ADDR="10.0.0.1",
        )
        ident = AnonRateThrottle().get_ident(request)
        assert ident == "203.0.113.7"


@pytest.mark.django_db
class TestGoogleOAuthThrottling:
    """Rate limiting on the Google OAuth flow (#49)."""

    URL = reverse("google-login")

    def test_oauth_throttle_rate_is_20_per_hour(self):
        """OAuth throttle is configured at 20/hour."""
        assert OAuthRateThrottle().rate == "20/hour"

    def test_google_login_is_throttled(self, api_client, monkeypatch):
        """Repeated OAuth initiations beyond the limit return 429."""
        monkeypatch.setattr(
            "apps.users.services.google_oauth.GoogleOAuthService."
            "get_authorization_url",
            lambda self, request: "https://accounts.google.com/o/oauth2/auth",
        )

        for _ in range(20):
            response = api_client.get(self.URL)
            assert response.status_code == status.HTTP_302_FOUND

        response = api_client.get(self.URL)
        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
