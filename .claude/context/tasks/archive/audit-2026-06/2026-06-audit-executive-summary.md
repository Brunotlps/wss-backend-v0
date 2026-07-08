# Backend Audit — Executive Summary (2026-06)

**Scope:** full app-by-app audit of the WSS/NousFlow backend (Django 5.2 + DRF), one app at a
time, layer by layer (models → serializers → views → permissions → services/signals/tasks →
tests), via the `code-reviewer` sub-agent. Each app was reviewed whole (not a diff) and run
through `flake8`, `pytest`, coverage, `black`, and `isort`.

**Dates:** 2026-06-12 → 2026-06-13.
**Result:** **81 issues** filed (`#12`–`#92`), tracked on GitHub with `app:*` + `severity:*`
labels. The 16 Blocking findings are grouped by `theme:*` labels under the
**"Blocking Remediation"** milestone (#1).

---

## Severity by app

| App | Issues | Blocking | Major | Minor | Tests | Notable coverage gap |
|---|---:|:---:|:---:|:---:|---|---|
| payments | 16 | 1 | 6 | 9 | 41 pass | webhook signature path always mocked |
| enrollments | 11 | 3 | 5 | 3* | 61 pass | `serializers.py` 72% (validation branches) |
| users | 15 | 4 | 8 | 3 | 86 pass | `permissions.py` 64%, OAuth exchange 81% |
| videos | 10 | 3 | 4 | 3 | 62 pass | — (96%) |
| courses | 9 | 0 | 6 | 3 | 56 pass | `filter_is_free` untested |
| certificates | 13 | 5 | 5 | 3 | 32 pass | **`utils.py` 24%, no task/utils tests** |
| core | 7 | 0 | 3 | 3 +1 infra | 2 pass | `TimeStampedModel` untested (100% is import-time only) |
| **Total** | **81** | **16** | **37** | **28** | | |

\* enrollments count includes the cross-app certificate CASCADE issue (#38).

**Overall health:** structure, ORM conventions (`TimeStampedModel`, `related_name`, `TextChoices`,
indexes), and test breadth are generally strong. The risk concentrates in **content access
control**, **privilege/PII boundaries**, **transactional/fraud integrity**, and the
**certificate (legal document) trust chain** — captured as the 5 Blocking themes below.

---

## The 16 Blocking findings, grouped by theme

### 🔴 `theme:protected-media` — public/guessable file delivery (2)
Paid/PII content bytes are served by Nginx straight off `/media/` as public, guessable URLs, so
the API-layer permission checks protect only JSON metadata, not the files.
- **#54** videos — video files at public `/media/videos/...` URLs; `IsEnrolled` bypassable.
- **#74** certificates — PDFs at `/media/certificates/<code>.pdf`; PII (name/course/date) leak.
- **Shared root cause:** Nginx serves `/media/` public (no `internal`/signed URL) — infra half
  lives in #54 (+ `app:infra`). **Fix once, benefits both:** protected delivery
  (X-Accel-Redirect / pre-signed URLs), stop exposing file URLs in serializers, non-guessable
  storage paths.

### 🔴 `theme:access-control` — enrollment/content gating bypass (2)
- **#55** `VideoViewSet` never applies `IsEnrolled`; anonymous `GET /api/videos/` returns file URLs.
- **#56** preview check trusts `order == 1` instead of the `is_free_preview` flag (forgeable;
  leaks every course's first lesson).

### 🔴 `theme:privilege-pii` — privilege escalation & PII exposure (4)
- **#39** `is_instructor` mass-assignable at registration (anonymous → content-creator role).
- **#40** any authenticated user self-promotes to instructor via PATCH.
- **#41** anonymous `GET /api/users/` & `/api/profiles/` leak email/phone/birth_date of everyone
  (root cause: `IsOwnerOrReadOnly` has no `has_permission`; global default is
  `IsAuthenticatedOrReadOnly`).
- **#42** `POST /api/profiles/` → 500 (create endpoint with no owner).

### 🔴 `theme:transactional-integrity` — payment/enrollment integrity & fraud (4)
- **#12** double-charge: no PaymentIntent `idempotency_key`/dedup; duplicate webhook silently
  absorbed (no refund, no alert).
- **#28** duplicate enrollment POST → 500 (unhandled `IntegrityError`) instead of 409.
- **#29** cross-course lesson progress completes a course → **fraudulent certificate** without
  consuming content.
- **#30** mass-assignment on enrollment create (`completed`/`rating`/`review` writable on POST).

### 🔴 `theme:certificate-trust` — verification & legal-document trust (4)
- **#73** `is_valid` overloaded (PDF-generation flag vs revocation flag) — false "revoked" window;
  revocation re-triggers PDF and un-revokes.
- **#75** verification code uses non-crypto `random` with only 6 secret chars (enumerable).
- **#76** public verification endpoint has no throttle (brute-force + name leak); no global
  throttle defaults.
- **#77** issued certificate is mutable & non-durable (no denormalized snapshot; editing course/
  name rewrites issued docs). Pairs with #38 (on_delete CASCADE).

---

## Cross-cutting recommendations (highest leverage first)

1. **Protected media delivery** (#54 + #74) — one infra+serializer change closes two Blocking
   PII/paid-content leaks. Do first.
2. **Permission baseline** — fix `IsOwnerOrReadOnly.has_permission` and re-evaluate the global
   `DEFAULT_PERMISSION_CLASSES = IsAuthenticatedOrReadOnly` (#41), which is the root of the PII
   exposure and a recurring pattern.
3. **Global DRF throttling** — no `DEFAULT_THROTTLE_RATES` project-wide; enables enumeration
   (#76) and abuse (#87 health, users register/OAuth #49). Set anon/user defaults centrally.
4. **Mass-assignment hardening** — dedicated create serializers exposing only safe fields
   (#30, #39, #40). Same pattern across users & enrollments.
5. **Webhook & money correctness** — idempotency keys + `IntegrityError`-safe `get_or_create`
   recur in payments (#12) and certificate creation (#79).
6. **Certificate as immutable legal document** — denormalized snapshot + `PROTECT`/`SET_NULL`
   (#77/#38) + crypto code (#75) + revocation untangle (#73).

---

## Recurring lower-severity patterns (Major/Minor)

- **Redundant serializer checks returning 400 for authz failures** (should be 403, already
  enforced by permissions): courses #66.
- **N+1 from `.count()` in SerializerMethodFields**: courses #64.
- **Lint debt** (unused imports F401/F841, black, isort) in test modules of **every** app:
  #19, #36, #51, #61, #70, #83, #89 — batchable.
- **Missing type hints / Google-style docstrings**: #22, #37, #52, #63, #71, #84, #90.
- **Bulk-write cache invalidation gap** for enrollment access decision: #33 (touches videos).

---

## Tracking

- **Milestone:** "Blocking Remediation" (#1) — all 16 Blocking issues.
- **Theme labels:** `theme:protected-media`, `theme:access-control`, `theme:privilege-pii`,
  `theme:transactional-integrity`, `theme:certificate-trust`.
- **Board view:** filter `is:issue is:open label:severity:blocking` and group by `theme:*`.
- **Product decisions recorded in issues:** price soft-freeze + audited `adjust-price` (#69);
  certificate snapshot/immutability split from on_delete (#77/#38).

---

## Status & production-discovered bugs (updated 2026-06-19)

**Phase 1 — Blocking: 16/16 done, merged, and deployed to production on 2026-06-18** (PRs
#102–#109, including the #73 `is_valid` backfill follow-up). Migrations `certificates 0003/0004/0005`
applied; deploy validated. Per-slice notes in `.claude/context/tasks/archive/audit-2026-06/slices/2026-06-18-*.md`; deploy
runbook in `remediation/DEPLOY-blocking-batch-2026-06-18.md`.

**Production-discovered bugs (NOT part of the 81 audit findings).** Manual end-to-end testing after
the deploy surfaced operational/feature bugs outside the audit scope. They are tracked **separately**
in milestone **#2 "Production Stabilization"** (the audit milestone #1 stays the clean 16/16):

- **#110** — `bug(infra): celery & celery-beat run gunicorn instead of the worker` (**Blocking**,
  `app:infra`). `entrypoint.sh` hardcodes `exec gunicorn` with no `exec "$@"`, so the Celery
  `command:` is ignored → **no worker ever runs**; async tasks (certificate PDF generation, etc.)
  are enqueued to Redis and never consumed → certificates stuck "PDF em processamento". Pre-existing
  infra bug, surfaced by the full prod flow; **not** a regression of the audit fixes. Reprocessing
  the stuck certificates is in its acceptance criteria. **Priority: fix before resuming Phase 2.**
- **#111** — `bug(videos): video duration never extracted — 0:00` (Major, `app:videos`). No
  `ffprobe`/`ffmpeg` extraction exists; `duration` stays null. May depend on #110 if async.
- **#112** — `bug(videos): intermittent playback — Range/seek over signed X-Accel stream` (Major,
  `app:videos`). Traces to the protected-media/signed-URL delivery (PR #99/#101), not the Blocking
  batch; needs Nginx `/protected/` Range + signed-URL lifecycle investigation.

**Revised sequencing:** #110 (prod incident) → then Phase 2 (Major), with #111/#112 folded into the
Phase-2 work. See `remediation/00-plan.md`.
