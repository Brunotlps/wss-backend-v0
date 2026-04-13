"""Tests for the Stripe webhook endpoint."""

import json
import pytest
from unittest.mock import MagicMock, patch

from apps.courses.factories import CourseFactory
from apps.payments.factories import PaymentFactory
from apps.payments.models import Payment
from apps.users.factories import UserFactory


WEBHOOK_URL = "/api/webhooks/stripe/"


def _make_event(event_type, user, course, pi_id="pi_webhook_001"):
    """Build a minimal Stripe-like event payload."""
    return {
        "id": f"evt_{pi_id}",
        "type": event_type,
        "data": {
            "object": {
                "id": pi_id,
                "amount": int(course.price * 100),
                "currency": "brl",
                "metadata": {
                    "user_id": str(user.id),
                    "course_id": str(course.id),
                },
            }
        },
    }


@pytest.mark.django_db
class TestStripeWebhookView:
    """Tests for POST /api/webhooks/stripe/."""

    def test_invalid_signature_returns_400(self, api_client):
        """Request with invalid Stripe signature is rejected."""
        with patch(
            "apps.payments.views.StripeService.verify_webhook_signature"
        ) as mock_verify:
            import stripe

            mock_verify.side_effect = stripe.error.SignatureVerificationError(
                "invalid", "sig"
            )
            response = api_client.post(
                WEBHOOK_URL,
                data=b'{"type": "test"}',
                content_type="application/json",
                HTTP_STRIPE_SIGNATURE="invalid_sig",
            )
        assert response.status_code == 400

    def test_payment_succeeded_creates_enrollment(self, api_client):
        """payment_intent.succeeded event triggers enrollment creation."""
        user = UserFactory()
        course = CourseFactory(price=100.00)
        event_data = _make_event("payment_intent.succeeded", user, course)

        mock_event = MagicMock()
        mock_event.type = "payment_intent.succeeded"
        mock_event.data = event_data["data"]

        with patch(
            "apps.payments.views.StripeService.verify_webhook_signature",
            return_value=mock_event,
        ), patch(
            "apps.payments.views.StripeService.handle_payment_success"
        ) as mock_handle:
            response = api_client.post(
                WEBHOOK_URL,
                data=json.dumps(event_data).encode(),
                content_type="application/json",
                HTTP_STRIPE_SIGNATURE="valid_sig",
            )

        assert response.status_code == 200
        mock_handle.assert_called_once_with(event_data["data"])

    def test_duplicate_webhook_returns_200_idempotent(self, api_client):
        """Duplicate payment_intent.succeeded returns 200 without error."""
        user = UserFactory()
        course = CourseFactory(price=100.00)
        event_data = _make_event("payment_intent.succeeded", user, course)

        mock_event = MagicMock()
        mock_event.type = "payment_intent.succeeded"
        mock_event.data = event_data["data"]

        with patch(
            "apps.payments.views.StripeService.verify_webhook_signature",
            return_value=mock_event,
        ), patch(
            "apps.payments.views.StripeService.handle_payment_success",
            side_effect=ValueError("pi_webhook_001 already processed"),
        ):
            response = api_client.post(
                WEBHOOK_URL,
                data=json.dumps(event_data).encode(),
                content_type="application/json",
                HTTP_STRIPE_SIGNATURE="valid_sig",
            )

        # Must return 200 so Stripe doesn't retry
        assert response.status_code == 200

    def test_payment_failed_event_returns_200(self, api_client):
        """payment_intent.payment_failed event is handled gracefully."""
        user = UserFactory()
        course = CourseFactory(price=100.00)
        event_data = _make_event("payment_intent.payment_failed", user, course)

        mock_event = MagicMock()
        mock_event.type = "payment_intent.payment_failed"
        mock_event.data = event_data["data"]

        with patch(
            "apps.payments.views.StripeService.verify_webhook_signature",
            return_value=mock_event,
        ):
            response = api_client.post(
                WEBHOOK_URL,
                data=json.dumps(event_data).encode(),
                content_type="application/json",
                HTTP_STRIPE_SIGNATURE="valid_sig",
            )

        assert response.status_code == 200

    def test_unknown_event_type_returns_200(self, api_client):
        """Unrecognised event types are silently ignored (returns 200)."""
        mock_event = MagicMock()
        mock_event.type = "customer.subscription.created"
        mock_event.data = {"object": {}}

        with patch(
            "apps.payments.views.StripeService.verify_webhook_signature",
            return_value=mock_event,
        ):
            response = api_client.post(
                WEBHOOK_URL,
                data=b"{}",
                content_type="application/json",
                HTTP_STRIPE_SIGNATURE="valid_sig",
            )

        assert response.status_code == 200

    def test_webhook_accessible_without_authentication(self, api_client):
        """Webhook endpoint does not require JWT authentication."""
        mock_event = MagicMock()
        mock_event.type = "ping"
        mock_event.data = {"object": {}}

        with patch(
            "apps.payments.views.StripeService.verify_webhook_signature",
            return_value=mock_event,
        ):
            # No credentials attached to api_client
            response = api_client.post(
                WEBHOOK_URL,
                data=b"{}",
                content_type="application/json",
                HTTP_STRIPE_SIGNATURE="valid_sig",
            )

        # 200 (not 401) confirms endpoint is public
        assert response.status_code == 200

    def test_internal_error_returns_500(self, api_client):
        """Unexpected exception during payment processing returns 500."""
        user = UserFactory()
        course = CourseFactory(price=100.00)
        event_data = _make_event("payment_intent.succeeded", user, course)

        mock_event = MagicMock()
        mock_event.type = "payment_intent.succeeded"
        mock_event.data = event_data["data"]

        with patch(
            "apps.payments.views.StripeService.verify_webhook_signature",
            return_value=mock_event,
        ), patch(
            "apps.payments.views.StripeService.handle_payment_success",
            side_effect=RuntimeError("unexpected db error"),
        ):
            response = api_client.post(
                WEBHOOK_URL,
                data=json.dumps(event_data).encode(),
                content_type="application/json",
                HTTP_STRIPE_SIGNATURE="valid_sig",
            )

        assert response.status_code == 500
