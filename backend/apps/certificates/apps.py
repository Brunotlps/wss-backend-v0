

from django.apps import AppConfig


class CertificatesConfig(AppConfig):
    """
    Django application configuration for certificates app.
    
    Handles automatic certificate generation when enrollments are completed.
    Registers signal handlers in ready() method.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.certificates"
    verbose_name = "Certificate Management"

    def ready(self):
        """
        Initialize Django signals when app is ready.
        
        Imports signal handlers to register them with Django's
        signal dispatcher. This enables automatic certificate
        generation on enrollment completion.
        """
        import apps.certificates.signals  # noqa: F401
