"""Throttle classes for the payments app."""

from rest_framework.throttling import UserRateThrottle


class PaymentIntentRateThrottle(UserRateThrottle):
    """Limit Payment Intent creation to 10 per day per authenticated user.

    Prevents abuse of the Stripe API and unexpected billing costs from
    automated requests. Each user has an independent counter.
    """

    rate = "10/day"
