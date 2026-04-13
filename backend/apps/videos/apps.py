from django.apps import AppConfig


class VideosConfig(AppConfig):
    """Django application configuration for the videos app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.videos"
    verbose_name = "Video Content"
