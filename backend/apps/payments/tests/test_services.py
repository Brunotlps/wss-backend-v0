"""Tests for StripeService business logic."""

import hashlib
import hmac
import logging
import time
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.db import IntegrityError

import pytest
import stripe

from apps.courses.factories import CourseFactory
from apps.enrollments.factories import EnrollmentFactory
from apps.enrollments.models import Enrollment
from apps.payments.factories import PaymentFactory
from apps.payments.models import Payment
from apps.payments.services import StripeService
from apps.users.factories import UserFactory


@pytest.mark.django_db
class TestStripeServiceCreatePaymentIntent:
    """Tests for StripeService.create_payment_intent."""

    @patch("apps.payments.services.stripe.PaymentIntent.create")
    def test_returns_client_secret_and_intent_id(self, mock_create):
        """create_payment_intent returns expected keys."""
        mock_create.return_value = MagicMock(
            id="pi_test_123",
            client_secret="pi_test_123_secret_abc",
            amount=10000,
            currency="brl",
        )
        user = UserFactory()
        course = CourseFactory(price=100.00)

        result = StripeService.create_payment_intent(user, course)

        assert result["client_secret"] == "pi_test_123_secret_abc"
        assert result["payment_intent_id"] == "pi_test_123"
        assert result["amount"] == 10000
        assert result["currency"] == "brl"

    @patch("apps.payments.services.stripe.PaymentIntent.create")
    def test_calls_stripe_with_correct_amount_in_cents(self, mock_create):
        """Price in BRL is converted to cents before calling Stripe."""
        mock_create.return_value = MagicMock(
            id="pi_test_456",
            client_secret="secret",
            amount=9990,
            currency="brl",
        )
        user = UserFactory()
        course = CourseFactory(price=99.90)

        StripeService.create_payment_intent(user, course)

        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["amount"] == 9990

    @patch("apps.payments.services.stripe.PaymentIntent.create")
    def test_metadata_contains_user_and_course_ids(self, mock_create):
        """Stripe metadata includes user_id, course_id and emails."""
        mock_create.return_value = MagicMock(
            id="pi_test_789",
            client_secret="secret",
            amount=5000,
            currency="brl",
        )
        user = UserFactory()
        course = CourseFactory(price=50.00)

        StripeService.create_payment_intent(user, course)

        metadata = mock_create.call_args[1]["metadata"]
        assert str(user.id) == str(metadata["user_id"])
        assert str(course.id) == str(metadata["course_id"])
        assert user.email == metadata["user_email"]

    @patch("apps.payments.services.stripe.PaymentIntent.create")
    def test_uses_deterministic_idempotency_key(self, mock_create):
        """A deterministic idempotency_key is passed so a retry / second tab
        reuses the same intent instead of creating a second live one (#12)."""
        mock_create.return_value = MagicMock(
            id="pi_idem",
            client_secret="secret",
            amount=10000,
            currency="brl",
        )
        user = UserFactory()
        course = CourseFactory(price=100.00)

        StripeService.create_payment_intent(user, course)

        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["idempotency_key"] == f"pi:{user.id}:{course.id}"

    @patch("apps.payments.services.stripe.PaymentIntent.create")
    def test_raises_stripe_error_on_api_failure(self, mock_create):
        """StripeError from API bubbles up to the caller."""
        import stripe

        mock_create.side_effect = stripe.error.APIConnectionError("Network error")
        user = UserFactory()
        course = CourseFactory(price=100.00)

        with pytest.raises(stripe.error.StripeError):
            StripeService.create_payment_intent(user, course)

    @patch("apps.payments.services.stripe.PaymentIntent.create")
    def test_persists_pending_payment_on_intent_creation(self, mock_create):
        """Intent creation persists a PENDING Payment row (#16 lifecycle).

        The documented lifecycle (pending -> succeeded | failed) starts here:
        a row is created at checkout time so failed/abandoned attempts are also
        part of the financial audit trail, not only successes.
        """
        mock_create.return_value = MagicMock(
            id="pi_pending_001",
            client_secret="secret",
            amount=10000,
            currency="brl",
        )
        user = UserFactory()
        course = CourseFactory(price=Decimal("100.00"))

        StripeService.create_payment_intent(user, course)

        payment = Payment.objects.get(stripe_payment_intent_id="pi_pending_001")
        assert payment.status == Payment.Status.PENDING
        assert payment.user == user
        assert payment.course == course
        assert payment.amount == Decimal("100.00")

    @patch("apps.payments.services.stripe.PaymentIntent.create")
    def test_pending_payment_is_idempotent_on_retry(self, mock_create):
        """A repeated create-intent (same intent id) does not duplicate the
        PENDING row (#16) — Stripe returns the same intent via idempotency_key.
        """
        mock_create.return_value = MagicMock(
            id="pi_pending_retry",
            client_secret="secret",
            amount=10000,
            currency="brl",
        )
        user = UserFactory()
        course = CourseFactory(price=Decimal("100.00"))

        StripeService.create_payment_intent(user, course)
        StripeService.create_payment_intent(user, course)

        assert (
            Payment.objects.filter(stripe_payment_intent_id="pi_pending_retry").count()
            == 1
        )

    @patch("apps.payments.services.stripe.PaymentIntent.create")
    def test_pending_write_failure_does_not_break_checkout(self, mock_create):
        """A DB failure persisting the PENDING row must not fail checkout (#16).

        The live Stripe intent already exists; the succeeded webhook's
        fallback-create path recovers the row, so create_intent still returns
        the client_secret instead of surfacing a 500.
        """
        mock_create.return_value = MagicMock(
            id="pi_pending_dberr",
            client_secret="secret",
            amount=10000,
            currency="brl",
        )
        user = UserFactory()
        course = CourseFactory(price=Decimal("100.00"))

        with patch(
            "apps.payments.models.Payment.objects.get_or_create",
            side_effect=Exception("db down"),
        ):
            result = StripeService.create_payment_intent(user, course)

        assert result["payment_intent_id"] == "pi_pending_dberr"
        assert result["client_secret"] == "secret"


