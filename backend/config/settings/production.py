"""
Production settings for the WSS Backend project.

This file contains Django settings specifically configured for production environment.
It typically includes:
- Database configuration for production
- Security settings (DEBUG=False, ALLOWED_HOSTS, etc.)
- Static/media files configuration
- Logging configuration
- Cache settings
- Email backend configuration
- Third-party service integrations

This file should import from base.py and override/add production-specific settings.
Environment variables should be used for sensitive data like database credentials,
secret keys, and API tokens.

Usage:
  Set DJANGO_SETTINGS_MODULE=config.settings.production in production environment
"""


from .base import *

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False

# Hosts específicos em produção
ALLOWED_HOSTS = env.list('ALLOWED_HOSTS')


# Security Settings
# https://docs.djangoproject.com/en/5.2/ref/settings/#security

SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SECURE_HSTS_SECONDS = 31536000  # 1 ano
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True


# Email Configuration for Production
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = env('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = env.int('EMAIL_PORT', default=587)
EMAIL_USE_TLS = env.bool('EMAIL_USE_TLS', default=True)
EMAIL_HOST_USER = env('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = env('DEFAULT_FROM_EMAIL', default='noreply@wss-backend.com')


# CORS - Specific origins only in production
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = env.list('CORS_ALLOWED_ORIGINS')


# Static files with WhiteNoise (opcional, se não usar CDN)
# MIDDLEWARE.insert(1, 'whitenoise.middleware.WhiteNoiseMiddleware')
# STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'


# Logging Configuration for Production
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'django.log',
            'maxBytes': 1024 * 1024 * 15,  # 15MB
            'backupCount': 10,
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'django.db.backends': {
            'handlers': ['file'],
            'level': 'WARNING',  # Apenas warnings em produção
            'propagate': False,
        },
    },
}


# Create logs directory if it doesn't exist
import os
os.makedirs(BASE_DIR / 'logs', exist_ok=True)