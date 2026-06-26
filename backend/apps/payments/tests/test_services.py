"""Tests for StripeService business logic."""

import logging
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.db import IntegrityError

import pytest

from apps.courses.factories import CourseFactory
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
