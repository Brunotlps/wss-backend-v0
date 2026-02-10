"""
Django AppConfig for Users application.

This module configures the Users app and ensures that signals
are properly registered when the app is ready.
"""

from django.apps import AppConfigcreate


class UsersConfig(AppConfig):
    """
    Configuration class for the Users application.
    
    Attributes:
        default_auto_field (str): Specifies the type of auto-created primary keys.
        name (str): Full Python path to the application.
        verbose_name (str): Human-readable name for the application.
    
    Methods:
        ready(): Called when Django starts. Imports signal handlers to ensure
                they are registered with Django's signal dispatcher.
    """
    
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.users'
    verbose_name = 'Users'
    
    def ready(self):
        """
        Import signal handlers when the app is ready.
        
        This method is called by Django when the application is fully loaded.
        We import signals here to ensure they are registered with Django's
        signal dispatcher and will be triggered at the appropriate times.
        
        Signals imported:
            - Profile auto-creation when User is created
        """
        import apps.users.signals  # noqa: F401
