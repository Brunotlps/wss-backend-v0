# WSS — Web School System

> An API-first online course platform built with Django and Django REST Framework.

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-5.2-092E20?style=flat&logo=django&logoColor=white)](https://www.djangoproject.com/)
[![DRF](https://img.shields.io/badge/DRF-3.15.2-A30000?style=flat&logo=django&logoColor=white)](https://www.django-rest-framework.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-336791?style=flat&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Redis](https://img.shields.io/badge/Redis-7-DC382D?style=flat&logo=redis&logoColor=white)](https://redis.io/)
[![Celery](https://img.shields.io/badge/Celery-5.4-37814A?style=flat&logo=celery&logoColor=white)](https://docs.celeryq.dev/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=flat&logo=docker&logoColor=white)](https://www.docker.com/)
[![Status](https://img.shields.io/badge/Status-Production-brightgreen?style=flat)]()

---

## About the Project

**WSS (Web School System)** is an API-first platform for managing and selling
online courses, with built-in support for video content, enrollments,
certificates, and payments.

The project started from a real need: a couple of friends — *Dupla de Milheiros*
— who teach personal finance and travel hacking with airline miles, wanted a
platform to host their first paid course. What began as a single-tenant solution
evolved into an independent, multi-instructor platform aimed at small course
creators who want a focused, community-driven alternative to mainstream course
marketplaces.

The long-term vision is to build **a learning platform centered on community and
learning enhancement** — not just a video catalog, but a space where students and
instructors interact, collaborate, and grow together.

---

## Current Status

✅ **Production live** at [api.nousflow.com.br](https://api.nousflow.com.br).

The backend currently implements the core LMS flow end to end:

- User registration, JWT authentication, profiles, and Google OAuth 2.0/OIDC.
- Course catalog with categories, modules, lessons, draft/published visibility,
  instructor ownership, and pricing.
- Video upload with real MIME validation, protected media delivery, short-lived
  signed stream URLs, and asynchronous duration extraction with Celery.
- Enrollments, lesson progress tracking, course completion, ratings, and reviews.
- Certificate issuance with immutable snapshots, unique validation codes, PDF
  generation via Celery/ReportLab, authenticated PDF download, and public
  validation by code.
- Stripe Payment Intent checkout with webhook signature verification,
  idempotent payment lifecycle transitions, paid-course enrollment gating, and
  refund-based access revocation.
- Production Docker Compose stack with PostgreSQL, Redis, Gunicorn, Nginx,
  Celery worker, optional Celery Beat, local media/static volumes, SSL, health
  checks, and offsite backup documented in project context.
- CI with linting, formatting checks, migration drift detection, Django system
  check, PostgreSQL/Redis services, and pytest coverage gate of 80%.

Context notes currently record 596 passing tests and ~98% coverage after the
2026-06 audit remediation. CI enforces the ≥80% threshold; run the suite locally
to confirm the exact number on the current branch.

---

## Tech Stack

**Backend & API**

- Python 3.12
- Django 5.2
- Django REST Framework 3.15.2
- `djangorestframework-simplejwt`
- `drf-spectacular`
- `django-filter`
- `django-cors-headers`

**Data & Async**

- PostgreSQL 15 in Docker Compose
- Redis 7 for Django cache and Celery broker/result backend
- Celery 5.4
- `django-redis`

**Payments, Auth & Integrations**

- Stripe Payment Intent API and webhooks
- Google OAuth 2.0 + OIDC (`google-auth`, `google-auth-oauthlib`)
- Sentry SDK with PII filtering

**Files & Media**

- Local filesystem storage via Docker volumes
- Nginx `X-Accel-Redirect` for protected video bytes
- `python-magic` / `libmagic` for MIME validation
- `ffmpeg` / `ffprobe` for video duration extraction
- ReportLab for certificate PDF generation
- Pillow for images

**Quality**

- `pytest`, `pytest-django`, `pytest-cov`
- `factory-boy`
- `black`, `isort`, `flake8`

**Infrastructure**

- Docker Compose
- Gunicorn
- Nginx
- Let's Encrypt certificates mounted into the Nginx container
- DigitalOcean VPS in the current production setup

---

## Architecture Overview

The project follows a modular Django app structure. Each domain area owns its
models, serializers, views, permissions, tests, factories, and admin
configuration.

```text
backend/
├── apps/
│   ├── core/             # Shared TimeStampedModel, health/readiness checks
│   ├── users/            # Custom user, profiles, JWT, Google OAuth/OIDC
│   ├── courses/          # Categories, courses, modules
│   ├── videos/           # Video files, lessons, streaming, validation
│   ├── enrollments/      # Enrollments, lesson progress, completion signals
│   ├── certificates/     # Certificate snapshots, PDF generation, validation
│   └── payments/         # Stripe PaymentIntent service and webhooks
├── config/
│   ├── settings/
│   │   ├── base.py
│   │   ├── development.py
│   │   └── production.py
│   ├── celery.py
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
├── templates/
│   └── admin/videos/video/change_form.html
├── conftest.py
├── Dockerfile
├── entrypoint.sh
├── manage.py
├── pyproject.toml
└── requirements.txt
```

Key design rules used in the codebase:

- Models inherit from `TimeStampedModel` for consistent `created_at` and
  `updated_at` fields.
- Views use `ModelViewSet` for standard CRUD and `APIView` for custom
  non-resource flows.
- Complex integration logic is kept in service classes, especially
  `StripeService`.
- Signals stay lightweight and enqueue heavy work to Celery.
- Permissions are explicit and role-aware: staff, instructors, owners,
  enrolled students, and anonymous preview users have distinct paths.
- Protected media is never exposed directly through public video/certificate
  media URLs.

---

## Main API Surface

Documentation endpoints:

- OpenAPI schema: `GET /api/schema/`
- Swagger UI: `GET /api/docs/`
- ReDoc: `GET /api/redoc/`

Operational endpoints:

- Liveness: `GET /api/health/`
- Readiness: `GET /api/health/ready/`

Domain endpoints:

- Auth/users: `/api/auth/*`, `/api/users/`, `/api/users/me/`, `/api/profiles/`
- Courses: `/api/categories/`, `/api/courses/`, `/api/modules/`
- Videos/lessons: `/api/videos/`, `/api/lessons/`
- Enrollments/progress: `/api/enrollments/`, `/api/progress/`
- Certificates: `/api/certificates/`
- Payments: `/api/payments/`, `/api/webhooks/stripe/`

---

## Technical Highlights

### Real MIME validation on uploads

Video uploads are validated by reading their actual content with
`python-magic`, not just by trusting file extensions.

### Protected video streaming

The frontend requests a short-lived signed stream URL after enrollment access is
checked. The browser can then use a plain `<video src>` URL with native Range
support, while Nginx serves the bytes through an internal location.

### Cached enrollment permission

The `IsEnrolled` check is cached for 15 minutes and invalidated on enrollment
save/delete. This reduces repeated database hits on protected content access.

### Stripe lifecycle hardening

PaymentIntent creation is idempotent per user/course. Webhooks use signature
verification, database transactions, row locking, explicit lifecycle
transitions, duplicate-delivery handling, and non-retryable event classification.

### Durable certificates

Issued certificates store snapshots of the student name, course title,
instructor name, and completion date so later edits/deletions do not mutate the
legal document.

### LGPD-aware monitoring

Sentry is configured with `send_default_pii=False` and a `before_send` filter for
sensitive fields such as authorization headers, passwords, and tokens.

---

## Known Operational Risks

These are known risks or hygiene gaps observed from the repository state. They
are documented so they can be prioritized deliberately. The project context
under `.claude/context/` keeps the tracked backlog; `INFRA-MELHORIAS.md`, when
present locally, contains a more detailed non-versioned operational audit.

- `backend/entrypoint.sh` interpolates superuser environment values into an
  inline Python script. A password containing quotes can break startup; a
  malicious value could execute Python code inside the container. Replace with
  Django's native `createsuperuser --noinput`.
- Redis memory policy is documented as runtime configuration, but not persisted
  in Compose. A Redis container recreate can lose the `maxmemory` limit unless
  the command is encoded in `docker-compose.yml`.
- The production HTTP server block for `api.nousflow.com.br` still serves/proxies
  content on port 80 instead of only redirecting to HTTPS. Cloudflare mitigates
  the main hostname, but direct/IP and DNS-only paths should be hardened.
- The Docker image is single-stage, runs as root, and installs dev/test tooling
  in the production image.
- `celery-beat` is provisioned in production profiles, but no periodic schedule
  is currently defined in code.
- The staging Nginx configuration does not mirror production's protected media
  rules, and the Compose file maps 8443 even though the current staging Nginx
  config only defines an HTTP server block.
- A `.dockerignore` file is absent for the `backend/` build context, so local
  artifacts under that directory can be sent to Docker builds unless excluded by
  external workflow discipline.

---

## Getting Started

### Prerequisites

- Docker and Docker Compose
- Git

### Running locally with Docker Compose

```bash
git clone https://github.com/Brunotlps/wss-backend-v0.git
cd wss-backend-v0

cp .env.example .env
# Edit .env with local values.

docker compose up --build
```

The backend entrypoint waits for PostgreSQL, runs migrations, collects static
files, optionally creates a superuser from `DJANGO_SUPERUSER_*`, and starts
Gunicorn.

The API will be available at:

- API: `http://localhost:8000/`
- Swagger UI: `http://localhost:8000/api/docs/`
- ReDoc: `http://localhost:8000/api/redoc/`

### Running tests

```bash
cd backend
pytest
pytest apps/users/
pytest --cov=apps --cov-report=html
```

The default pytest settings use `config.settings.development`. CI runs the test
suite against PostgreSQL and Redis services for closer production parity.

### Code quality

```bash
cd backend
flake8 apps/ config/
black --check apps/ config/
isort --check-only apps/ config/
python manage.py makemigrations --check --dry-run
```

---

## Roadmap

### Short term

- PDF lesson viewer and lesson supplementary materials.
- Instructor dashboard with analytics and student progress.
- Stripe live validation flow when product priorities return to payments.
- Infrastructure hardening items listed in `INFRA-MELHORIAS.md`.

### Medium term

- Direct object-storage upload with presigned URLs (Cloudflare R2/S3-compatible
  storage), preserving validation and protected playback decisions.
- Course community tab with discussions and Q&A.
- Better deployment automation (`deploy.sh` or controlled CD).

### Long term

- Live classes.
- Richer instructor content-management workflows.
- Multi-instructor platform with a strong focus on community and learning
  outcomes rather than catalog volume.

---

## About the Author

Built and maintained by **Bruno Teixeira Lopes** — a backend developer from
Brazil focused on building real, maintainable systems. WSS is the project where
I bring together backend engineering, architecture, async processing, security,
observability, and deployment practice.

[![GitHub](https://img.shields.io/badge/GitHub-100000?style=flat&logo=github&logoColor=white)](https://github.com/Brunotlps)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-0A66C2?style=flat&logo=linkedin&logoColor=white)](https://linkedin.com/in/brunotlps)
[![Email](https://img.shields.io/badge/Email-D14836?style=flat&logo=gmail&logoColor=white)](mailto:brunoteixlps@gmail.com)

---

## License

This project is licensed under the [MIT License](LICENSE).
