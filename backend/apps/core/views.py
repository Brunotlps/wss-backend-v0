"""Views for the core app."""

import logging

from django.core.cache import cache
from django.db import connection

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .throttles import HealthCheckThrottle

logger = logging.getLogger(__name__)


@api_view(["GET", "HEAD"])
@permission_classes([AllowAny])
@throttle_classes([HealthCheckThrottle])
def health_check(request):
    """Liveness probe — returns 200 if the process is alive.

    Used by Docker healthcheck, load balancers, and uptime monitoring tools.
    Does not check database or Redis connectivity (liveness, not readiness).

    Returns:
        200: {"status": "ok", "message": ..., "version": ...}
    """
    return Response(
        {
            "status": "ok",
            "message": "WSS Backend API is running!",
            "version": "1.0.0",
        }
    )


def _check_database() -> bool:
    """Return True if a trivial query succeeds against the default database."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        return True
    except Exception:
        logger.warning("Readiness: database check failed", exc_info=True)
        return False


def _check_cache() -> bool:
    """Return True if a set/get round-trip against the cache succeeds."""
    try:
        cache.set("readiness:probe", "ok", timeout=5)
        return cache.get("readiness:probe") == "ok"
    except Exception:
        logger.warning("Readiness: cache check failed", exc_info=True)
        return False


@api_view(["GET", "HEAD"])
@permission_classes([AllowAny])
@throttle_classes([HealthCheckThrottle])
def readiness_check(request):
    """Readiness probe — verifies the API can serve traffic.

    Unlike the liveness probe, this checks the critical backing services so a
    load balancer / uptime monitor can route away from an instance whose DB or
    cache is unavailable. Each check is wrapped so a failure degrades to a
    graceful 503 (the cause is logged server-side, never leaked in the body).

    Celery worker liveness is intentionally not probed here (would add a
    broadcast round-trip and latency); it is covered by separate monitoring.

    Returns:
        200: {"status": "ready", "checks": {"database": "ok", "cache": "ok"}}
        503: {"status": "not ready", "checks": {...}} if any dependency is down.
    """
    checks = {
        "database": "ok" if _check_database() else "error",
        "cache": "ok" if _check_cache() else "error",
    }
    ready = all(value == "ok" for value in checks.values())

    return Response(
        {"status": "ready" if ready else "not ready", "checks": checks},
        status=(status.HTTP_200_OK if ready else status.HTTP_503_SERVICE_UNAVAILABLE),
    )
