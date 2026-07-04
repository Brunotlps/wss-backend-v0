"""Throttle classes for the payments app."""

from rest_framework.throttling import UserRateThrottle


class PaymentIntentRateThrottle(UserRateThrottle):
    """Limit Payment Intent creation to 10 per day per authenticated user.

    Prevents abuse of the Stripe API and unexpected billing costs from
    automated requests. Each user has an independent counter.

    A dedicated ``scope`` is required: ``UserRateThrottle`` defaults to
    ``scope = "user"``, which keys the cache on ``throttle_user_<id>`` — the
    same bucket as the global default ``user`` throttle (1000/hour). Sharing
    that bucket would let ordinary authenticated traffic erode the
    create-intent allowance (#136, mirrors #57's fix for video uploads).
    ``payment_intent`` isolates the counter. ``rate`` is set on the class, so
    ``get_rate()`` never consults ``DEFAULT_THROTTLE_RATES`` and the scope
    needs no settings entry.
    """

    scope = "payment_intent"
    rate = "10/day"
