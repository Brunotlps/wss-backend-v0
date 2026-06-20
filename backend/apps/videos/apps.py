from django.apps import AppConfig


class VideosConfig(AppConfig):
    """Django application configuration for the videos app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.videos"
    verbose_name = "Video Content"

    def ready(self) -> None:
        """Register signal handlers (async duration extraction on upload)."""
        import apps.videos.signals  # noqa: F401
