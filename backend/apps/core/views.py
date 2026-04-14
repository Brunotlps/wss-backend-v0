"""Views for the core app."""

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


@api_view(["GET"])
@permission_classes([AllowAny])
def health_check(request):
    """Liveness probe — returns 200 if the process is alive.

    Used by Docker healthcheck, load balancers, and uptime monitoring tools.
    Does not check database or Redis connectivity (liveness, not readiness).

    Returns:
        200: {"status": "ok", "message": ..., "version": ...}
    """
    return Response({
        "status": "ok",
        "message": "WSS Backend API is running!",
        "version": "1.0.0",
    })
