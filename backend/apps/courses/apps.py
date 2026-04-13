from django.apps import AppConfig


class CoursesConfig(AppConfig):
    """Django application configuration for the courses app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.courses"
    verbose_name = "Course Management"