@pytest.mark.django_db
class TestStripeServiceHandlePaymentSuccess:
    """Tests for StripeService.handle_payment_success."""

    def _make_event_data(self, user, course, pi_id="pi_test_success_001"):
        """Helper: build a Stripe-like event data dict."""
        return {
            "object": {
                "id": pi_id,
                "amount": int(course.price * 100),
                "currency": "brl",
                "metadata": {
                    "user_id": str(user.id),
                    "course_id": str(course.id),
                },
            }
        }

    def test_creates_payment_record_with_succeeded_status(self):
        """Successful payment creates a Payment with status=succeeded."""
        user = UserFactory()
        course = CourseFactory(price=100.00)
        event_data = self._make_event_data(user, course)

        StripeService.handle_payment_success(event_data)

        payment = Payment.objects.get(stripe_payment_intent_id="pi_test_success_001")
        assert payment.status == Payment.Status.SUCCEEDED
        assert payment.user == user
        assert payment.course == course

    def test_creates_enrollment_linked_to_payment(self):
        """Successful payment creates an Enrollment linked to the Payment."""
        user = UserFactory()
        course = CourseFactory(price=100.00)
        event_data = self._make_event_data(user, course)

        enrollment = StripeService.handle_payment_success(event_data)

        assert enrollment.user == user
        assert enrollment.course == course
        assert enrollment.payment is not None
        assert enrollment.payment.status == Payment.Status.SUCCEEDED

    def test_amount_stored_as_exact_decimal(self):
        """Cents→BRL conversion is exact Decimal arithmetic, never float (#14).

        A float (19990 / 100 == 199.90000000000000568…) would not equal the
        exact Decimal even though the DB column later quantizes it, which is
        why the previous ``pytest.approx`` assertion masked the bug.
        """
        user = UserFactory()
        course = CourseFactory(price=Decimal("199.90"))
        event_data = self._make_event_data(user, course, pi_id="pi_cents_test")

        enrollment = StripeService.handle_payment_success(event_data)

        # In-memory value (before DB quantization) must already be exact.
        assert isinstance(enrollment.payment.amount, Decimal)
        assert enrollment.payment.amount == Decimal("199.90")
        payment = Payment.objects.get(stripe_payment_intent_id="pi_cents_test")
        assert payment.amount == Decimal("199.90")

    def test_raises_value_error_for_duplicate_payment_intent(self):
        """Duplicate payment_intent_id raises ValueError (idempotency)."""
        user = UserFactory()
        course = CourseFactory(price=100.00)
        PaymentFactory(
            user=user,
            course=course,
            stripe_payment_intent_id="pi_duplicate_001",
        )
        event_data = self._make_event_data(user, course, pi_id="pi_duplicate_001")

        with pytest.raises(ValueError, match="already processed"):
            StripeService.handle_payment_success(event_data)

    def test_second_succeeded_for_enrolled_user_logs_error(self, caplog):
        """A second succeeded intent (different pi_id) for an already-enrolled
        user is a duplicate charge: logged at ERROR for ops to refund, with
        the enrollment not duplicated and the new Payment still recorded (#12).
        """
        user = UserFactory()
        course = CourseFactory(price=100.00)

        first = self._make_event_data(user, course, pi_id="pi_first")
        StripeService.handle_payment_success(first)

        second = self._make_event_data(user, course, pi_id="pi_second")
        with caplog.at_level(logging.ERROR, logger="apps.payments.services"):
            StripeService.handle_payment_success(second)

        assert Enrollment.objects.filter(user=user, course=course).count() == 1
        assert Payment.objects.filter(stripe_payment_intent_id="pi_second").exists()
        assert any("Duplicate charge" in r.getMessage() for r in caplog.records)
        # The original enrollment's payment link is the audit-trail invariant:
        # it must still point at the first intent, never silently repointed.
        enrollment = Enrollment.objects.get(user=user, course=course)
        assert enrollment.payment.stripe_payment_intent_id == "pi_first"

    def test_payment_and_enrollment_are_atomic(self):
        """If enrollment creation fails, payment is also rolled back."""
        from unittest.mock import patch

        from django.db import IntegrityError

        user = UserFactory()
        course = CourseFactory(price=100.00)
        event_data = self._make_event_data(user, course, pi_id="pi_atomic_test")

        with patch(
            "apps.enrollments.models.Enrollment.objects.get_or_create",
            side_effect=IntegrityError("forced"),
        ):
            with pytest.raises(IntegrityError):
                StripeService.handle_payment_success(event_data)

        # Payment must not exist — transaction was rolled back
        assert not Payment.objects.filter(
            stripe_payment_intent_id="pi_atomic_test"
        ).exists()

    def test_success_transitions_pending_payment_to_succeeded(self):
        """A succeeded webhook transitions the existing PENDING row in place,
        without creating a duplicate Payment (#16 lifecycle).
        """
        user = UserFactory()
        course = CourseFactory(price=Decimal("100.00"))
        PaymentFactory(
            pending=True,
            user=user,
            course=course,
            stripe_payment_intent_id="pi_transition",
            amount=Decimal("100.00"),
        )
        event_data = self._make_event_data(user, course, pi_id="pi_transition")

        enrollment = StripeService.handle_payment_success(event_data)

        payment = Payment.objects.get(stripe_payment_intent_id="pi_transition")
        assert payment.status == Payment.Status.SUCCEEDED
        assert (
            Payment.objects.filter(stripe_payment_intent_id="pi_transition").count()
            == 1
        )
        assert enrollment.payment_id == payment.id

    def test_toctou_create_collision_raises_value_error_not_integrity(self):
        """Concurrent duplicate delivery is idempotent, never IntegrityError.

        When a competing delivery wins the race and our INSERT hits the
        unique constraint, the handler must surface the idempotent ValueError
        (caught by the view → 200), not let IntegrityError escape into a
        spurious 500 that makes Stripe retry (#13).
        """
        user = UserFactory()
        course = CourseFactory(price=100.00)
        event_data = self._make_event_data(user, course, pi_id="pi_toctou")

        with patch(
            "apps.payments.models.Payment.objects.create",
            side_effect=IntegrityError("duplicate key value violates unique"),
        ):
            with pytest.raises(ValueError, match="already processed"):
                StripeService.handle_payment_success(event_data)

    def test_missing_metadata_raises_non_retryable(self):
        """Malformed metadata is non-retryable, not a generic 500 (#18)."""
        from apps.payments.services import NonRetryableWebhookError

        course = CourseFactory(price=100.00)
        event_data = {
            "object": {
                "id": "pi_no_meta",
                "amount": 10000,
                "currency": "brl",
                "metadata": {"course_id": str(course.id)},  # user_id missing
            }
        }

        with pytest.raises(NonRetryableWebhookError):
            StripeService.handle_payment_success(event_data)

    def test_orphaned_user_raises_non_retryable(self):
        """Event referencing a deleted user is non-retryable (#18)."""
        from apps.payments.services import NonRetryableWebhookError

        course = CourseFactory(price=100.00)
        event_data = {
            "object": {
                "id": "pi_orphan_user",
                "amount": 10000,
                "currency": "brl",
                "metadata": {
                    "user_id": "999999",
                    "course_id": str(course.id),
                },
            }
        }

        with pytest.raises(NonRetryableWebhookError):
            StripeService.handle_payment_success(event_data)

    def test_orphaned_course_raises_non_retryable(self):
        """Event referencing a deleted course is non-retryable (#18)."""
        from apps.payments.services import NonRetryableWebhookError

        user = UserFactory()
        event_data = {
            "object": {
                "id": "pi_orphan_course",
                "amount": 10000,
                "currency": "brl",
                "metadata": {
                    "user_id": str(user.id),
                    "course_id": "999999",
                },
            }
        }

        with pytest.raises(NonRetryableWebhookError):
            StripeService.handle_payment_success(event_data)

    def test_amount_mismatch_logs_warning_but_records(self, caplog):
        """Captured amount diverging from course price warns, still records.

        The amount is server-controlled at intent creation, so a divergence
        signals an integration bug or mid-flight price change. We log a
        warning for ops but never refuse a charge that already happened (#27).
        """
        user = UserFactory()
        course = CourseFactory(price=Decimal("100.00"))
        event_data = {
            "object": {
                "id": "pi_amount_mismatch",
                "amount": 5000,  # R$50.00, not the course's R$100.00
                "currency": "brl",
                "metadata": {
                    "user_id": str(user.id),
                    "course_id": str(course.id),
                },
            }
        }

        with caplog.at_level(logging.WARNING, logger="apps.payments.services"):
            StripeService.handle_payment_success(event_data)

        assert any("mismatch" in r.getMessage().lower() for r in caplog.records)
        payment = Payment.objects.get(stripe_payment_intent_id="pi_amount_mismatch")
        assert payment.amount == Decimal("50.00")

    def test_unexpected_currency_logs_warning(self, caplog):
        """A currency other than BRL warns for ops review (#27)."""
        user = UserFactory()
        course = CourseFactory(price=Decimal("100.00"))
        event_data = {
            "object": {
                "id": "pi_currency",
                "amount": 10000,
                "currency": "usd",
                "metadata": {
                    "user_id": str(user.id),
                    "course_id": str(course.id),
                },
            }
        }

        with caplog.at_level(logging.WARNING, logger="apps.payments.services"):
            StripeService.handle_payment_success(event_data)

        assert any("currency" in r.getMessage().lower() for r in caplog.records)


