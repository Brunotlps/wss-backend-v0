"""Tests for the Payment model."""

import pytest

from apps.courses.factories import CourseFactory
from apps.payments.factories import PaymentFactory
from apps.payments.models import Payment
from apps.users.factories import UserFactory


@pytest.mark.django_db
class TestPaymentModel:
    """Test suite for the Payment model."""

    def test_create_payment_with_valid_data(self):
        """Payment is created with expected defaults."""
        payment = PaymentFactory()
        assert payment.pk is not None
        assert payment.status == Payment.Status.SUCCEEDED
        assert payment.currency == "brl"

    def test_str_returns_readable_representation(self):
        """__str__ includes user email, course title and status."""
        payment = PaymentFactory()
        result = str(payment)
        assert payment.user.email in result
        assert payment.course.title in result
        assert payment.status in result

    def test_is_succeeded_returns_true_for_succeeded_status(self):
        """is_succeeded property returns True when status is succeeded."""
        payment = PaymentFactory(status=Payment.Status.SUCCEEDED)
        assert payment.is_succeeded is True

    def test_is_succeeded_returns_false_for_pending_status(self):
        """is_succeeded property returns False when status is pending."""
        payment = PaymentFactory.build(status=Payment.Status.PENDING)
        assert payment.is_succeeded is False

    def test_is_succeeded_returns_false_for_failed_status(self):
        """is_succeeded property returns False when status is failed."""
        payment = PaymentFactory.build(status=Payment.Status.FAILED)
        assert payment.is_succeeded is False

    def test_stripe_payment_intent_id_is_unique(self):
        """Two payments cannot share the same stripe_payment_intent_id."""
        from django.db import IntegrityError

        PaymentFactory(stripe_payment_intent_id="pi_unique_123")
        with pytest.raises(IntegrityError):
            PaymentFactory(stripe_payment_intent_id="pi_unique_123")

    def test_ordering_is_newest_first(self):
        """Payments are ordered by -created_at."""
        user = UserFactory()
        p1 = PaymentFactory(user=user)
        p2 = PaymentFactory(user=user)
        payments = list(Payment.objects.filter(user=user))
        assert payments[0].pk == p2.pk

    def test_payment_linked_to_enrollment_via_reverse(self):
        """Payment can access its enrollment via reverse relation."""
        from apps.enrollments.factories import EnrollmentFactory

        payment = PaymentFactory()
        enrollment = EnrollmentFactory(payment=payment)
        assert payment.enrollment == enrollment

    def test_status_choices_are_valid(self):
        """All defined Status choices are accepted by the model."""
        user = UserFactory()
        course = CourseFactory()
        for status_value, _ in Payment.Status.choices:
            p = PaymentFactory(
                user=user,
                course=course,
                status=status_value,
            )
            assert p.status == status_value
