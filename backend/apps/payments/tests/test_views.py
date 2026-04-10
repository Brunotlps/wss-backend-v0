"""Tests for Payment API endpoints."""

import pytest
from unittest.mock import MagicMock, patch
from rest_framework import status

from apps.courses.factories import CourseFactory
from apps.enrollments.factories import EnrollmentFactory
from apps.payments.factories import PaymentFactory
from apps.payments.models import Payment
from apps.users.factories import UserFactory


@pytest.mark.django_db
class TestPaymentListView:
    """Tests for GET /api/payments/."""

    URL = "/api/payments/"

    def test_list_requires_authentication(self, api_client):
        """Unauthenticated requests are rejected with 401."""
        response = api_client.get(self.URL)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_student_sees_only_own_payments(self, auth_client):
        """Student sees only their own payment records."""
        PaymentFactory(user=auth_client.user)
        PaymentFactory()  # Another user's payment
        response = auth_client.get(self.URL)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1

    def test_staff_sees_all_payments(self, staff_client):
        """Staff can see all payments."""
        PaymentFactory.create_batch(3)
        response = staff_client.get(self.URL)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 3

    def test_response_contains_expected_fields(self, auth_client):
        """Payment list response contains the expected fields."""
        PaymentFactory(user=auth_client.user)
        response = auth_client.get(self.URL)
        result = response.data["results"][0]
        assert "id" in result
        assert "amount" in result
        assert "status" in result
        assert "stripe_payment_intent_id" in result


@pytest.mark.django_db
class TestPaymentDetailView:
    """Tests for GET /api/payments/{id}/."""

    URL = "/api/payments/"

    def test_owner_can_retrieve_own_payment(self, auth_client):
        """Payment owner can retrieve their payment."""
        payment = PaymentFactory(user=auth_client.user)
        response = auth_client.get(f"{self.URL}{payment.pk}/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["id"] == payment.pk

    def test_cannot_retrieve_other_user_payment(self, auth_client):
        """Student cannot retrieve another user's payment."""
        other_payment = PaymentFactory()
        response = auth_client.get(f"{self.URL}{other_payment.pk}/")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_staff_can_retrieve_any_payment(self, staff_client):
        """Staff can retrieve any payment."""
        payment = PaymentFactory()
        response = staff_client.get(f"{self.URL}{payment.pk}/")
        assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestCreatePaymentIntentView:
    """Tests for POST /api/payments/create-intent/."""

    URL = "/api/payments/create-intent/"

    def test_requires_authentication(self, api_client):
        """Unauthenticated requests are rejected with 401."""
        course = CourseFactory()
        response = api_client.post(self.URL, {"course_id": course.pk})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_missing_course_id_returns_400(self, auth_client):
        """Missing course_id in body returns 400."""
        response = auth_client.post(self.URL, {})
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "course_id" in response.data

    def test_nonexistent_course_returns_404(self, auth_client):
        """Non-existent course_id returns 404."""
        response = auth_client.post(self.URL, {"course_id": 99999})
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_free_course_returns_400(self, auth_client):
        """Free course (price=0) cannot have a payment intent."""
        course = CourseFactory(price=0)
        response = auth_client.post(self.URL, {"course_id": course.pk})
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "free" in response.data["detail"].lower()

    def test_already_enrolled_returns_400(self, auth_client):
        """User already enrolled in course returns 400."""
        course = CourseFactory(price=100)
        EnrollmentFactory(user=auth_client.user, course=course)
        response = auth_client.post(self.URL, {"course_id": course.pk})
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "enrolled" in response.data["detail"].lower()

    @patch("apps.payments.views.StripeService.create_payment_intent")
    def test_successful_intent_returns_200_with_client_secret(
        self, mock_create_intent, auth_client
    ):
        """Valid paid course returns 200 with client_secret."""
        mock_create_intent.return_value = {
            "client_secret": "pi_test_secret_xyz",
            "payment_intent_id": "pi_test_xyz",
            "amount": 10000,
            "currency": "brl",
        }
        course = CourseFactory(price=100)
        response = auth_client.post(self.URL, {"course_id": course.pk})
        assert response.status_code == status.HTTP_200_OK
        assert response.data["client_secret"] == "pi_test_secret_xyz"
        assert response.data["payment_intent_id"] == "pi_test_xyz"

    @patch("apps.payments.views.StripeService.create_payment_intent")
    def test_stripe_api_error_returns_500(self, mock_create_intent, auth_client):
        """Stripe API failure returns 500 without leaking details."""
        import stripe

        mock_create_intent.side_effect = stripe.error.APIConnectionError("down")
        course = CourseFactory(price=100)
        response = auth_client.post(self.URL, {"course_id": course.pk})
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "detail" in response.data
        # Must not leak Stripe internals
        assert "down" not in str(response.data)
