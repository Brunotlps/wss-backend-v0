"""Tests for public certificate verification throttling (#76)."""

from django.core.cache import cache

from rest_framework import status

import pytest

from apps.certificates.factories import CertificateFactory
from apps.certificates.throttles import VerifyThrottle


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear Django cache before and after each test to reset throttle counters."""
    cache.clear()
    yield
    cache.clear()


@pytest.mark.django_db
class TestVerifyByCodeThrottling:
    """Rate limiting on GET /api/certificates/validate/{code}/ (AllowAny)."""

    URL = "/api/certificates/"

    def test_verify_throttle_rate_is_20_per_minute(self):
        """The dedicated verification throttle is configured at 20/min."""
        assert VerifyThrottle().rate == "20/min"

    def test_allows_up_to_20_verifications_per_minute(self, api_client):
        """Anonymous verification is allowed 20 times per minute, then blocked."""
        cert = CertificateFactory(is_valid=True)
        url = f"{self.URL}validate/{cert.certificate_code}/"

        for _ in range(20):
            response = api_client.get(url)
            assert response.status_code == status.HTTP_200_OK

        response = api_client.get(url)
        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
