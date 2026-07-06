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


class OAuthExchangeRateThrottle(AnonRateThrottle):
    """Limit the OAuth code-exchange endpoint per IP address (#155).

    A dedicated scope is required: sharing ``OAuthRateThrottle``'s ``oauth``
    scope would mean a single login already spends ~3 of the 20/hour budget
    (init + callback + exchange), and the exchange endpoint — the natural
    brute-force target for the single-use code — would erode the same bucket
    that gates legitimate login-init/callback traffic from that IP. Rate is
    configured under the ``oauth-exchange`` scope (DEFAULT_THROTTLE_RATES),
    same class of fix as #57 (``video_upload``) and #136 (``payment_intent``).
    """

    scope = "oauth-exchange"
