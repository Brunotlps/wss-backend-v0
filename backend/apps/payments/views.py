"""
Payment API views for WSS Backend.

Endpoints:
    GET  /api/payments/                    → List own payments
    GET  /api/payments/{id}/              → Retrieve single payment
    POST /api/payments/create-intent/     → Create Stripe Payment Intent
    POST /api/webhooks/stripe/            → Stripe webhook handler (public)
"""

import logging

from django.http import HttpResponse
from django.shortcuts import get_object_or_404

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

import stripe

from apps.courses.models import Course
from apps.enrollments.models import Enrollment

from .models import Payment
from .permissions import IsPaymentOwner
from .serializers import PaymentIntentRequestSerializer, PaymentSerializer
from .services import NonRetryableWebhookError, StripeService
from .throttles import PaymentIntentRateThrottle

logger = logging.getLogger(__name__)


class PaymentViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for Payment records (read-only).

    Payments are never created directly via this ViewSet — they are created
    through the create-intent flow and confirmed via Stripe webhooks.

    Endpoints:
        GET  /api/payments/                   → list own payments (staff: all)
        GET  /api/payments/{id}/              → retrieve single payment
        POST /api/payments/create-intent/     → create Stripe PaymentIntent

    Permissions:
        - Requires authentication
        - Students see only their own payments
        - Staff see all payments
    """

    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated, IsPaymentOwner]

    def get_throttles(self):
        """Apply payment intent throttle only to the create-intent action."""
        if self.action == "create_intent":
            return [PaymentIntentRateThrottle()]
        return super().get_throttles()

    def get_queryset(self):
        """Staff see all payments; others see only their own."""
        user = self.request.user
        qs = Payment.objects.select_related("user", "course")
        if user.is_staff:
            return qs
        return qs.filter(user=user)

    @action(detail=False, methods=["post"], url_path="create-intent")
    def create_intent(self, request):
        """
        Create a Stripe PaymentIntent for a paid course purchase.

        POST /api/payments/create-intent/
        Body: {"course_id": <int>}

        Returns:
            200: {client_secret, payment_intent_id, amount, currency}
            400: course_id missing | course is free
            404: course not found
            409: already enrolled in this course
            500: Stripe API error
        """
        serializer = PaymentIntentRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST,
            )

        course_id = serializer.validated_data["course_id"]
        course = get_object_or_404(Course, id=course_id)

        if course.price == 0:
            return Response(
                {"detail": "Free courses do not require payment."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if Enrollment.objects.filter(user=request.user, course=course).exists():
            return Response(
                {"detail": "Already enrolled in this course."},
                status=status.HTTP_409_CONFLICT,
            )

        try:
            result = StripeService.create_payment_intent(
                user=request.user,
                course=course,
            )
        except stripe.error.StripeError as exc:
            logger.error(
                "Stripe error for user %s, course %s: %s",
                request.user.id,
                course_id,
                exc,
            )
            return Response(
                {"detail": "Payment processing failed. Please try again."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(result, status=status.HTTP_200_OK)


class StripeWebhookView(APIView):
    """
    Stripe webhook receiver.

    POST /api/webhooks/stripe/

    Handles:
        payment_intent.succeeded      → transitions Payment to SUCCEEDED + enrolls
        payment_intent.payment_failed → records a FAILED Payment (audit trail)

    Security:
        - No Django authentication (Stripe cannot log in as a user)
        - authentication_classes=[] prevents DRF from consuming request.body
          before we can read the raw bytes needed for HMAC signature verification
        - Signature verified via STRIPE_WEBHOOK_SECRET on every request
    """

    permission_classes = [AllowAny]
    authentication_classes = []
    # Exempt from the global anon throttle: Stripe retries from a few fixed
    # egress IPs that would share one bucket; signature verification guards it.
    throttle_classes = []

    def post(self, request):
        """Handle an incoming Stripe webhook event."""
        payload = request.body
        signature = request.META.get("HTTP_STRIPE_SIGNATURE", "")

        try:
            event = StripeService.verify_webhook_signature(payload, signature)
        except stripe.error.SignatureVerificationError:
            logger.warning("Webhook signature verification failed")
            return HttpResponse(status=400)

        payment_intent = event.data.get("object", {})
        pi_id = payment_intent.get("id", "unknown")
        metadata = payment_intent.get("metadata", {})

        logger.info(
            "Webhook received: event=%s, payment_intent=%s, "
            "user_id=%s, course_id=%s",
            event.type,
            pi_id,
            metadata.get("user_id", "N/A"),
            metadata.get("course_id", "N/A"),
        )

        if event.type == "payment_intent.succeeded":
            status_code = self._process_succeeded(event, pi_id, metadata)
        elif event.type == "payment_intent.payment_failed":
            status_code = self._process_failed(event, pi_id, metadata)
        else:
            status_code = 200

        return HttpResponse(status=status_code)

    def _process_succeeded(self, event, pi_id, metadata) -> int:
        """Process payment_intent.succeeded; return the HTTP status to send.

        Maps the handler outcome to a status: idempotent duplicate (#13) and
        non-retryable malformed/orphaned events (#18) ack with 200; only a
        transient failure returns 500 so Stripe retries.
        """
        try:
            enrollment = StripeService.handle_payment_success(event.data)
            logger.info(
                "Payment processed: payment_intent=%s, "
                "enrollment_id=%s, user_id=%s, course_id=%s",
                pi_id,
                enrollment.id,
                enrollment.user_id,
                enrollment.course_id,
            )
        except ValueError as exc:
            # Idempotent duplicate (#13) — already processed.
            logger.info("Duplicate webhook ignored: %s", exc)
        except NonRetryableWebhookError as exc:
            # Malformed/orphaned event (#18) — log ERROR, ack with 200 so
            # Stripe stops redelivering it for days.
            logger.error(
                "Non-retryable webhook dropped: payment_intent=%s, "
                "user_id=%s, course_id=%s, error=%s",
                pi_id,
                metadata.get("user_id", "N/A"),
                metadata.get("course_id", "N/A"),
                exc,
            )
        except Exception as exc:
            # Transient failure (e.g. DB error) — 500 so Stripe retries.
            logger.error(
                "Error processing payment: payment_intent=%s, "
                "user_id=%s, course_id=%s, error=%s",
                pi_id,
                metadata.get("user_id", "N/A"),
                metadata.get("course_id", "N/A"),
                exc,
                exc_info=True,
            )
            return 500
        return 200

    def _process_failed(self, event, pi_id, metadata) -> int:
        """Process payment_intent.payment_failed; return the HTTP status (#16).

        Persists the failure in the audit trail. Non-retryable events ack with
        200; only a transient failure returns 500.
        """
        try:
            payment = StripeService.handle_payment_failed(event.data)
            logger.warning(
                "Payment failed recorded: payment_intent=%s, payment_id=%s, "
                "user_id=%s, course_id=%s",
                pi_id,
                payment.id,
                metadata.get("user_id", "N/A"),
                metadata.get("course_id", "N/A"),
            )
        except NonRetryableWebhookError as exc:
            # Malformed/orphaned event (#18) — log ERROR, ack with 200.
            logger.error(
                "Non-retryable payment_failed dropped: payment_intent=%s, error=%s",
                pi_id,
                exc,
            )
        except Exception as exc:
            # Transient failure — 500 so Stripe retries.
            logger.error(
                "Error recording failed payment: payment_intent=%s, error=%s",
                pi_id,
                exc,
                exc_info=True,
            )
            return 500
        return 200