@pytest.mark.django_db
class TestStripeServiceHandlePaymentFailed:
    """Tests for StripeService.handle_payment_failed (#16)."""

    def _event(self, user, course, pi_id, amount=None):
        """Helper: build a Stripe-like payment_failed event data dict."""
        return {
            "object": {
                "id": pi_id,
                "amount": amount or int(course.price * 100),
                "currency": "brl",
                "metadata": {
                    "user_id": str(user.id),
                    "course_id": str(course.id),
                },
            }
        }

    def test_persists_failed_payment_when_no_row_exists(self):
        """A failed event with no prior row records a FAILED Payment (#16)."""
        user = UserFactory()
        course = CourseFactory(price=Decimal("100.00"))

        StripeService.handle_payment_failed(self._event(user, course, "pi_fail_new"))

        payment = Payment.objects.get(stripe_payment_intent_id="pi_fail_new")
        assert payment.status == Payment.Status.FAILED
        assert payment.amount == Decimal("100.00")
        assert payment.user == user
        assert payment.course == course

    def test_transitions_pending_to_failed(self):
        """A failed event transitions the PENDING row in place (#16)."""
        user = UserFactory()
        course = CourseFactory(price=Decimal("100.00"))
        PaymentFactory(
            pending=True,
            user=user,
            course=course,
            stripe_payment_intent_id="pi_fail_pending",
        )

        StripeService.handle_payment_failed(
            self._event(user, course, "pi_fail_pending")
        )

        payment = Payment.objects.get(stripe_payment_intent_id="pi_fail_pending")
        assert payment.status == Payment.Status.FAILED
        assert (
            Payment.objects.filter(stripe_payment_intent_id="pi_fail_pending").count()
            == 1
        )

    def test_does_not_downgrade_succeeded_payment(self, caplog):
        """A failed event after a captured success never downgrades the audit
        trail; it logs a warning and leaves the row SUCCEEDED (#16).
        """
        user = UserFactory()
        course = CourseFactory(price=Decimal("100.00"))
        PaymentFactory(
            user=user,
            course=course,
            stripe_payment_intent_id="pi_fail_succeeded",
        )  # default status is SUCCEEDED

        with caplog.at_level(logging.WARNING, logger="apps.payments.services"):
            StripeService.handle_payment_failed(
                self._event(user, course, "pi_fail_succeeded")
            )

        payment = Payment.objects.get(stripe_payment_intent_id="pi_fail_succeeded")
        assert payment.status == Payment.Status.SUCCEEDED
        assert any("after success" in r.getMessage().lower() for r in caplog.records)


