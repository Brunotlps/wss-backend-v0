"""Tests for payment endpoint throttling."""

import pytest
from unittest.mock import MagicMock, patch

from django.core.cache import cache
from django.urls import reverse
from rest_framework import status

from apps.courses.factories import CourseFactory


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear Django cache before and after each test to reset throttle counters."""
    cache.clear()
    yield
    cache.clear()


@pytest.mark.django_db
class TestPaymentIntentThrottling:
    """Tests for rate limiting on POST /api/payments/create-intent/."""

    URL = reverse("payment-create-intent")

    @patch("apps.payments.services.stripe.PaymentIntent.create")
    def test_allows_up_to_10_payment_intents_per_day(self, mock_create, auth_client):
        """Authenticated users can create up to 10 Payment Intents per day."""
        mock_create.return_value = MagicMock(
            id="pi_test_123",
            client_secret="pi_test_123_secret_abc",
            amount=9990,
            currency="brl",
        )

        course = CourseFactory(price=99.90)
        payload = {"course_id": course.id}

        for _ in range(10):
            response = auth_client.post(self.URL, payload, format="json")
            assert response.status_code == status.HTTP_200_OK
            assert "client_secret" in response.data

        response = auth_client.post(self.URL, payload, format="json")
        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS

    @patch("apps.payments.services.stripe.PaymentIntent.create")
    def test_different_users_have_separate_limits(self, mock_create, api_client):
        """Each authenticated user has their own independent 10/day limit."""
        mock_create.return_value = MagicMock(
            id="pi_test_456",
            client_secret="pi_test_456_secret_xyz",
            amount=9990,
            currency="brl",
        )

        from apps.users.factories import UserFactory

        course = CourseFactory(price=99.90)
        payload = {"course_id": course.id}

        user1 = UserFactory()
        api_client.force_authenticate(user1)
        for _ in range(10):
            api_client.post(self.URL, payload, format="json")

        user2 = UserFactory()
        api_client.force_authenticate(user2)
        response = api_client.post(self.URL, payload, format="json")
        assert response.status_code == status.HTTP_200_OK
