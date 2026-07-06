# Layer: Models / Fields / Validators / Migrations / Admin

**Owns:** #77, #75†, #73†, #38, #68, #62, #24, #85† (index/datetime parts).
**Themes:** `certificate-trust`, plus correctness/maintainability.

## Canonical patterns (`.claude/rules/django-patterns.md`, `code-style.md`)

- All models inherit `TimeStampedModel`; explicit `related_name`; `TextChoices`; `Meta.indexes`
  for filtered/ordered fields; deliberate `on_delete`.
- Money: `DecimalField` + `Decimal` arithmetic, never `float`.
- Validators raise `ValidationError`; use `%`/`.format` inside `gettext`, not f-strings.

## Issues & fixes

### Certificate as an immutable, durable legal document — #77 (Blocking) ✅ FIXED (PR #108, 2026-06-18)
Denormalize a snapshot at issue time so the document survives edits/deletes of its sources.

```python
class Certificate(TimeStampedModel):
    enrollment = models.OneToOneField(
        "enrollments.Enrollment", on_delete=models.SET_NULL, null=True,
        related_name="certificate",
    )  # #38: was CASCADE — was destroying the legal record
    # snapshot, populated once in the signal/task, never recomputed:
    student_name = models.CharField(max_length=255)
    course_title = models.CharField(max_length=255)
    instructor_name = models.CharField(max_length=255)
    completion_date = models.DateField()
    code = models.CharField(max_length=20, unique=True, db_index=True)
    pdf_generated_at = models.DateTimeField(null=True, blank=True)   # #73: PDF state…
    is_valid = models.BooleanField(default=True)                     # …separate from revocation
```
Model properties prefer the stored snapshot. Migration: backfill snapshot for existing rows.

### Verification code — crypto + entropy — #75 (Blocking) ✅ FIXED (PR #107, 2026-06-18)
```python
import secrets
ALPHABET = string.ascii_uppercase + string.digits
def generate_certificate_code() -> str:
    for _ in range(5):
        code = f"WSS-{timezone.now():%Y}-" + "".join(secrets.choice(ALPHABET) for _ in range(12))
        if not Certificate.objects.filter(code=code).exists():
            return code
    raise RuntimeError("could not allocate unique certificate code")
```
(Generation moves into the task — see `06`. Decouple code from the stored filename — see `01`.)

### `is_valid` overload — #73 (Blocking) ✅ FIXED (PR #107, 2026-06-18)
Model owns the field split (above); task owns the guard (`if certificate.pdf_file:`) in `06`.

### Slug collision → 500 — #68 (courses, Major) ✅ FIXED (PR #125, 2026-06-22)
Unique-suffix loop; decide `allow_unicode` deliberately; surface 400 (not 500) on collision.
```python
base = slugify(self.title); slug = base; i = 2
while Course.objects.filter(slug=slug).exclude(pk=self.pk).exists():
    slug = f"{base}-{i}"; i += 1
self.slug = slug
```

### Validator i18n + missing separators — #62 (videos, Minor, has a real text bug) — ⬜ OPEN
`_("...type. ") + _("Make sure...")` — add the missing space; use `%(x)s` not `_(f"...")`.

### Misc — #24 (payments admin: `status` editable on financial record → make read-only or audit) — ⬜ OPEN,
#85 (certificates: drop redundant index on `certificate_code`; `timezone.now()` not naive `today()`) — ✅ FIXED (PR #218, 2026-07-06).

### `on_delete=CASCADE` on Certificate.enrollment — #38 (certificates, Minor) ✅ FIXED (PR #221, 2026-07-06)
Changed to `SET_NULL` + `null=True` (migration `0009`). Fixed the 3 call sites that bypassed the
model's already-null-safe snapshot properties (`__str__`, `validate_by_code`, admin display
methods). Follow-up filed: #220 (staff can't actually access other users' certificates, unrelated
latent gap surfaced during this fix).

### `is_active` semantics — #32† (enrollments, Major) ✅ RESOLVED (PR #211, 2026-07-04)
Decided: blocks video access (already true) + progress writes + auto-completion; certificate
already issued is not retroactively revoked. See `04-permissions.md`.

## Done criteria
- [x] Certificate renders from its own snapshot; editing source course/user does not change an
      issued certificate or its verification response. — #77.
- [x] Deleting an enrollment no longer deletes the certificate (FK `SET_NULL`/`PROTECT`). — #38.
- [x] Codes are `secrets`-based, ≥12 secret chars, collision-safe. — #75.
- [x] Slug collisions return 400; money fields use `Decimal` end-to-end (see `06` #14). — #68 + #14.
- [x] Migrations reviewed (project rule: ask before makemigrations). — followed consistently across all slices.
