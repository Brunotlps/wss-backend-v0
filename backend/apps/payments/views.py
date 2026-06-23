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
from .services import StripeService
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
        payment_intent.succeeded      → creates Payment + Enrollment records
        payment_intent.payment_failed → logs the failure

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

        event_type = event.type
        payment_intent = event.data.get("object", {})
        pi_id = payment_intent.get("id", "unknown")
        metadata = payment_intent.get("metadata", {})

        logger.info(
            "Webhook received: event=%s, payment_intent=%s, "
            "user_id=%s, course_id=%s",
            event_type,
            pi_id,
            metadata.get("user_id", "N/A"),
            metadata.get("course_id", "N/A"),
        )

        if event_type == "payment_intent.succeeded":
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
                logger.info("Duplicate webhook ignored: %s", exc)
            except Exception as exc:
                logger.error(
                    "Error processing payment: payment_intent=%s, "
                    "user_id=%s, course_id=%s, error=%s",
                    pi_id,
                    metadata.get("user_id", "N/A"),
                    metadata.get("course_id", "N/A"),
                    exc,
                    exc_info=True,
                )
                return HttpResponse(status=500)

        elif event_type == "payment_intent.payment_failed":
            logger.warning(
                "Payment failed: payment_intent=%s, " "user_id=%s, course_id=%s",
                pi_id,
                metadata.get("user_id", "N/A"),
                metadata.get("course_id", "N/A"),
            )

        return HttpResponse(status=200)
