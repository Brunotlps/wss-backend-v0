# Layer: Tests — Coverage & Security Deny-Tests

**Owns:** #17, #26, #34, #35, #50, #72†, #82, #86.
**Rule:** `.claude/rules/testing.md` — TDD (RED→GREEN→REFACTOR), factory-boy, ≥80% overall, ≥90%
on critical paths (payments, enrollments, permissions, certificates). Every Blocking fix lands
with its regression/deny-test **first**.

## Highest-risk gaps

### Certificate task & PDF utils — #82 (Major; `utils.py` 24%)
Add `test_tasks.py` + `test_utils.py`:
- idempotent re-run does **not** regenerate (PDF present);
- `Certificate.DoesNotExist` swallowed (deleted between enqueue and run);
- final failure sets `pdf_generation_failed_at` + alerts; retry behavior;
- code format/entropy/collision-retry; smoke test that a PDF file is written;
- public verification leaks no email/id; a PDF-pending cert still verifies as valid (#73).

### Payments webhook signature — #17 (Major)
Patch `stripe.Webhook.construct_event` (one level below the always-mocked
`verify_webhook_signature`) and assert it's called with the raw body, `Stripe-Signature` header,
and `STRIPE_WEBHOOK_SECRET`; optionally a real-HMAC test.

### Users security deny-tests — #50 (Major)
- `is_instructor` rejected at register and on PATCH (#39/#40);
- anonymous PII access **denied** (current tests assert the insecure behavior — rewrite them);
- `_exchange_code` with mocked `requests.post`; wrong-`audience` id_token; permissions deny branches.

### Enrollments — #34, #35 (Major)
- #34: POST/PATCH on `/api/progress/` (success, wrong owner→400, watched>duration→400,
  foreign-course lesson→400 after #29); end-to-end completion → certificate (`.delay` mocked).
- #35: remove/rewrite the obsolete `test_enrollment_created_without_payment_verification` (the
  402 rule is enforced at the view, not the model).

### Core — #86 (Major)
`TimeStampedModel` behavioral test via a concrete model: `created_at` set on create and unchanged
on update; `updated_at` advances. Health check: HEAD method + assert response shape.

### Smaller
- #72†: `filter_is_free` true/false branches (courses).
- #26: replace `reverse()` at import in `test_throttling.py` with `reverse_lazy`/fixture.

## Pattern reminder
```python
@pytest.mark.django_db
def test_register_ignores_is_instructor_flag(api_client):
    resp = api_client.post("/api/auth/register/",
                           {"email": "a@b.com", "password": "x", "is_instructor": True})
    assert resp.status_code == 201
    assert User.objects.get(email="a@b.com").is_instructor is False
```

## Done criteria
- [ ] Each Blocking issue has a regression test that fails before the fix and passes after.
- [ ] `apps.certificates` task/utils ≥90%; `apps.users` permissions ≥90%; enrollments serializers
      back above 80%.
- [ ] No test asserts insecure behavior as "expected" (audit found several).
- [ ] `pytest` green; coverage gate met without relying on import-time-only lines.
