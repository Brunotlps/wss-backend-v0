"""Tests for login endpoint throttling."""

import pytest
from django.core.cache import cache
from django.urls import reverse
from rest_framework import status


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
