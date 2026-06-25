"""Throttle classes for the videos app."""

from rest_framework.throttling import UserRateThrottle


class UploadRateThrottle(UserRateThrottle):
    """Limit video uploads to 10 per day per authenticated user.

    Video uploads are expensive (storage and downstream processing); this
    caps automated abuse of the create endpoint. Each user has an independent
    counter. Applied only to the create action (see ``VideoViewSet``).

    A dedicated ``scope`` is required: ``UserRateThrottle`` defaults to
    ``scope = "user"``, which keys the cache on ``throttle_user_<id>`` — the
    same bucket as the global default ``user`` throttle (1000/hour). Sharing
    that bucket would let ordinary authenticated traffic erode the upload
    allowance (and vice-versa). ``video_upload`` isolates the counter.
    ``rate`` is set on the class, so ``get_rate()`` never consults
    ``DEFAULT_THROTTLE_RATES`` and the scope needs no settings entry.
    """

    scope = "video_upload"
    rate = "10/day"
