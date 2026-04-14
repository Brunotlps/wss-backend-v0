"""Tests for core app views."""

import pytest
from rest_framework import status


@pytest.mark.django_db
class TestHealthCheck:
    """Tests for GET /api/health/ liveness probe."""

    URL = "/api/health/"

    def test_health_check_returns_200_unauthenticated(self, api_client):
        """Health endpoint must be accessible without authentication."""
        response = api_client.get(self.URL)
        assert response.status_code == status.HTTP_200_OK

    def test_health_check_response_contains_status_ok(self, api_client):
        """Health endpoint must return a body with status == "ok"."""
        response = api_client.get(self.URL)
        assert response.data["status"] == "ok"
