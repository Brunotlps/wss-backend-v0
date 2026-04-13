from django.apps import AppConfig


class EnrollmentsConfig(AppConfig):
    """Django application configuration for the enrollments app.

    Registers signal handlers in ready() to enable automatic course
    completion when all lessons are finished.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.enrollments"
    verbose_name = "Enrollment Management"

    def ready(self):
        """Initialize Django signals when the app is ready."""
        import apps.enrollments.signals  # noqa: F401
