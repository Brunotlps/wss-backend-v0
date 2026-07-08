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
- **✅ Majors from the consistency sweep — ALL RESOLVED (2026-07-04).** The sweep found the
  `04-permissions` layer's Major issues had never been scheduled (only Blocking #41/#55/#56 were
  done in Phase 0/1). All 5 residual Majors closed same-day:
  - **#58** videos — `IsEnrolled` self.message mutation → `raise PermissionDenied`. **FIXED, PR #207.**
  - **#136** payments — `PaymentIntentRateThrottle` shared the global `user` bucket → dedicated
    `payment_intent` scope (same pattern as #57). **FIXED, PR #209.**
  - **#32** enrollments — `is_active=False` semantics: decided to block video (already true) +
    progress writes + auto-completion; certificate already issued is not retroactively revoked.
    Real gap found: a refunded student could still complete lessons and trigger certificate
    generation. **FIXED, PR #211.** See `04-permissions.md`.
  - **#59** videos — list visibility (non-enrolled sees lesson metadata for published courses).
    **RESOLVED as documented decision** (catalog browsing intentional, same rationale as #72; no
    file-byte leak, only metadata — bytes stay gated by `IsEnrolled` at the file endpoint). No
    code change. See `04-permissions.md`.
  - **#33** enrollments — cache invalidation bypassed by bulk `.update()`/`bulk_create`.
    **RESOLVED as documented decision** — no bulk call site exists on `Enrollment` today
    (verified by grep); the constraint is now documented on the model docstring rather than
    building unused robustness for a hypothetical bulk write path.
  - All fixes deployed + validated in prod. Docs: `.claude/context/backlog/2026-07-04-*.md`.

- **2026-07-06 slices (most-complex-first order): #155, #85, #38, #122 all ✅ FIXED, deployed,
  validated in prod.** #155 users (OAuth exchange scope + Redis-outage detection, PR #216) · #85
  certificates (error envelope `detail` + redundant index + `timezone.now()`, PR #218; frontend
  coordinated and updated by Bruno) · #38 certificates (`on_delete` CASCADE→SET_NULL, PR #221;
  surfaced follow-up **#220** — staff can't actually access other users' certificates) · #122
  courses (module create ownership moved to permission layer, PR #224; surfaced follow-up **#223**
  — unfiltered course lookup can enumerate unpublished courses). Docs:
  `.claude/context/backlog/2026-07-06-*.md`.

- **2026-07-07 slice: #62 ✅ FIXED, deployed, validated in prod** (PR #226, doc PR #227). Videos
  validator i18n bug (f-string in `gettext`) + 2 missing separators fixed via `%(x)s` + `params=`
  substitution. Surfaced an unexpected metadata-only migration (`videos/0007_alter_video_file`,
  `sqlmigrate`-confirmed no-op) because changing a `FileExtensionValidator.message` changes the
  field's migration state.

- **2026-07-07 slice: #24 ✅ FIXED, deployed, validated in prod** (PR #228). `Payment.status` added
  to `PaymentAdmin.readonly_fields` — confirmed via grep that no code/runbook relies on manual
  status edits (Stripe webhook lifecycle in `services.py` is the sole source of truth). No
  migration (admin-only config).

- **Remaining — Minor (3) of the original 2026-06 audit, no Major left open.** #151 infra
  (healthcheck 301) · #180 enrollments (123-char f-string) · #183 infra (venv shebangs).
  - **Counts:** Blocking 0/18 · Major 0/42 open · Minor 4/38 open (+ 2 new follow-ups #220/#223
    filed during the 2026-07-06 slices, tracked separately from the original audit's count). Run
    `/audit-status` and recommend per severity/layer — remaining items are mechanical style fixes
    (#180/#183) and an infra fix (#151).

## Working agreement (per project rules)

- TDD: write the failing deny-test/regression test first (RED → GREEN → REFACTOR).
- One PR per layer-slice per app; conventional commits; ask before committing.
- Each issue closes only when its **done criteria** (in the playbook) are met and tests pass.
- Coverage gate ≥80% (≥90% on payments/enrollments/permissions/certificates critical paths).
