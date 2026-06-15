"""Tests for the shared cache backend configuration (#97).

These assert the *base* settings (inherited by production), independent of the
active test settings, so they do not require a running Redis instance.
"""

import config.settings.base as base_settings


class TestSharedCacheConfig:
    """The default cache must be a shared Redis backend in base/production."""

    def test_default_cache_uses_redis_backend(self):
        """Throttle counters must live in Redis, not per-process LocMemCache."""
        cache = base_settings.CACHES["default"]
        assert cache["BACKEND"] == "django_redis.cache.RedisCache"

    def test_default_cache_fails_open_on_redis_outage(self):
        """A Redis outage must not 500 the API (fail-open, no throttling)."""
        options = base_settings.CACHES["default"]["OPTIONS"]
        assert options["IGNORE_EXCEPTIONS"] is True

    def test_cache_uses_separate_redis_db_from_celery_broker(self):
        """Cache and Celery broker must not share a Redis DB (key collisions)."""
        from urllib.parse import urlsplit

        cache_db = urlsplit(base_settings.CACHES["default"]["LOCATION"]).path
        broker_db = urlsplit(base_settings.CELERY_BROKER_URL).path
        assert cache_db == "/1"
        assert cache_db != broker_db
