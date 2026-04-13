from django.apps import AppConfig


class PaymentsConfig(AppConfig):
    """Django application configuration for the payments app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.payments"
    verbose_name = "Payment Processing"
