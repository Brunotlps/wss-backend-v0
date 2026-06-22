# Layer: Serializers & Field-Level Validation

**Owns:** #30, #39, #40 (mass-assignment, Blocking), #29† (cross-course validation), #45, #46,
#65, #66, #67†, #31, #25, #60.
**Themes:** `privilege-pii`, `transactional-integrity`.

## Canonical pattern (`.claude/rules/security.md` — Prevent Mass Assignment)

Dedicated **create** serializers expose only client-settable fields; system/role fields are
read-only or absent. Authorization lives in permissions (403), **not** in serializer `validate`
(which returns 400). Cross-object integrity is validated in `validate()`.

```python
class EnrollmentCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Enrollment
        fields = ["course_id"]            # only this is client-settable
        # completed, completed_at, rating, review, certificate_issued, is_active → NOT here
```

## Issues & fixes

### Mass-assignment — #30, #39, #40 (Blocking)
- enrollments #30: create serializer with only `course_id` (and maybe `is_active`).
- users #39: remove `is_instructor` from `UserRegistrationSerializer.fields` (or `read_only`).
- users #40: make `is_instructor` read-only on `UserUpdateSerializer` (today only demotion is
  blocked; promotion slips through).

### Cross-course progress → fraudulent certificate — #29† (Blocking)
`LessonProgressSerializer.validate()` must reject when `lesson.course_id != enrollment.course_id`.
(Defensive count in the signal lives in `06`.)
```python
def validate(self, attrs):
    if attrs["lesson"].course_id != attrs["enrollment"].course_id:
        raise serializers.ValidationError("Lesson does not belong to this enrollment's course.")
    return attrs
```

### Email normalization & enumeration — #46, #45 (users, Major)
`validate_email` → `value.lower()`, uniqueness via `email__iexact`; normalize in the OAuth
`_find_or_create_user` too (prevents duplicate accounts). **Done (#46):** `User.save()` lowercases
the stored email (single source); `validate_email` adds the case-insensitive check; OAuth looks up
via `email__iexact`; `CustomTokenObtainPairSerializer` lowercases the login email so storage
normalization does not break case-typed logins.

**#45 — product decision (2026-06-22): documented & accepted, no code change.** The explicit
"email already exists" message is kept. Rationale: the registration endpoint is throttled to
`register: 5/day` per IP (mass enumeration is impractical), and true non-enumeration requires an
email-confirmation flow (always-200 "check your inbox") — a separate feature, risky to retrofit on
a live product. Revisit if/when that flow is built. **Follow-up:** legacy case-duplicate rows
predating #46 can make the OAuth `email__iexact` lookup raise `MultipleObjectsReturned`; needs a
one-off detection/merge before it can bite (not auto-merged here).

### Price validation — #65 (courses, Major)
`validate_price` rejects `value < 0` in create & update serializers (or `MinValueValidator(0)`
on the model + migration).

### Drop redundant authz checks (wrong status) — #66, #25 (courses/payments)
Remove ownership/role re-checks from serializers that duplicate permissions and return 400 instead
of 403; rely on the permission classes. Move `instructor = request.user` to `perform_create`.
Delete dead `PaymentIntentResponseSerializer` (#25) or wire it into the response.

### Progress POST timestamps — #31 (enrollments, Major)
Move `completed_at`/`watched_duration` logic into a shared method called by both `create` and
`update` (today only `update` sets them).

### Publish content-gate — #67† (courses, Major)
`validate` blocks `is_published=True` when `obj.lessons.count() == 0` (or move to a `publish`
action in `05`).

### Docstring vs validation — #60 (videos, Minor): sync serializer docstring with `validators.py`
(2GB, no avi).

## Order / dependencies
- #39/#40/#30 unblock the `privilege-pii` theme; pair with `04-permissions` #41.
- Media-field exposure changes (#54/#74) are applied here too — see `01`.

## Done criteria
- [ ] POST/PATCH cannot set `is_instructor`, `completed`, `rating`, `review`, `is_active`,
      `is_published` (where not allowed) — deny-tests assert each is ignored/400.
- [ ] Progress with a foreign-course lesson → 400.
- [ ] Negative price → 400; emails stored lowercase; no duplicate-by-case accounts.
- [ ] No serializer returns 400 for an authorization failure (permissions return 403).
