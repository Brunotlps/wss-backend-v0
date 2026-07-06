# Layer: Services / Signals / Celery Tasks

**Owns:** #12 (double-charge, Blocking), #29† (signal defensive count), #73† (task PDF guard),
#13, #14, #16, #18, #27, #23, #43, #44, #47, #78, #79, #80.
**Themes:** `transactional-integrity`, `certificate-trust`.

> ✅ **PROD REALITY (updated 2026-06-25): the Celery worker IS running in production.** #110 was
> fixed (PR #113) and validated — the `celery`/`celery-beat` services now run their real commands
> and consume from Redis (`.delay()` paths are live; the 4 stuck certs drained). Tests still use
> `CELERY_TASK_ALWAYS_EAGER=True` in development. Historical context: `entrypoint.sh` had ignored
> the container `command` so both services ran gunicorn. See memory `infra_celery_entrypoint_bug`.

## Canonical patterns (`.claude/rules/django-patterns.md`, `security.md`, `testing.md`)

- Signals stay lightweight; heavy work → Celery. Tasks fetch by **id**, are **idempotent**,
  handle `DoesNotExist`, and separate "retry" from "final failure".
- Writes that can race use `get_or_create` / catch `IntegrityError`.
- Money uses `Decimal`. Webhooks verify signature and are idempotent.

## Payments

### Double-charge — #12 (Blocking) ✅ FIXED (PR #106, 2026-06-18)
Deterministic idempotency + dedup of pending intents.
```python
intent = stripe.PaymentIntent.create(
    amount=int(course.price * 100), currency="brl",
    metadata={"user_id": user.id, "course_id": course.id},
    idempotency_key=f"pi:{user.id}:{course.id}",
)
```
On a duplicate `succeeded` webhook for an already-enrolled user → log ERROR/alert, consider
auto-refund.

### Webhook robustness — #13/#14/#18/#27 ✅ FIXED (PR #142, 2026-06-26), #16 ✅ FIXED (PRs #144/#146, 2026-06-26), #23 ✅ FIXED (PR #148, 2026-06-26)
- #13: race-safe idempotency — `Payment.objects.get_or_create(stripe_payment_intent_id=...)` or
  catch `IntegrityError` (don't 500).
- #14: `amount = Decimal(payment_intent["amount"]) / 100` (no float).
- #16: persist `FAILED`/`REFUNDED` events (today only success is recorded); fix stale docstrings.
- #18: distinguish retryable (transient DB → 500) from non-retryable (malformed/orphaned event →
  log ERROR, return **200** so Stripe stops redelivering for days).
- #27: defense-in-depth — warn/refuse when paid amount/currency diverges from `course.price`.
- #23: fail-fast on empty `STRIPE_*` / `GOOGLE_OAUTH_*` keys in `settings/production.py`.

## Users / OAuth (services/google_oauth.py) — #43/#44/#47 ✅ FIXED (PRs #152/#154/#157, 2026-06-27~29)
- #43: stop returning JWTs in the URL fragment — issue a single-use code (Redis, short TTL) +
  `POST /api/auth/google/exchange/` returning the pair in the body (or httpOnly refresh cookie).
- #44: `request.session.pop("google_oauth_state"/"nonce")` after validation (single-use).
- #47: keep the `email_verified` gate; add a security-log entry when linking to an existing local
  account with a usable password; consider extra confirmation.

## Enrollments / Certificates signals & tasks — ✅ FIXED (PR #105 for #29, PR #149 for #79/#80/#73/#78, 2026-06-18~27)
- #29† defensive: completion signal counts only `lesson_progress` where
  `lesson__course == enrollment.course` (validation primary fix is in `03`).
- #79: certificate creation signal → `Certificate.objects.get_or_create(enrollment=...)`
  (race-safe; no raw IntegrityError to the caller).
- #80: move code generation (and ideally row creation) into the task; keep the signal light.
- #73† task guard: idempotency keyed on **PDF presence** (`if certificate.pdf_file: return`), not
  `is_valid` (which now means revocation only — see `02`).
- #78: clean retry branch — if retries remain `raise self.retry(...)`; on final failure set
  `pdf_generation_failed_at`, capture to Sentry/log ERROR, **stop** (no double-retry). Surface
  `pdf_generation_failed_at` in admin `list_filter`.

## Done criteria
- [x] Two concurrent checkouts / duplicate webhooks never double-charge or double-record; dup is
      logged/alerted. — #12/#13.
- [x] Webhook handler returns 200 on non-retryable events; money stored as exact `Decimal`. — #18/#14.
- [x] No JWT in URL; OAuth state/nonce are single-use; linking is audit-logged. — #43/#44/#47.
- [x] Certificate creation is idempotent under concurrency; task no-ops when PDF exists; final
      failure is alerted and visible in admin. — #79/#73/#78.
- [x] Tests cover each branch (see `07`: #17 signature, #82 task/utils). — both closed.
