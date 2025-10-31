"""
Django Settings Module Configuration

This __init__.py file serves as the entry point for the settings package in this Django project.
It automatically imports the appropriate settings module based on the environment.

The settings are organized into separate modules:
- base.py: Contains common settings shared across all environments
- development.py: Development-specific settings (DEBUG=True, local database, etc.)
- production.py: Production-specific settings (DEBUG=False, production database, security settings)
- testing.py: Settings optimized for running tests

Environment Detection:
The DJANGO_SETTINGS_MODULE environment variable or Django's default behavior
determines which settings module is loaded. This file can contain logic to
automatically select the appropriate settings based on environment variables
or other detection methods.

Usage:
Instead of specifying the full path like 'config.settings.development',
you can use 'config.settings' and let this file handle the module selection.
"""

# Import the appropriate settings module based on environment
# This is typically handled by Django's DJANGO_SETTINGS_MODULE setting
# but can include conditional logic here if needed