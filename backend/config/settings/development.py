"""
Development settings for the WSS Backend project.

This file contains Django settings specifically configured for development environment.
It inherits from base settings and overrides/adds development-specific configurations.

Key aspects typically handled in development settings:
- Debug mode enabled for detailed error reporting
- Database configuration (usually SQLite for simplicity)
- Static files handling for development server
- Email backend configuration (console/file backend)
- Logging configuration with verbose output
- Security settings relaxed for development
- Development-specific middleware and apps
- CORS settings for frontend development
- Cache configuration (dummy cache or local memory)

This file should never be used in production environments.
"""

import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.redis import RedisIntegration
from sentry_sdk.integrations.celery import CeleryIntegration

from .base import *

# DEBUG mode enabled for development
DEBUG = True

# Allowed hosts for local development
ALLOWED_HOSTS = ['localhost', '127.0.0.1', 'backend', '0.0.0.0']


# Development-specific apps
INSTALLED_APPS += [
    'django_extensions',  # Shell Plus, RunScript, etc
    'debug_toolbar',      # Django Debug Toolbar
]


# Development-specific middleware
MIDDLEWARE += [
    'debug_toolbar.middleware.DebugToolbarMiddleware',
]


# Debug Toolbar Configuration
# https://django-debug-toolbar.readthedocs.io/en/latest/configuration.html

INTERNAL_IPS = [
    '127.0.0.1',
    'localhost',
]

# Docker support for Debug Toolbar
import socket
hostname, _, ips = socket.gethostbyname_ex(socket.gethostname())
INTERNAL_IPS += [ip[: ip.rfind(".")] + ".1" for ip in ips]


# Email backend for development (prints to console)
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'


# CORS - Allow all origins in development
CORS_ALLOW_ALL_ORIGINS = True


# Logging Configuration for Development
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'django.db.backends': {
            'handlers': ['console'],
            'level': 'DEBUG',  # Mostra todas as queries SQL
            'propagate': False,
        },
    },
}


# ==============================================
# SENTRY CONFIGURATION (Development Testing)
# ==============================================

def filter_sensitive_data(event, hint):
    """
    Filter sensitive data before sending events to Sentry.
    
    Removes authentication headers and personal data for LGPD compliance.
    
    Args:
        event (dict): Sentry event containing error information
        hint (dict): Additional context about the event
    
    Returns:
        dict: Filtered event or None to discard the event
    """
    if 'request' in event:
        headers = event['request'].get('headers', {})
        if 'Authorization' in headers:
            headers['Authorization'] = '[Filtered]'
    
    if 'request' in event and 'data' in event['request']:
        data = event['request']['data']
        if isinstance(data, dict):
            if 'password' in data:
                data['password'] = '[Filtered]'
            if 'token' in data:
                data['token'] = '[Filtered]'
    
    return event


if env('SENTRY_DSN', default=None):
    sentry_sdk.init(
        dsn=env('SENTRY_DSN'),
        integrations=[
            DjangoIntegration(),
            RedisIntegration(),
            CeleryIntegration(),
        ],
        environment='development',
        release=env('RELEASE_VERSION', default='1.0.0-dev'),
        traces_sample_rate=1.0,
        send_default_pii=False,
        before_send=filter_sensitive_data,
    )