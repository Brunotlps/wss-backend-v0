"""Throttle classes for the core app."""

from rest_framework.throttling import AnonRateThrottle


class HealthCheckThrottle(AnonRateThrottle):
    """Limit hits on the public liveness probe per IP address.

    The endpoint stays ``AllowAny`` for load balancers and uptime
    monitors, but an explicit throttle guards against abuse and
    DoS-amplification. Rate is configured under the ``health`` scope
    (DEFAULT_THROTTLE_RATES).
    """

    scope = "health"
