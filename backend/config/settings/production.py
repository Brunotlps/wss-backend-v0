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
import os
import sentry_sdk

from .base import *
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.redis import RedisIntegration
from sentry_sdk.integrations.celery import CeleryIntegration


DEBUG = False

ALLOWED_HOSTS = env.list('ALLOWED_HOSTS')

# ==============================================
# SECURITY SETTINGS
# ==============================================
# https://docs.djangoproject.com/en/5.2/ref/settings/#security

# Force HTTPS for all requests
SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')  # Trust Nginx/Load Balancer

# Secure cookies (only sent over HTTPS)
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True  # Prevent JavaScript access to session cookie
CSRF_COOKIE_HTTPONLY = True     # Prevent JavaScript access to CSRF token

# Security headers
SECURE_BROWSER_XSS_FILTER = True        # Enable browser XSS protection
SECURE_CONTENT_TYPE_NOSNIFF = True      # Prevent MIME-sniffing
X_FRAME_OPTIONS = 'DENY'                 # Prevent clickjacking (no iframes)

# HSTS (HTTP Strict Transport Security) - Force HTTPS for 1 year
SECURE_HSTS_SECONDS = 31536000           # 1 year in seconds
SECURE_HSTS_INCLUDE_SUBDOMAINS = True    # Apply to all subdomains
SECURE_HSTS_PRELOAD = True               # Allow browser HSTS preload list

# ==============================================
# EMAIL CONFIGURATION
# ==============================================
# Production uses SMTP backend (e.g., Gmail, SendGrid, AWS SES)

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = env('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = env.int('EMAIL_PORT', default=587)
EMAIL_USE_TLS = env.bool('EMAIL_USE_TLS', default=True)
EMAIL_HOST_USER = env('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = env('DEFAULT_FROM_EMAIL', default='noreply@wss-backend.com')
SERVER_EMAIL = DEFAULT_FROM_EMAIL  # Email for error notifications

# ==============================================
# ADMIN CONFIGURATION
# ==============================================
# Admins receive error emails (500 errors)

ADMINS = [
    ('Admin', env('ADMIN_EMAIL', default='admin@example.com')),
]
MANAGERS = ADMINS  # Managers receive broken link notifications (404 errors)

# ==============================================
# CORS CONFIGURATION
# ==============================================
# CORS_ALLOW_ALL_ORIGINS is already False by default
# CORS_ALLOWED_ORIGINS is already configured in base.py from .env
# No need to redefine here

# ==============================================
# STATIC FILES (CSS, JavaScript, Images)
# ==============================================
# WhiteNoise serves static files efficiently in production without nginx

MIDDLEWARE.insert(1, 'whitenoise.middleware.WhiteNoiseMiddleware')
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# ==============================================
# MEDIA FILES (User uploads: videos, certificates)
# ==============================================
# Currently using filesystem storage
# For scalability, migrate to AWS S3 when reaching >50GB or >10k users/month

MEDIA_URL = env('MEDIA_URL', default='/media/')
MEDIA_ROOT = env('MEDIA_ROOT', default=str(BASE_DIR / 'media'))

# AWS S3 Configuration (currently disabled - enable with USE_S3=True in .env)
# Uncomment and configure when ready to migrate:
#
# USE_S3 = env.bool('USE_S3', default=False)
#
# if USE_S3:
#     DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
#     AWS_STORAGE_BUCKET_NAME = env('AWS_STORAGE_BUCKET_NAME')
#     AWS_S3_REGION_NAME = env('AWS_S3_REGION_NAME', default='us-east-1')
#     AWS_ACCESS_KEY_ID = env('AWS_ACCESS_KEY_ID')
#     AWS_SECRET_ACCESS_KEY = env('AWS_SECRET_ACCESS_KEY')
#     AWS_S3_CUSTOM_DOMAIN = f'{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com'
#     AWS_DEFAULT_ACL = 'public-read'
#     AWS_QUERYSTRING_AUTH = False
#     AWS_S3_OBJECT_PARAMETERS = {
#         'CacheControl': 'max-age=86400',  # 24 hours cache
#     }
#
# Cost estimate (2026): ~$12-15/month for 100GB storage + 100k requests

# Logging Configuration
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
            'level': 'WARNING',  
            'propagate': False,
        },
    },
}


# Create logs directory if it doesn't exist
os.makedirs(BASE_DIR / 'logs', exist_ok=True)


# ==============================================
# SENTRY CONFIGURATION (Error Tracking)
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


# Inicializar Sentry apenas se DSN estiver configurado
if env('SENTRY_DSN', default=None):
    sentry_sdk.init(
        dsn=env('SENTRY_DSN'),
        integrations=[
            DjangoIntegration(),
            RedisIntegration(),
            CeleryIntegration(),
        ],
        environment=env('ENVIRONMENT', default='production'),
        release=env('RELEASE_VERSION', default='1.0.0'),
        traces_sample_rate=0.1,
        send_default_pii=False,
        before_send=filter_sensitive_data,
    )