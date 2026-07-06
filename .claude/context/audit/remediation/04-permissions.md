# Layer: DRF Permissions & Access Control

**Owns:** #41 (PII exposure, Blocking), #55, #56 (gating bypass, Blocking), #58, #59, #32†.
**Themes:** `privilege-pii`, `access-control`. **Phase 0** for #41.

## Canonical pattern (`.claude/rules/django-patterns.md`, `api-conventions.md`)

Permissions enforce both **collection-level** (`has_permission`) and **object-level**
(`has_object_permission`). Authorization → 403. Compose, don't duck-type. Raise
`PermissionDenied(detail=...)` rather than mutating instance state.

```python
class IsOwnerOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view) -> bool:           # #41: was missing
        return request.user and request.user.is_authenticated   # no anonymous list/retrieve
    def has_object_permission(self, request, view, obj) -> bool:
        if request.method in permissions.SAFE_METHODS:
            return obj == request.user or request.user.is_staff
        return obj == request.user
```

## Issues & fixes

### Anonymous PII exposure — #41 (Blocking, root cause)
- Add `has_permission` (above) to `IsOwnerOrReadOnly`.
- Compose `[IsAuthenticated, IsOwnerOrReadOnly]` on `UserViewSet`/`ProfileViewSet`.
- Re-evaluate the global default `DEFAULT_PERMISSION_CLASSES = IsAuthenticatedOrReadOnly`
  (`config/settings/base.py:196-198`) — it silently permits anonymous reads everywhere; prefer
  `IsAuthenticated` globally with explicit `AllowAny` on public endpoints (catalog, health,
  certificate verification).
- Non-owners get a public-fields-only serializer (no email/phone/birth_date) — see `03`.

### Video gating bypass — #55, #56 (Blocking)
- #55: apply an enrollment-aware permission on `VideoViewSet` (today only `LessonViewSet` has
  `IsEnrolled`), or stop returning `file` to non-enrolled users.
- #56: gate preview on `getattr(obj, "is_free_preview", False)` for Lessons and
  `obj.lesson.is_free_preview` for Videos. **Drop the `order == 1` heuristic.**

### `IsEnrolled` hardening — #58, #59 (videos, Major)
- **#58 ✅ FIXED (2026-07-04, PR #207).** Replaced `self.message = ...` side-effect with
  `raise PermissionDenied(detail=...)` (thread-safety; avoids leaking another course's title into
  a reused permission instance). Deployed + validated in prod.
- **#59 ✅ RESOLVED as a documented product decision (2026-07-04) — no code change.** List
  visibility (`GET /api/lessons/`) exposing metadata (title/order/duration/thumbnail/
  is_free_preview) to non-enrolled users for published courses is **intentional catalog
  browsing**, same rationale as #72 (`is_published` kept in list). No leak of file bytes:
  `LessonListSerializer`/`VideoListSerializer` never expose the raw file, only a `stream_url`
  pointing at `/api/videos/{id}/file/`, which is itself gated by `IsEnrolled` at the object/file
  level (#54/#55/#56). `IsEnrolled` correctly stays object-permission-only; list is a catalog
  view by design.

### `is_active=False` enforcement — #32† (enrollments, Major)
**✅ FIXED (2026-07-04, PR #211).** Decision: `is_active=False` blocks video access (already true
via `IsEnrolled`) **and** blocks new progress writes / course auto-completion
(`LessonProgressSerializer.validate()` + `check_course_completion` signal, defense-in-depth).
A certificate already issued before deactivation is **not** retroactively revoked. Deployed +
validated in prod. See `.claude/context/backlog/2026-07-04-enrollments-is-active-semantics-32.md`.

## Order / dependencies
- #41 first (Phase 0) — unblocks the users app and the `privilege-pii` theme.
- #55/#56 must land with the protected media view (`01`) so the bypass doesn't just relocate.

## Done criteria
- [ ] Anonymous `GET /api/users/` and `/api/profiles/` → 401/403; non-owner cannot read PII.
- [ ] Non-enrolled user cannot retrieve non-preview video metadata or file via **any** endpoint.
- [ ] Preview access derives from `is_free_preview`, not `order`.
- [ ] Permission classes raise 403 via `PermissionDenied`, no instance mutation.
- [ ] Allow + deny tests for each (owner / other / anonymous / enrolled / preview).
