"""Throttle classes for the certificates app."""

from rest_framework.throttling import AnonRateThrottle


class VerifyThrottle(AnonRateThrottle):
    """Limit public certificate verification by code per IP address.

    The verification endpoint is ``AllowAny`` and leaks the student's
    name on a hit, so it must be throttled to make code enumeration
    infeasible. Rate is configured under the ``verify`` scope
    (DEFAULT_THROTTLE_RATES).
    """

    scope = "verify"
