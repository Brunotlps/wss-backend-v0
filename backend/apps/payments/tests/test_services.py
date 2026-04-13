"""Tests for StripeService business logic."""

import pytest
from unittest.mock import MagicMock, patch

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

    def test_amount_converted_from_cents_to_brl(self):
        """Amount in cents (Stripe) is stored as BRL decimal."""
        user = UserFactory()
        course = CourseFactory(price=199.90)
        event_data = self._make_event_data(user, course, pi_id="pi_cents_test")

        StripeService.handle_payment_success(event_data)

        payment = Payment.objects.get(stripe_payment_intent_id="pi_cents_test")
        assert float(payment.amount) == pytest.approx(199.90, rel=1e-2)

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
