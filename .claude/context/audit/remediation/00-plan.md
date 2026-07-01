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

## Status (updated 2026-06-30)

- **Phase 0 + Phase 1 (all 16 Blocking): done, merged, deployed to prod 2026-06-18** (PRs #102–#109).
- **Milestone #2 "Production Stabilization" (prod bugs, NOT audit findings): COMPLETE & validated**
  — #110 (Celery worker ran gunicorn → fixed, PR #113; **worker now runs in prod**), #111 (video
  duration via ffprobe, PR #115), #112 (streaming anon throttle → `video_stream` scope, PR #120),
  #114 (nginx stale upstream IP, mitigated, PR #119), #116 (cert download CORS → FileResponse, PR #117).
- **Phase 2 (Major) — COMPLETE (all four layers, 2026-06-29):**
  - **models + serializers: DONE** (2026-06-22) — #68, #65/#66/#67 (migration `courses/0004`),
    #46, #31; #45 closed as documented product decision.
  - **views/throttling (`05`): DONE** (2026-06-23~25) — #64 (PR #128), #69 (PR #130), #15
    (PR #132), #81 (PR #134), #57 (PR #137), #88 (PR #139).
  - **services/signals/tasks (`06`): DONE** (2026-06-26~29), all validated in prod:
    payments webhooks #13/#14/#18/#27 (PR #142) + #16 lifecycle 16a/16b (PRs #144/#146) + #23
    fail-fast settings; certificates #79/#80/#78 (PR #149, migration `certificates/0006` nullable
    code); OAuth #44/#47 (PR #152), #43 in two steps — exchange endpoint (PR #154) + callback
    cut-over (PR #157, `#code=` fragment, exchange runs no JWT auth). **#43 frontend cut-over also
    done** (wss-frontend PR #9 → main → Vercel; live Google login confirmed 2026-06-29).
- **Phase 3 (hardening & hygiene) — IN PROGRESS:**
  - **`07-tests`: DONE (100%, 2026-06-30, all test-only, no deploy).** #82 cert task/utils (PR #161),
    #50 users deny-tests (PR #163), #17 webhook signature (PR #165), #34/#35 enrollments (PR #167),
    #86 core TimeStampedModel/health (PR #169), #72 courses filter_is_free (PR #171), #26 payments
    reverse_lazy (PR #173). Each has a slice doc in `.claude/context/backlog/2026-06-30-*.md`.
  - **`08-lint-style`: IN PROGRESS.** Batch 1 done — #92 config lint + CI now lints `apps/ config/`
    (PR #175, formatting only, no deploy). **Remaining = Batch 2 (type hints+docstrings) + Batch 3
    (dead code), one app per PR:** payments #19/#20/#21/#22 · enrollments #36/#37 · users #51/#52/#53 ·
    videos #61/#63 · courses #70/#71 · certificates #83/#84 · core #89/#90/#91.
  - **Then videos #60** (serializer docstring vs validation, Minor) closes Phase 3.
  - ⚠️ Non-style items to handle with care: certificates #85 (error envelope `{"error"}`→`{"detail"}`
    = frontend contract), core #91 (de-dup hardcoded `version`), users #53 (defensive `id_token` check
    in `_exchange_code` is logic, not format — keep out of the auto-format commit).
- **Open follow-ups (GitHub issues):** #155 (`oauth-exchange` throttle scope + Redis observability),
  #151 (Docker healthcheck 301 via SSL redirect), #136 (`PaymentIntentRateThrottle` scope),
  #122 (module serializer authz 400→403), #38 (cert `on_delete`).

## Working agreement (per project rules)

- TDD: write the failing deny-test/regression test first (RED → GREEN → REFACTOR).
- One PR per layer-slice per app; conventional commits; ask before committing.
- Each issue closes only when its **done criteria** (in the playbook) are met and tests pass.
- Coverage gate ≥80% (≥90% on payments/enrollments/permissions/certificates critical paths).
