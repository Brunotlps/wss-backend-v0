# Remediation Plan — by Layer

Master plan for resolving the 81 findings from the 2026-06 audit, organized **by layer**
(mirroring how the audit was run). Each `NN-*.md` playbook owns one layer: the canonical pattern
(from `.claude/rules/`), the issues it resolves, the steps, and the done criteria.

See the findings overview in [`../2026-06-audit-executive-summary.md`](../2026-06-audit-executive-summary.md).

## Layer files

| File | Layer | Owns issues |
|---|---|---|
| `01-infra-storage.md` | Infra / media delivery / storage | #54, #74 |
| `02-models.md` | Models, fields, validators, migrations, admin | #24, #38, #62, #68, #73†, #75†, #77, #85† |
| `03-serializers.md` | Serializers & field-level validation | #25, #29, #30, #31, #39, #40, #45, #46, #60, #65, #66, #67† |
| `04-permissions.md` | DRF permissions & access control | #32†, #41, #55, #56, #58, #59 |
| `05-views-throttling.md` | Views, status codes, throttling, routing | #15, #28, #42, #48, #49, #57, #64, #69, #76, #81, #87, #88 |
| `06-services-signals-tasks.md` | Stripe/OAuth services, signals, Celery tasks | #12, #13, #14, #16, #18, #23, #27, #29†, #43, #44, #47, #73, #78, #79, #80 |
| `07-tests.md` | Test coverage & security deny-tests | #17, #26, #34, #35, #50, #72†, #82, #86 |
| `08-lint-style.md` | Lint, type hints, docstrings, dead code | #19, #20, #21, #22, #36, #37, #51, #52, #53, #61, #63, #70, #71, #83, #84, #89, #90, #91, #92 |

† = cross-layer issue; the playbook that owns it is marked, others cross-reference it.

## Sequencing (dependencies first)

```
Phase 0 — Foundations (unblock everything else)
  04-permissions  : fix IsOwnerOrReadOnly.has_permission + global default   (#41)
  05-throttling   : set global DEFAULT_THROTTLE_RATES                       (#76, #87, #49)
  01-infra-storage: protected media delivery (X-Accel-Redirect/pre-signed)  (#54, #74)

Phase 1 — Blocking by theme (depends on Phase 0)
  privilege-pii         : 03-serializers (#39,#40,#30) + 05-views (#42)
  access-control        : 04-permissions (#55,#56)
  transactional         : 06-services (#12,#29) + 05-views (#28)
  certificate-trust     : 02-models (#77,#75,#73) + 05-views (#76) + 06-tasks (#73)

Phase 2 — Major (correctness/perf/business rules)
  02-models (#68,#38,#24) · 03-serializers (#65,#66,#67,#46,#45,#31) ·
  05-views (#64,#69,#15,#81,#88,#48,#57) · 06 (#13,#14,#16,#18,#27,#43,#44,#47,#78,#79,#80)

Phase 3 — Hardening & hygiene
  07-tests (all coverage/deny-test gaps) · 08-lint-style (batch, all apps)
```

## Cross-cutting fixes (do once, resolve many)

1. **Permission baseline** (#41) — root of PII exposure; unblocks users app.
2. **Global throttling** (#76/#87/#49) — one settings change covers verification, health, auth.
3. **Protected media delivery** (#54/#74) — one infra+serializer change closes 2 Blocking leaks.
4. **Create-serializer / mass-assignment pattern** (#30/#39/#40) — same fix shape across apps.
5. **Idempotent webhook/task writes** (`get_or_create` + `IntegrityError`) — #12/#28/#79.

## Status & interleaved production bugs (updated 2026-06-19)

- **Phase 0 + Phase 1 (all 16 Blocking): done, merged, deployed to prod 2026-06-18** (PRs #102–#109).
- **Production-discovered bugs (milestone #2 "Production Stabilization", NOT in the 81 audit
  findings)** — found via manual testing after the deploy:
  - **#110** (Blocking, `app:infra`) — Celery worker never runs (`entrypoint.sh` ignores the
    container `command`; the `celery`/`celery-beat` services run gunicorn). Async tasks (cert PDF,
    any video processing) are never consumed. **Do this BEFORE Phase 2.** Not a `/fix-issue`-shaped
    code slice — it's infra (`entrypoint.sh`/`docker-compose.yml`) + a deploy + reprocessing stuck
    certs. See memory `infra_celery_entrypoint_bug` and the executive summary.
  - **#111** (Major, `app:videos`) — `Video.duration` never extracted (player shows 0:00); folds
    into Phase 2 (may depend on #110 if extraction is async).
  - **#112** (Major, `app:videos`) — intermittent playback / Range over the signed X-Accel stream;
    folds into Phase 2.
- **Revised order:** **#110 → Phase 2 (Major)** with #111/#112 interleaved by app/layer.

## Working agreement (per project rules)

- TDD: write the failing deny-test/regression test first (RED → GREEN → REFACTOR).
- One PR per layer-slice per app; conventional commits; ask before committing.
- Each issue closes only when its **done criteria** (in the playbook) are met and tests pass.
- Coverage gate ≥80% (≥90% on payments/enrollments/permissions/certificates critical paths).
