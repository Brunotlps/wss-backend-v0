"""Tests for the Stripe webhook endpoint."""

import json
from unittest.mock import MagicMock, patch

import pytest

from apps.courses.factories import CourseFactory
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

        with (
            patch(
                "apps.payments.views.StripeService.verify_webhook_signature",
                return_value=mock_event,
            ),
            patch(
                "apps.payments.views.StripeService.handle_payment_success"
            ) as mock_handle,
        ):
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

        with (
            patch(
                "apps.payments.views.StripeService.verify_webhook_signature",
                return_value=mock_event,
            ),
            patch(
                "apps.payments.views.StripeService.handle_payment_success",
                side_effect=ValueError("pi_webhook_001 already processed"),
            ),
        ):
            response = api_client.post(
                WEBHOOK_URL,
                data=json.dumps(event_data).encode(),
                content_type="application/json",
                HTTP_STRIPE_SIGNATURE="valid_sig",
            )

        # Must return 200 so Stripe doesn't retry
        assert response.status_code == 200

    def test_payment_failed_event_persists_failed_payment(self, api_client):
        """payment_intent.payment_failed persists a FAILED Payment (#16).

        The failure must be part of the financial audit trail, not only a log
        line, and the endpoint still returns 200.
        """
        from apps.payments.models import Payment

        user = UserFactory()
        course = CourseFactory(price=100.00)
        event_data = _make_event(
            "payment_intent.payment_failed", user, course, pi_id="pi_failed_evt"
        )

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
        payment = Payment.objects.get(stripe_payment_intent_id="pi_failed_evt")
        assert payment.status == Payment.Status.FAILED

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

        with (
            patch(
                "apps.payments.views.StripeService.verify_webhook_signature",
                return_value=mock_event,
            ),
            patch(
                "apps.payments.views.StripeService.handle_payment_success",
                side_effect=RuntimeError("unexpected db error"),
            ),
        ):
            response = api_client.post(
                WEBHOOK_URL,
                data=json.dumps(event_data).encode(),
                content_type="application/json",
                HTTP_STRIPE_SIGNATURE="valid_sig",
            )

        assert response.status_code == 500

    def test_failed_event_transient_error_returns_500(self, api_client):
        """A transient error recording a failed payment returns 500 (#16/#18).

        Mirrors the succeeded path: only transient failures retry; non-retryable
        ones ack with 200.
        """
        user = UserFactory()
        course = CourseFactory(price=100.00)
        event_data = _make_event("payment_intent.payment_failed", user, course)

        mock_event = MagicMock()
        mock_event.type = "payment_intent.payment_failed"
        mock_event.data = event_data["data"]

        with (
            patch(
                "apps.payments.views.StripeService.verify_webhook_signature",
                return_value=mock_event,
            ),
            patch(
                "apps.payments.views.StripeService.handle_payment_failed",
                side_effect=RuntimeError("unexpected db error"),
            ),
        ):
            response = api_client.post(
                WEBHOOK_URL,
                data=json.dumps(event_data).encode(),
                content_type="application/json",
                HTTP_STRIPE_SIGNATURE="valid_sig",
            )

        assert response.status_code == 500

    def test_charge_refunded_event_marks_refunded(self, api_client):
        """charge.refunded marks the Payment REFUNDED and returns 200 (#16)."""
        from apps.payments.factories import PaymentFactory
        from apps.payments.models import Payment

        payment = PaymentFactory(stripe_payment_intent_id="pi_refund_evt")

        event_data = {
            "id": "evt_refund",
            "type": "charge.refunded",
            "data": {
                "object": {
                    "id": "ch_refund_evt",
                    "payment_intent": "pi_refund_evt",
                    "amount": 10000,
                    "amount_refunded": 10000,
                    "refunded": True,
                    "currency": "brl",
                }
            },
        }

        mock_event = MagicMock()
        mock_event.type = "charge.refunded"
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
        payment.refresh_from_db()
        assert payment.status == Payment.Status.REFUNDED

    def test_failed_event_malformed_metadata_returns_200(self, api_client):
        """A failed event with unresolvable metadata is non-retryable → 200."""
        course = CourseFactory(price=100.00)
        event_data = {
            "id": "evt_failed_no_meta",
            "type": "payment_intent.payment_failed",
            "data": {
                "object": {
                    "id": "pi_failed_no_meta",
                    "amount": int(course.price * 100),
                    "currency": "brl",
                    "metadata": {},  # user_id / course_id missing
                }
            },
        }

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

    def test_charge_refunded_unknown_intent_returns_200(self, api_client):
        """A refund for an unknown intent is non-retryable → 200 (#18)."""
        event_data = {
            "id": "evt_refund_unknown",
            "type": "charge.refunded",
            "data": {
                "object": {
                    "id": "ch_unknown",
                    "payment_intent": "pi_never_seen",
                    "amount": 10000,
                    "amount_refunded": 10000,
                    "refunded": True,
                    "currency": "brl",
                }
            },
        }

        mock_event = MagicMock()
        mock_event.type = "charge.refunded"
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

    def test_charge_refunded_transient_error_returns_500(self, api_client):
        """A transient error processing a refund returns 500 (#16/#18)."""
        event_data = {
            "id": "evt_refund_err",
            "type": "charge.refunded",
            "data": {"object": {"id": "ch_err", "payment_intent": "pi_err"}},
        }

        mock_event = MagicMock()
        mock_event.type = "charge.refunded"
        mock_event.data = event_data["data"]

        with (
            patch(
                "apps.payments.views.StripeService.verify_webhook_signature",
                return_value=mock_event,
            ),
            patch(
                "apps.payments.views.StripeService.handle_refund",
                side_effect=RuntimeError("unexpected db error"),
            ),
        ):
            response = api_client.post(
                WEBHOOK_URL,
                data=json.dumps(event_data).encode(),
                content_type="application/json",
                HTTP_STRIPE_SIGNATURE="valid_sig",
            )

        assert response.status_code == 500

    def test_malformed_metadata_returns_200_not_500(self, api_client):
        """Missing metadata is non-retryable → 200 so Stripe stops (#18).

        A signature-valid event whose metadata can never resolve must not
        loop as a 500 redelivered for days; it is logged and acknowledged.
        """
        course = CourseFactory(price=100.00)
        event_data = {
            "id": "evt_no_meta",
            "type": "payment_intent.succeeded",
            "data": {
                "object": {
                    "id": "pi_no_meta",
                    "amount": int(course.price * 100),
                    "currency": "brl",
                    "metadata": {},  # user_id / course_id missing
                }
            },
        }

        mock_event = MagicMock()
        mock_event.type = "payment_intent.succeeded"
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

    def test_orphaned_event_returns_200_not_500(self, api_client):
        """Event for a deleted user/course is non-retryable → 200 (#18)."""
        course = CourseFactory(price=100.00)
        event_data = {
            "id": "evt_orphan",
            "type": "payment_intent.succeeded",
            "data": {
                "object": {
                    "id": "pi_orphan",
                    "amount": int(course.price * 100),
                    "currency": "brl",
                    "metadata": {
                        "user_id": "999999",  # no such user
                        "course_id": str(course.id),
                    },
                }
            },
        }

        mock_event = MagicMock()
        mock_event.type = "payment_intent.succeeded"
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
