"""Tests for core app views."""

from unittest.mock import patch

from django.db.utils import OperationalError

from rest_framework import status

import pytest


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

    def test_health_check_head_returns_200(self, api_client):
        """The endpoint declares HEAD; a HEAD probe must also return 200."""
        response = api_client.head(self.URL)
        assert response.status_code == status.HTTP_200_OK

    def test_health_check_response_shape(self, api_client):
        """The public liveness contract is status/message/version, nothing else."""
        response = api_client.get(self.URL)
        assert set(response.data.keys()) == {"status", "message", "version"}
        assert response.data["status"] == "ok"
        assert response.data["message"] == "WSS Backend API is running!"
        assert isinstance(response.data["version"], str) and response.data["version"]


@pytest.mark.django_db
class TestReadinessCheck:
    """Tests for GET /api/health/ready/ readiness probe (#88)."""

    URL = "/api/health/ready/"

    def test_ready_returns_200_when_dependencies_ok(self, api_client):
        """Readiness returns 200 (no auth) when DB and cache are reachable."""
        response = api_client.get(self.URL)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "ready"
        assert response.data["checks"]["database"] == "ok"
        assert response.data["checks"]["cache"] == "ok"

    def test_ready_returns_503_when_database_down(self, api_client):
        """A DB outage yields 503 with the database check marked error."""
        with patch(
            "apps.core.views.connection.cursor",
            side_effect=OperationalError("db down"),
        ):
            response = api_client.get(self.URL)
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert response.data["status"] == "not ready"
        assert response.data["checks"]["database"] == "error"

    def test_ready_returns_503_when_cache_down(self, api_client):
        """A cache outage yields 503 with the cache check marked error.

        ``_check_cache`` is patched (rather than the shared cache object) so the
        simulated outage does not also break the endpoint's own throttle, which
        uses the same default cache in ``initial()``.
        """
        with patch("apps.core.views._check_cache", return_value=False):
            response = api_client.get(self.URL)
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert response.data["status"] == "not ready"
        assert response.data["checks"]["cache"] == "error"

    def test_check_cache_returns_false_on_backend_error(self):
        """_check_cache detects a real backend failure (set raises)."""
        from apps.core.views import _check_cache

        with patch("apps.core.views.cache.set", side_effect=Exception("redis down")):
            assert _check_cache() is False

    def test_check_database_returns_false_on_backend_error(self):
        """_check_database detects a real backend failure (cursor raises)."""
        from apps.core.views import _check_database

        with patch(
            "apps.core.views.connection.cursor",
            side_effect=OperationalError("db down"),
        ):
            assert _check_database() is False

    def test_ready_failure_body_has_no_traceback(self, api_client):
        """The 503 body must not leak a stack trace."""
        with patch(
            "apps.core.views.connection.cursor",
            side_effect=OperationalError("db down"),
        ):
            response = api_client.get(self.URL)
        body = str(response.data)
        assert "Traceback" not in body
        assert "db down" not in body