@pytest.mark.django_db
class TestStripeServiceHandleRefund:
    """Tests for StripeService.handle_refund (#16, 16b)."""

    def _charge(self, pi_id, amount=10000, amount_refunded=None, refunded=True):
        """Helper: build a Stripe-like charge.refunded event data dict."""
        return {
            "object": {
                "id": "ch_test",
                "payment_intent": pi_id,
                "amount": amount,
                "amount_refunded": (
                    amount_refunded if amount_refunded is not None else amount
                ),
                "refunded": refunded,
                "currency": "brl",
            }
        }

    def test_full_refund_marks_refunded_and_revokes_access(self):
        """A full refund marks the Payment REFUNDED and deactivates the
        linked enrollment, revoking paid access while keeping the record (#16).
        """
        user = UserFactory()
        course = CourseFactory(price=Decimal("100.00"))
        payment = PaymentFactory(
            user=user,
            course=course,
            stripe_payment_intent_id="pi_refund",
        )  # default SUCCEEDED
        enrollment = EnrollmentFactory(
            user=user, course=course, payment=payment, is_active=True
        )

        StripeService.handle_refund(self._charge("pi_refund"))

        payment.refresh_from_db()
        enrollment.refresh_from_db()
        assert payment.status == Payment.Status.REFUNDED
        assert enrollment.is_active is False

    def test_partial_refund_does_not_mark_refunded(self, caplog):
        """A partial refund is not a full REFUNDED; it warns and keeps the
        status (and access) intact (#16).
        """
        user = UserFactory()
        course = CourseFactory(price=Decimal("100.00"))
        payment = PaymentFactory(
            user=user,
            course=course,
            stripe_payment_intent_id="pi_partial",
        )

        with caplog.at_level(logging.WARNING, logger="apps.payments.services"):
            StripeService.handle_refund(
                self._charge(
                    "pi_partial",
                    amount=10000,
                    amount_refunded=4000,
                    refunded=False,
                )
            )

        payment.refresh_from_db()
        assert payment.status == Payment.Status.SUCCEEDED
        assert any("partial" in r.getMessage().lower() for r in caplog.records)

    def test_refund_is_idempotent_when_already_refunded(self):
        """A redelivered refund for an already-REFUNDED payment is a no-op."""
        user = UserFactory()
        course = CourseFactory(price=Decimal("100.00"))
        PaymentFactory(
            user=user,
            course=course,
            stripe_payment_intent_id="pi_already_refunded",
            status=Payment.Status.REFUNDED,
        )

        # Must not raise.
        StripeService.handle_refund(self._charge("pi_already_refunded"))

        payment = Payment.objects.get(stripe_payment_intent_id="pi_already_refunded")
        assert payment.status == Payment.Status.REFUNDED

    def test_refund_without_enrollment_still_marks_refunded(self):
        """A refund for a payment with no linked enrollment still records
        REFUNDED without error (#16).
        """
        user = UserFactory()
        course = CourseFactory(price=Decimal("100.00"))
        PaymentFactory(
            user=user,
            course=course,
            stripe_payment_intent_id="pi_refund_no_enr",
        )

        StripeService.handle_refund(self._charge("pi_refund_no_enr"))

        payment = Payment.objects.get(stripe_payment_intent_id="pi_refund_no_enr")
        assert payment.status == Payment.Status.REFUNDED

    def test_refund_for_unknown_intent_raises_non_retryable(self):
        """A refund referencing an unknown intent is non-retryable (#18)."""
        from apps.payments.services import NonRetryableWebhookError

        with pytest.raises(NonRetryableWebhookError):
            StripeService.handle_refund(self._charge("pi_does_not_exist"))

    def test_refund_without_payment_intent_raises_non_retryable(self):
        """A charge with no payment_intent reference is non-retryable (#18)."""
        from apps.payments.services import NonRetryableWebhookError

        charge = self._charge("pi_irrelevant")
        charge["object"]["payment_intent"] = None

        with pytest.raises(NonRetryableWebhookError):
            StripeService.handle_refund(charge)


