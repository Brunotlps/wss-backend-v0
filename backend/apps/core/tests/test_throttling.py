"""Tests for the core health endpoint throttling (#87)."""

from django.core.cache import cache

from rest_framework import status

import pytest

from apps.core.throttles import HealthCheckThrottle


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear Django cache before and after each test to reset throttle counters."""
    cache.clear()
    yield
    cache.clear()


@pytest.mark.django_db
class TestHealthCheckThrottling:
    """Rate limiting on GET /api/health/ (AllowAny liveness probe)."""

    URL = "/api/health/"

    def test_health_throttle_rate_is_configured(self):
        """The health endpoint has an explicit anonymous throttle rate."""
        assert HealthCheckThrottle().rate == "120/min"

    def test_health_check_is_throttled(self, api_client, monkeypatch):
        """Repeated hits beyond the limit return 429 (abuse/DoS guard)."""
        monkeypatch.setattr(HealthCheckThrottle, "rate", "2/min", raising=False)

        for _ in range(2):
            response = api_client.get(self.URL)
            assert response.status_code == status.HTTP_200_OK

        response = api_client.get(self.URL)
        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
