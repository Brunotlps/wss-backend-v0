# Layer: Views / Status Codes / Throttling / Routing

**Owns:** #76 (verification throttle, Blocking), #28 (dup→409, Blocking), #42 (profile 500,
Blocking), #15, #64, #69, #81, #88, #87, #48, #49, #57.
**Themes:** `transactional-integrity`, `certificate-trust`, plus correctness/perf.

## Canonical patterns (`.claude/rules/api-conventions.md`, `security.md`)

- Status codes: 402 payment required, 409 conflict (already-exists), 403 authz, 410 gone.
- Throttling: global `DEFAULT_THROTTLE_RATES` + dedicated throttles on sensitive actions.
- Query optimization in `get_queryset` (annotate counts; `select_related`/`prefetch_related`).

## Phase 0 — global throttling (#76, #87, #49 share this)
```python
# config/settings/base.py
REST_FRAMEWORK = {
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {"anon": "100/hour", "user": "1000/hour"},
}
NUM_PROXIES = 2  # #48: behind Cloudflare + Nginx, else throttle keys on the proxy IP
```

## Issues & fixes

### Certificate verification throttle — #76 (Blocking) ✅ FIXED (Phase 0/1, 2026-06-18)
Dedicated `class VerifyThrottle(AnonRateThrottle): rate = "20/min"` on `validate_by_code`
(`AllowAny` stays). Brute-force of the (now crypto) code becomes infeasible.

### Status-code correctness
- #28 (Blocking) ✅ FIXED: duplicate enrollment POST → **409** (check + catch `IntegrityError`; pair with
  `get_or_create` in `06`). Fix the masked test (`{"course": pk}` → `course_id`, expect 409).
- #15 ✅ FIXED (PR #132, 2026-06-23~25): payments "already enrolled" → **409** (not 400).
- #81 ✅ FIXED (PR #134, 2026-06-23~25): `download` returns **410/403** when `is_valid` is False (revoked).

### Profile create 500 — #42 (Blocking) ✅ FIXED (Phase 0/1, PR #103, 2026-06-18)
`ProfileViewSet` → read/update mixins (no create), or `perform_create(user=self.request.user)` +
`IsAuthenticated`. Profiles are created by signal; the create endpoint shouldn't 500.

### Query optimization — #64 (courses, Major) ✅ FIXED (PR #128, 2026-06-23~25)
Annotate in `get_queryset`: `Count("enrollments", filter=Q(enrollments__is_active=True))`,
`Count("lessons")`; read annotations in the serializer (removes N+1). Also #53 (users N+1:
`prefetch_related("profile")`) — ✅ fixed, PR #201.

### Price soft-freeze + audited adjust — #69 (courses, Major; product decision recorded) ✅ FIXED (PR #130, 2026-06-23~25)
`price` read-only via normal PATCH when `enrolled_count > 0`; dedicated
`@action POST /courses/{id}/adjust-price/` (owner-only, requires `confirm=true` when enrollments
exist, validates ≥0, logs `old→new` + actor + timestamp). Existing enrollments unaffected
(`Payment.amount` is the source of truth).

### Upload throttle — #57 (videos, Major) ✅ FIXED (PR #137, 2026-06-23~25)
`UploadRateThrottle (10/day)` on `VideoViewSet` create, dedicated `video_upload` scope. Same
defect resurfaced in payments as **#136 — also ✅ FIXED (PR #209, 2026-07-04)**, dedicated
`payment_intent` scope.

### Auth throttles — #49 (users, Major) ✅ FIXED (Phase 0/1, 2026-06-18)
`RegistrationThrottle (5/day)` on registration; throttle on the OAuth endpoints.

### Readiness endpoint — #88 (core, Major) ✅ FIXED (PR #139, 2026-06-23~25)
`/api/health/ready/` checks DB (`SELECT 1`) + cache round-trip, returns **503 gracefully**
(caught, no stack trace, short timeout). Keep the existing liveness probe + add its throttle
(#87 — ✅ fixed alongside, Phase 0).

## Done criteria
- [x] Global throttle active; verification ≤20/min; register/upload throttled; `NUM_PROXIES` set. — #76/#49/#57/#48.
- [x] Duplicate enrollment → 409; already-enrolled payment → 409; revoked download → 410/403. — #28/#15/#81.
- [x] Profile create no longer 500s. — #42.
- [x] Course list/detail issue no per-row COUNT queries (assert query count in a test). — #64.
- [x] `adjust-price` works owner-only with confirmation + audit log; `/ready/` returns 503 on a
      simulated DB/cache outage. — #69/#88.
