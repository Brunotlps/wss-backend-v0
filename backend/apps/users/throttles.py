"""Throttle classes for the users app."""

from rest_framework.throttling import AnonRateThrottle


class LoginRateThrottle(AnonRateThrottle):
    """Limit login attempts to 5 per hour per IP address.

    Applies to both successful and failed attempts to prevent
    brute-force attacks and valid-account enumeration.
    """

    rate = "5/hour"
