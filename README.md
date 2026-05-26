# WSS — Web School System
 
> An API-first online course platform built with Django and Django REST Framework.
 
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-5.2-092E20?style=flat&logo=django&logoColor=white)](https://www.djangoproject.com/)
[![DRF](https://img.shields.io/badge/DRF-3.15-A30000?style=flat&logo=django&logoColor=white)](https://www.django-rest-framework.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-336791?style=flat&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Redis](https://img.shields.io/badge/Redis-DC382D?style=flat&logo=redis&logoColor=white)](https://redis.io/)
[![Celery](https://img.shields.io/badge/Celery-37814A?style=flat&logo=celery&logoColor=white)](https://docs.celeryq.dev/)
[![Docker](https://img.shields.io/badge/Docker-2496ED?style=flat&logo=docker&logoColor=white)](https://www.docker.com/)
[![Status](https://img.shields.io/badge/Status-Production-brightgreen?style=flat)]()
 
---
 
## About the Project
 
**WSS (Web School System)** is an API-first platform for managing and selling online courses, with built-in support for video content, enrollments, certificates, and payments.
 
The project started from a real need: a couple of friends — *Dupla de Milheiros* — who teach personal finance and travel hacking with airline miles, wanted a platform to host their first paid course. What began as a single-tenant solution evolved into an independent, multi-instructor platform aimed at small course creators who want a focused, community-driven alternative to mainstream course marketplaces.
 
The long-term vision is to build **a learning platform centered on community and learning enhancement** — not just a video catalog, but a space where students and instructors interact, collaborate, and grow together.
 
---
 
## Project Status
 
✅ **Production live** at [api.nousflow.com.br](https://api.nousflow.com.br) — Sprint 11 complete.
 
### What's done
 
- Core domain models and CRUD endpoints (users, courses, videos, enrollments, certificates)
- JWT authentication with `djangorestframework-simplejwt`
- Custom user model
- Settings modularized by environment (`base`, `development`, `production`)
- Production hardening: HSTS, SSL/HTTPS, secure cookies, security headers
- Video upload with real MIME validation via `python-magic` (not just file extension)
- Redis-cached `IsEnrolled` permission for performance on protected resources
- PDF certificate generation with `ReportLab` (unique certificate codes, integrated with the Django model layer)
- Background task infrastructure with Celery + Redis
- Sentry integration with LGPD-compliant PII filtering
- OpenAPI / Swagger documentation via `drf-spectacular`
- Containerized environment with Docker Compose + Nginx reverse proxy (production on DigitalOcean)
- Stripe Payment Intent integration with webhook verification
- Google OAuth 2.0 + OIDC login (Authorization Code Flow, id_token validation via JWKS)
- 311 tests passing, 96.23% coverage enforced in CI
 
### What's next
 
- 🟡 PDF lesson viewer — pending `pdf_file` field on lessons endpoint
- 🟡 Lesson supplementary materials — pending `attachments[]` field
- 🟡 Instructor dashboard — analytics and student progress
- 🟡 Course community tab — discussions and Q&A per course

 
---
 
## Tech Stack
 
**Backend & API**
- Django 5.2
- Django REST Framework 3.15
- `djangorestframework-simplejwt` (JWT auth)
- `drf-spectacular` (OpenAPI / Swagger documentation)
 
**Data**
- PostgreSQL (production)
- SQLite (local development)
 
**Async & Performance**
- Celery 5.4 (background jobs)
- Redis (Celery broker + application cache)
 
**File Handling**
- `python-magic` (MIME type validation for uploads)
- `ReportLab` (PDF certificate generation)
 
**Quality & Observability**
- `pytest`, `pytest-django`, `factory-boy` (testing)
- `flake8`, `black`, `isort`, `pylint` (code quality)
- Sentry (error monitoring with LGPD-compliant PII filtering)
 
**Auth**
- `google-auth` + `google-auth-oauthlib` (Google OAuth 2.0 + OIDC)

**Infrastructure**
- Docker + Docker Compose
- Gunicorn + Nginx (production on DigitalOcean VPS)
 
---
 
## Architecture Overview
 
The project follows a **modular Django app structure**, where each domain concept lives in its own app with clear boundaries.
 
```
backend/
├── apps/
│   ├── core/             # Shared base models (TimeStampedModel) and utilities
│   ├── users/            # Custom user model, authentication, profiles
│   ├── courses/          # Course catalog, modules, lessons
│   ├── videos/           # Video content + upload validation
│   ├── enrollments/      # User-course relationships and access control
│   ├── certificates/     # PDF certificate generation on course completion
│   └── payments/         # Stripe integration (in active development)
├── config/
│   ├── settings/
│   │   ├── base.py
│   │   ├── development.py
│   │   └── production.py
│   ├── celery.py
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
├── planning_deploy/      # Architecture and roadmap documentation
├── conftest.py
├── Dockerfile
├── entrypoint.sh
├── manage.py
├── pyproject.toml
└── requirements.txt
```
 
**Design principles applied:**
 
- **Models** inherit from a shared `TimeStampedModel` base for consistent `created_at` / `updated_at` tracking.
- **Views** use `ViewSets` for standard CRUD and `APIView` for custom logic.
- **Permissions** favor composition over inheritance, with caching where it makes sense (e.g., `IsEnrolled`).
- **Signals** are kept lightweight — heavy work is delegated to Celery tasks.
- **Settings** are split per environment, with no secrets in the codebase (all sensitive config via `.env`).
 
---
 
## Technical Highlights
 
A few decisions that go beyond the default Django tutorial:
 
### Real MIME validation on uploads
Files are validated by reading their actual content with `python-magic`, not just by trusting the file extension. This prevents users from uploading executables disguised as videos.
 
### Cached permission checks
The `IsEnrolled` permission — which runs on every request to enrollment-protected resources — is cached in Redis to avoid repeated database hits on hot paths.
 
### Asynchronous heavy work via Celery
Operations that are slow or prone to failure (like PDF generation, email sending, and future payment confirmations) run as Celery tasks instead of blocking the request cycle.
 
### LGPD-aware error monitoring
Sentry integration filters out personally identifiable information before events are sent, keeping observability without leaking user data — a requirement under Brazilian data protection law.
 
### Production-ready settings from day one
Even in active development, `production.py` enforces HSTS, SSL redirect, secure cookies, and other security headers. The intent is that "going to production" should not require a security audit at the last moment.
 
### Google OAuth 2.0 + OIDC
Login with Google uses the Authorization Code Flow entirely server-side. The backend generates a cryptographic `state` and `nonce`, validates the `id_token` signature via Google's JWKS endpoint, enforces `email_verified`, and issues its own JWT pair — the Google token never touches the frontend. Tokens are delivered via URL fragment (`#`) to prevent exposure in server logs.

### Test-Driven Development
The project follows a TDD workflow (RED → GREEN → REFACTOR) with a >80% coverage target enforced in CI. Test data is built with `factory-boy` factories instead of fragile fixtures.
 
---
 
## Getting Started
 
### Prerequisites
 
- Docker and Docker Compose
- Git
 
### Running locally
 
```bash
# Clone the repository
git clone https://github.com/Brunotlps/wss-backend-v0.git
cd wss-backend-v0
 
# Set up environment variables
cp backend/.env.example backend/.env
# Edit backend/.env with your local values
 
# Build and start the containers
docker compose up --build
 
# In another terminal, run migrations
docker compose exec backend python manage.py migrate
 
# (Optional) Create a superuser
docker compose exec backend python manage.py createsuperuser
```
 
The API will be available at `http://localhost:8000/`.
Interactive API documentation (Swagger) at `http://localhost:8000/api/schema/swagger-ui/`.
 
### Running tests
 
```bash
# All tests
docker compose exec backend pytest
 
# With coverage report
docker compose exec backend pytest --cov=apps --cov-report=html
 
# Specific app
docker compose exec backend pytest apps/enrollments/
```
 
---
 
## Roadmap
 
### Short term
- PDF lesson viewer and supplementary materials (pending backend fields)
- Instructor dashboard — analytics and student progress

### Medium term
- Private beta with *Dupla de Milheiros* as the first real instructors
- Public launch with companion ebook
 
### Long term
- **Course community tab** — discussions and Q&A tied to each course
- **Live classes** — real-time sessions with students
- **Instructor dashboard** — analytics, student progress, content management
- Multi-instructor platform with a strong focus on **community and learning outcomes**, rather than catalog volume
 
For the OAuth implementation strategy, see [`sprint-oauth.md`](./sprint-oauth.md).
 
---
 
## About the Author
 
Built and maintained by **Bruno Teixeira Lopes** — a backend developer from Brazil focused on building real, maintainable systems. WSS is the project where I bring together everything I'm learning about backend engineering: architecture, async processing, security, observability, and deploying real software to real users.
 
[![GitHub](https://img.shields.io/badge/GitHub-100000?style=flat&logo=github&logoColor=white)](https://github.com/Brunotlps)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-0A66C2?style=flat&logo=linkedin&logoColor=white)](https://linkedin.com/in/brunotlps)
[![Email](https://img.shields.io/badge/Email-D14836?style=flat&logo=gmail&logoColor=white)](mailto:brunoteixlps@gmail.com)
 
---
 
⭐ *This is an active learning and engineering project. Feedback, ideas, and questions are welcome — open an issue or reach out directly.*

---

## License

This project is licensed under the [MIT License](LICENSE).