# WSS Backend — LMS API (NousFlow)

Django 5.2 + DRF platform for online course management with video content, certificates, and Stripe payments.

## Project Structure

```
backend/
├── apps/
│   ├── core/           # Shared base: TimeStampedModel (inherited by ALL models), health check
│   ├── users/          # Auth & profiles (JWT + Google OAuth/OIDC); OAuth logic in services/
│   ├── courses/        # Courses, Modules, Lessons
│   ├── videos/         # Video content + MIME validation (validators.py)
│   ├── enrollments/    # User-course relationships + completion signals
│   ├── certificates/   # PDF generation on completion (tasks.py=Celery, utils.py)
│   └── payments/       # Stripe Payment Intent + webhooks (services.py=StripeService)
├── config/
│   ├── settings/       # base.py, development.py, production.py
│   ├── celery.py
│   └── urls.py
└── manage.py
```

**Where to look per app (for review/navigation):** every app has
`models.py serializers.py views.py permissions.py urls.py admin.py factories.py tests/`.
App-specific files: `filters.py` (courses, videos, enrollments) ·
`signals.py` (users, enrollments, certificates) · `throttles.py` (users, payments) ·
`services.py` (payments) / `services/` (users) · `validators.py` (videos) ·
`tasks.py` (certificates).

## Status

**Sprint 11 complete. 2026-06 audit remediation fully closed (2026-07-08): all 81 findings**
**resolved (Blocking 18/18, Major 42/42, Minor 36/36), plus 2 follow-up findings surfaced during**
**the work (#220, #223) and a follow-up of those (#237) — zero open issues from that audit. Full**
**history archived at `.claude/context/tasks/archive/audit-2026-06/`. Sprint 12 paused (see**
**`.claude/context/tasks/archive/sprint-12.md`). Production live at https://api.nousflow.com.br**

- Context records 596 tests passing, ~98% coverage after the audit remediation; CI (GitHub Actions) gates merges with a lint + migration-drift check (flake8/black/isort) and the pytest suite on PostgreSQL + Redis, coverage enforced ≥80%
- All features implemented: auth (JWT + Google OAuth), courses/modules/lessons, videos, enrollments, certificates, payments
- Celery active (certificate PDF generation)
- Docker Compose on VPS DigitalOcean (NYC1), 1.9GB RAM, 48GB disk
- Server optimized (2026-05-26): bot blocking, memory limits, swap, log rotation
- Fresh documentation/codebase audit on 2026-07-11 found operational hygiene risks still present in repo state; tracked summaries live in `README.md`, `.claude/context/architecture.md`, `.claude/context/tech-stack.md`, `.claude/context/current-sprint.md`, and `.claude/context/tasks/backlog.md` (`INFRA-MELHORIAS.md` may exist locally as ignored detailed context)

## Common Commands

```bash
# Dev
source venv/bin/activate
python3 manage.py runserver

# Celery
celery -A config worker -l info
celery -A config beat -l info

# Tests
pytest
pytest apps/users/
pytest --cov=apps --cov-report=html

# Code quality
flake8 apps/ && black apps/ && isort apps/

# Django
python3 manage.py makemigrations && python3 manage.py migrate
python3 manage.py shell_plus
```

## Critical Rules

**Code Style:** PEP8, 88-char lines (Black), Google-style docstrings, type hints on all signatures, no hardcoded secrets.

**Django Patterns:**
- Models → always inherit `TimeStampedModel`
- Views → `ModelViewSet` for CRUD, `APIView` for custom logic
- Permissions → composition over inheritance
- Signals → keep lightweight; delegate heavy ops to Celery

**Testing:** TDD required (RED → GREEN → REFACTOR). Tests must pass before any commit. Minimum 80% coverage. Use factory-boy for test data.

**Git:** Conventional commits (`feat:`, `fix:`, `refactor:`, `test:`, `docs:`). Always ask before committing. Never push directly.

## Safety & Collaboration

**Always ask before:** modifying files, running terminal commands, creating migrations, installing packages, deleting code.

**Never:** commit secrets or `.env`, skip tests, push to remote, run `sudo`.

## Context Files

- `.claude/rules/` — coding conventions (code-style, django-patterns, security, testing, api-conventions)
- `.claude/agents/code-reviewer.md` — layer-by-layer code review sub-agent
- `.claude/context/` — architecture.md, tech-stack.md, current-sprint.md
- `.claude/context/tasks/` — backlog.md (future/unscheduled work); `archive/` holds completed/paused
  sprints (incl. sprint-12.md) + server-optimization-2026-05-26.md +
  `audit-2026-06/` (the full 2026-06 audit: executive summary, 8 layer remediation playbooks,
  execution logs, and every per-issue slice doc under `audit-2026-06/slices/`)
