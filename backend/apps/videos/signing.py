"""Short-lived signed tokens for protected video streaming.

A browser ``<video src>`` cannot send an Authorization header, so protected
video bytes are reached via a signed, expiring token bound to a single video.
The token is issued by the ``stream-url`` endpoint only after the enrollment
check passes, and validated by the ``file`` endpoint without any header.

The token is an HMAC (Django ``TimestampSigner``, keyed by ``SECRET_KEY``) over
the video id, so it cannot be forged and cannot be replayed against another
video. ``TimestampSigner`` embeds the issue time, enforcing expiry on validation.

Security note — the signed URL is intentionally a **bearer capability**: anyone
holding it (browser history, a shared link, an access log) can fetch that one
video's bytes until the token expires, with no Authorization header. This is the
accepted trade-off that lets a plain ``<video src>`` stream with native
Range/seek. It is deliberately scoped (one video) and short-lived (TTL below),
and is a *separate* token from the JWT — never put the JWT itself in a URL.
Clients should re-request ``stream-url`` if playback fails after expiry.
"""

from typing import Optional

from django.conf import settings
from django.core import signing

# Salt namespaces this signature so a token cannot be reused with other signers.
_STREAM_SALT = "apps.videos.signing.video-stream"

# Default TTL (2h) comfortably covers a single viewing session (a long lecture
# plus seeks) while keeping the leak window small; the token is scoped to one
# video and only issued after IsEnrolled passes. Override via env if needed.
DEFAULT_STREAM_URL_TTL_SECONDS = 2 * 60 * 60


def _ttl_seconds() -> int:
    """Return the configured signed-URL lifetime in seconds."""
    return getattr(
        settings, "VIDEO_STREAM_URL_TTL_SECONDS", DEFAULT_STREAM_URL_TTL_SECONDS
    )


def sign_video_stream(video_id: int) -> str:
    """Return a signed, timestamped token authorizing access to one video.

    Args:
        video_id: Primary key of the video the token grants access to.

    Returns:
        An opaque signed token to be placed in the ``sig`` query parameter.
    """
    return signing.TimestampSigner(salt=_STREAM_SALT).sign(str(video_id))


def unsign_video_stream(token: str) -> Optional[int]:
    """Validate a stream token and return its video id, or None if invalid.

    The token is rejected when the signature is bad or it is older than the
    configured TTL.

    Args:
        token: The value of the ``sig`` query parameter.

    Returns:
        The video id encoded in the token, or None if invalid/expired.
    """
    if not token:
        return None
    try:
        value = signing.TimestampSigner(salt=_STREAM_SALT).unsign(
            token, max_age=_ttl_seconds()
        )
    except signing.BadSignature:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
