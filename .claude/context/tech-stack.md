# Tech Stack — WSS Backend LMS

**Last Updated:** 2026-05-26

## Version Matrix

| Component | Version | Notes |
|-----------|---------|-------|
| Python | 3.12 | |
| Django | 5.2 | |
| Django REST Framework | 3.15.2 | |
| PostgreSQL | 15 | Docker container in prod |
| Redis | 7.x | Cache + Celery broker |
| Celery | 5.4 | Active — PDF generation |
| Stripe | 8.5+ | Payment Intent API, webhooks |
| Gunicorn | 23.0 | WSGI server |
| Nginx | 1.26 | Reverse proxy + SSL + bot blocking (default_server 444) |
| Sentry SDK | 2.0 | PII filtering active, traces_sample_rate=0.1 |
| WhiteNoise | 6.8.2 | Static file serving in production |
| pytest | 8.x | 269 tests, 96.21% coverage |

---

## Key Dependencies

**Production (`requirements.txt`):**
```
Django, djangorestframework, djangorestframework-simplejwt
django-filter, django-cors-headers, django-redis
psycopg2-binary, redis, celery
stripe, python-decouple, sentry-sdk
python-magic, reportlab, pillow, gunicorn
```

**Dev extras:** pytest, pytest-django, pytest-cov, pytest-mock, factory-boy, black, isort, flake8, pylint, django-extensions

---

## REST Framework Config

```python
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': ['rest_framework_simplejwt.authentication.JWTAuthentication'],
    'DEFAULT_PERMISSION_CLASSES': ['rest_framework.permissions.IsAuthenticated'],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_THROTTLE_RATES': {'anon': '100/hour', 'user': '1000/hour'},
}
```

## JWT Config

```python
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
}
```

## File Storage

- **Dev:** `FileSystemStorage` — `backend/media/`
- **Prod:** Local Docker volume `wss-backend-v0_media_volume` (backed up to Backblaze B2)
- **Future:** Migrate to Cloudflare R2 or AWS S3 when disk ~70%

## Production Infrastructure

| Component | Config |
|-----------|--------|
| VPS | DigitalOcean NYC1, 1.9GB RAM, 48GB disk |
| Swap | 1GB (`/swapfile`, persistent via `/etc/fstab`) |
| Docker log rotation | `daemon.json` — 10MB × 3 per container |
| Backend memory limit | 1GB (512MB reserved) |
| Celery worker limit | 384MB (128MB reserved) |
| Celery beat limit | 128MB (64MB reserved) |
| Redis maxmemory | 64MB, allkeys-lru (runtime config) |
| SSL | Let's Encrypt via Certbot (auto-renew) |
| Nginx bot blocking | Default server returns 444 for unrecognized Host headers |

## Environment Variables (`.env`)

```bash
SECRET_KEY, DEBUG, ALLOWED_HOSTS
DATABASE_NAME, DATABASE_USER, DATABASE_PASSWORD, DATABASE_HOST, DATABASE_PORT
REDIS_URL
STRIPE_PUBLIC_KEY, STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET
SENTRY_DSN, ENVIRONMENT
```
