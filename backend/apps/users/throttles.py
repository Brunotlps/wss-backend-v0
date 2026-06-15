"""Throttle classes for the users app."""

from rest_framework.throttling import AnonRateThrottle


class LoginRateThrottle(AnonRateThrottle):
    """Limit login attempts per IP address.

    Applies to both successful and failed attempts to prevent
    brute-force attacks and valid-account enumeration. Rate is
    configured under the ``login`` scope (DEFAULT_THROTTLE_RATES).
    """

    scope = "login"


class RegistrationThrottle(AnonRateThrottle):
    """Limit account-creation attempts per IP address.

    Prevents registration spam. Rate is configured under the
    ``register`` scope (DEFAULT_THROTTLE_RATES).
    """

    scope = "register"


class OAuthRateThrottle(AnonRateThrottle):
    """Limit Google OAuth flow initiations/callbacks per IP address.

    Prevents token-exchange abuse on the OAuth endpoints. Rate is
    configured under the ``oauth`` scope (DEFAULT_THROTTLE_RATES).
    """

    scope = "oauth"
