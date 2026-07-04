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

## Status (updated 2026-07-04)

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
- **Phase 3 (hardening & hygiene) — `07-tests` + `08-lint-style` DONE (2026-07-04):**
  - **`07-tests`: DONE (2026-06-30, test-only).** #82 (PR #161), #50 (#163), #17 (#165), #34/#35 (#167),
    #86 (#169), #72 (#171), #26 (#173). Slice docs in `.claude/context/backlog/2026-06-30-*.md`.
  - **`08-lint-style`: DONE (2026-07-02~03), all 8 apps.** #92 config (PR #175) · payments #19-22 (#178) ·
    enrollments #36/#37 (#181) · courses #70/#71 (#184) · certificates #83/#84 (#186) · users #51/#52 (#188) ·
    core #89/#90 (#191) · videos #60/#61 (#193). Lint siblings (#19/#20, #36, #51, #61, #70, #83, #89) were
    already satisfied on `main` from Phase 2 rewrites → closed with evidence.
  - **Hygiene DONE:** core #91 version de-dup + dead `default_app_config` (PR #196), #195 dead config in
    the other 5 apps (PR #198), users #53 no-deploy scope — defensive `id_token`, N+1 lock, dead code (PR #201).
  - **Migration window DONE + DEPLOYED to prod (2026-07-03):** #63 videos type hints + `Video.Meta.indexes`
    (PR #203, `videos/0005` AddIndex×3) + #190 `updated_at` help_text (abstract base → AlterField in 6 apps) +
    #200 `User.email/phone` verbose_name (PR #204). One `migrate`: 1 index + 7 metadata-only (`sqlmigrate`=no-op).
    Sequential merges (avoid migration-number collision). Slice docs `2026-07-03-*.md`.
- **⚠️ STILL OPEN — audit findings NOT yet remediated (surfaced by a consistency sweep 2026-07-04).**
  The pre-2026-07-04 Status wrongly implied the audit was nearly done. Reality: the **`04-permissions`
  layer's Major issues were never scheduled** (only its Blocking #41/#55/#56 were done in Phase 0/1), plus
  several Minors remain. Verified present in code on 2026-07-04:
  - **Major (5):** #58 videos (`IsEnrolled` mutates `self.message` — thread-safety; `permissions.py:195`) ·
    #59 videos (`IsEnrolled` has no list gating → non-enrolled see all lesson metadata; **product decision**) ·
    #32 enrollments (`is_active=False` semantics undefined; **decision + test + field doc**) · #33 enrollments
    (cache invalidation bypassed by `queryset.update()`/bulk; **latent**, no mass-update today) · #136
    payments (`PaymentIntentRateThrottle` shares the global `user` bucket; same defect #57 fixed for uploads).
  - **Minor (10):** #85 certificates (error envelope `{"error"}`→`{"detail"}` = **frontend contract** +
    redundant index + naive datetime) · #62 videos **bug** (f-string inside `_()` gettext breaks i18n,
    `validators.py:56/98/110`; + 2 messages missing a separator) · #24 payments (admin allows silent Payment
    `status` edits) · #25 payments (dead `PaymentIntentResponseSerializer`) · #38 cert `on_delete=CASCADE` ·
    #122 courses (module serializer 400→403) · #151 infra (healthcheck 301) · #155 users (OAuth exchange
    hardening) · #180 enrollments (123-char f-string) · #183 infra (venv shebangs).
  - **Counts:** Blocking 0/18 · Major 5/42 open · Minor 10/36 open. No pre-decided "next slice" — the open
    items mix product decisions (#32/#59), correctness/security fixes (#58/#136/#62), dead code (#25/#24),
    and a frontend contract (#85). Run `/audit-status` and recommend per severity/layer.

## Working agreement (per project rules)

- TDD: write the failing deny-test/regression test first (RED → GREEN → REFACTOR).
- One PR per layer-slice per app; conventional commits; ask before committing.
- Each issue closes only when its **done criteria** (in the playbook) are met and tests pass.
- Coverage gate ≥80% (≥90% on payments/enrollments/permissions/certificates critical paths).
