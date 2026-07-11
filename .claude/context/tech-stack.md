# Tech Stack — WSS Backend LMS

**Last Updated:** 2026-07-11
**Source of truth:** repository code/config at this date. Historical sprint docs
may contain older numbers or settings.

## Version Matrix

| Component | Version | Evidence / notes |
|-----------|---------|------------------|
| Python | 3.12 | `backend/Dockerfile`, `.github/workflows/ci.yml` |
| Django | 5.2 | `backend/requirements.txt` |
| Django REST Framework | 3.15.2 | `backend/requirements.txt` |
| PostgreSQL | 15 prod/staging compose, 16 in CI service | `docker-compose*.yml`, CI |
| Redis | 7.x | `redis:7-alpine` in compose/CI |
| Celery | 5.4.0 | `backend/requirements.txt` |
| Stripe SDK | 8.5.0 | Payment Intent API + webhooks |
| Gunicorn | 23.0.0 | WSGI server |
| Nginx | 1.26-alpine | Reverse proxy + SSL + protected media |
| Sentry SDK | 2.0.0 | PII filtering active, traces_sample_rate=0.1 in prod |
| WhiteNoise | 6.8.2 | Static file middleware in production settings |
| pytest | 8.3.2 | CI/test suite, coverage gate ≥80% |

## Key Runtime Dependencies

Runtime dependencies are currently installed from a single
`backend/requirements.txt` file. That file includes both production runtime
packages and dev/test/formatting tools, so the production Docker image carries
extra dependencies until requirements are split.

Core runtime:

```text
Django, djangorestframework, djangorestframework-simplejwt
django-filter, django-cors-headers, django-redis
psycopg2-binary, redis, celery
stripe, sentry-sdk, google-auth, google-auth-oauthlib
python-magic, reportlab, pillow, gunicorn
drf-spectacular, whitenoise
```

Dev/test tools currently in the same requirements file:

```text
pytest, pytest-django, pytest-cov, coverage, factory-boy
black, isort, flake8, django-extensions, django-debug-toolbar
```

## REST Framework Config — Real Defaults

Defined in `backend/config/settings/base.py`.

```python
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticatedOrReadOnly",
    ),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),
    "DEFAULT_THROTTLE_RATES": {
        "anon": "100/hour",
        "user": "1000/hour",
        "login": "5/hour",
        "register": "5/day",
        "oauth": "20/hour",
        "oauth-exchange": "20/hour",
        "verify": "20/min",
        "health": "120/min",
        "video_stream": "2000/hour",
    },
    "NUM_PROXIES": 1,
}
```

## JWT Config — Real Defaults

```python
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "ALGORITHM": "HS256",
    "AUTH_HEADER_TYPES": ("Bearer",),
}
```

Both lifetimes are configurable via `JWT_ACCESS_TOKEN_LIFETIME` and
`JWT_REFRESH_TOKEN_LIFETIME`.

## API Documentation

Configured in `backend/config/urls.py`:

- Schema: `/api/schema/`
- Swagger UI: `/api/docs/`
- ReDoc: `/api/redoc/`

Older references to `/api/schema/swagger-ui/` are stale.

## File Storage

- **Local/dev/prod today:** Django filesystem storage backed by Docker volumes.
- **Protected videos:** local `media_volume`, served only through Nginx
  `internal` locations after Django permission checks / signed stream URLs.
- **Protected certificate PDFs:** direct authenticated Django `FileResponse`;
  direct `/media/certificates/` access is blocked in production Nginx.
- **Future:** Cloudflare R2/S3-compatible storage when disk/bandwidth or upload
  UX demands it. See `.claude/context/tasks/backlog.md`.

## Production Infrastructure

| Component | Config |
|-----------|--------|
| VPS | DigitalOcean NYC1, Ubuntu 24.04, 1.9GB RAM, 48GB disk |
| Stack | Docker Compose: backend, nginx, postgres, redis, celery, celery-beat profile |
| Database | PostgreSQL 15 container, `postgres_data` volume |
| Cache/broker | Redis 7 container |
| Backend | Gunicorn, `GUNICORN_WORKERS` default 3, timeout default 120s |
| Static/media | `static_volume`, `media_volume` |
| SSL | Let's Encrypt certs bind-mounted into Nginx |
| Main host | `api.nousflow.com.br` |
| Upload host | `upload.nousflow.com.br` DNS-only, bypasses Cloudflare upload limit |
| Backup | Offsite Backblaze B2 described in context; scripts currently not versioned |
| Monitoring | UptimeRobot → `/api/health/`; readiness endpoint also exists |

## Environment Variables

Examples are versioned at `.env.example` and `.env.staging.example`; real `.env`
files are intentionally ignored.

Required/important groups:

```bash
DJANGO_SETTINGS_MODULE
SECRET_KEY
DEBUG
ALLOWED_HOSTS
DATABASE_URL
POSTGRES_DB
POSTGRES_USER
POSTGRES_PASSWORD
REDIS_URL
CELERY_BROKER_URL
CELERY_RESULT_BACKEND
CORS_ALLOWED_ORIGINS
STRIPE_SECRET_KEY
STRIPE_WEBHOOK_SECRET
GOOGLE_OAUTH_CLIENT_ID
GOOGLE_OAUTH_CLIENT_SECRET
GOOGLE_OAUTH_REDIRECT_URI
FRONTEND_URL
SENTRY_DSN
ENVIRONMENT
RELEASE_VERSION
```

`production.py` fails fast if Stripe or Google OAuth backend credentials are
empty.

## Known Stack / Infra Hygiene Risks

These are summarized here and in `tasks/backlog.md`. `INFRA-MELHORIAS.md` may
exist locally as a more detailed ignored audit file.

1. Backup scripts and cron schedule are documented but not versioned.
2. `entrypoint.sh` interpolates superuser credentials into inline Python.
3. Port 80 production host still serves/proxies content instead of redirecting
   all recognized HTTP traffic to HTTPS.
4. Host firewall / cloud firewall state is not codified in the repository.
5. Redis `maxmemory`/`allkeys-lru` is documented as runtime config, not persisted
   in Compose.
6. Dockerfile is single-stage, runs as root, and installs dev/test dependencies.
7. `docker-compose.yml` still uses obsolete `version: '3.8'`.
8. There is no CD/deploy script; deploy is manual and has known recreate
   gotchas.
9. `celery-beat` is provisioned without a current `beat_schedule`.
10. Staging Nginx does not mirror production protected-media rules and has a
    port/config mismatch for 8443.
11. No `.dockerignore` is present for the `backend/` build context.
