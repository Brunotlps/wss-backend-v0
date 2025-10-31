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