def _stripe_signature_header(payload: bytes, secret: str, timestamp: int) -> str:
    """Build a valid Stripe-Signature header for ``payload`` under ``secret``.

    Mirrors Stripe's scheme: HMAC-SHA256 over ``"{timestamp}.{payload}"`` keyed
    by the webhook secret, formatted as ``t=<ts>,v1=<hex digest>``.
    """
    signed_payload = f"{timestamp}.".encode() + payload
    digest = hmac.new(secret.encode(), signed_payload, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={digest}"


class TestVerifyWebhookSignature:
    """Direct coverage for the security-critical signature path (#17).

    The webhook endpoint tests all mock ``verify_webhook_signature`` away, so
    nothing asserts that ``stripe.Webhook.construct_event`` is called with the
    raw body, the Stripe-Signature header, and STRIPE_WEBHOOK_SECRET. These
    tests patch one level lower (and run a real HMAC round-trip) to lock that in.
    """

    @patch("apps.payments.services.stripe.Webhook.construct_event")
    def test_passes_raw_body_signature_and_secret(self, mock_construct, settings):
        """construct_event receives the raw bytes, the header, and the secret."""
        settings.STRIPE_WEBHOOK_SECRET = "whsec_unit_secret"
        sentinel = object()
        mock_construct.return_value = sentinel
        payload = b'{"id": "evt_1", "type": "ping"}'

        result = StripeService.verify_webhook_signature(payload, "t=1,v1=abc")

        assert result is sentinel
        mock_construct.assert_called_once_with(
            payload, "t=1,v1=abc", "whsec_unit_secret"
        )

    def test_real_hmac_signature_is_accepted(self, settings):
        """A genuinely signed payload verifies end-to-end (no mock)."""
        secret = "whsec_real_hmac_test"
        settings.STRIPE_WEBHOOK_SECRET = secret
        payload = b'{"id": "evt_real", "type": "ping"}'
        header = _stripe_signature_header(payload, secret, int(time.time()))

        event = StripeService.verify_webhook_signature(payload, header)

        assert event["type"] == "ping"

    def test_tampered_signature_is_rejected(self, settings):
        """A bad v1 digest raises SignatureVerificationError (no silent pass)."""
        settings.STRIPE_WEBHOOK_SECRET = "whsec_real_hmac_test"
        payload = b'{"id": "evt_real", "type": "ping"}'
        header = f"t={int(time.time())},v1=deadbeef"

        with pytest.raises(stripe.error.SignatureVerificationError):
            StripeService.verify_webhook_signature(payload, header)

    def test_wrong_secret_is_rejected(self, settings):
        """A signature made with a different secret does not verify."""
        payload = b'{"id": "evt_real", "type": "ping"}'
        header = _stripe_signature_header(payload, "whsec_attacker", int(time.time()))
        settings.STRIPE_WEBHOOK_SECRET = "whsec_real_server_secret"

        with pytest.raises(stripe.error.SignatureVerificationError):
            StripeService.verify_webhook_signature(payload, header)
