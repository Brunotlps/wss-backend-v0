"""
Stripe payment service layer for WSS Backend.

This module encapsulates all Stripe API interactions, keeping views thin
and business logic centralized and testable.

Classes:
    StripeService: Static methods for Stripe Payment Intent operations.
"""

import logging
from typing import Any, Dict

import stripe
from django.conf import settings
from django.db import transaction

logger = logging.getLogger(__name__)


class StripeService:
    """
    Service layer for Stripe payment operations.

    All methods are static to allow easy mocking in tests without
    instantiating the class. Stripe API key is set at module level
    from Django settings.

    Methods:
        create_payment_intent: Create a Stripe PaymentIntent for a course purchase.
        verify_webhook_signature: Validate incoming Stripe webhook payload.
        handle_payment_success: Process a succeeded payment and create enrollment.
    """

    @staticmethod
    def _get_stripe_key() -> str:
        """Return Stripe secret key from settings."""
        return getattr(settings, "STRIPE_SECRET_KEY", "")

    @staticmethod
    def create_payment_intent(
        user: Any,
        course: Any,
    ) -> Dict[str, Any]:
        """
        Create a Stripe PaymentIntent for a course purchase.

        Args:
            user: Authenticated User instance initiating the purchase.
            course: Course instance being purchased.

        Returns:
            Dict containing:
                - client_secret: Stripe client secret for frontend confirmation
                - payment_intent_id: Stripe PI ID
                - amount: Amount in cents
                - currency: Currency code

        Raises:
            stripe.error.StripeError: If the Stripe API call fails.
        """
        stripe.api_key = StripeService._get_stripe_key()

        try:
            intent = stripe.PaymentIntent.create(
                amount=int(course.price * 100),  # Convert BRL to cents
                currency="brl",
                metadata={
                    "user_id": user.id,
                    "user_email": user.email,
                    "course_id": course.id,
                    "course_title": course.title,
                },
                description=f"Enrollment: {course.title}",
                automatic_payment_methods={
                    "enabled": True,
                    "allow_redirects": "never",
                },
            )

            logger.info(
                "Payment intent created: %s for user %s, course %s",
                intent.id,
                user.id,
                course.id,
            )

            return {
                "client_secret": intent.client_secret,
                "payment_intent_id": intent.id,
                "amount": intent.amount,
                "currency": intent.currency,
            }

        except stripe.error.StripeError as exc:
            logger.error("Stripe error creating payment intent: %s", exc)
            raise

    @staticmethod
    def verify_webhook_signature(
        payload: bytes,
        signature: str,
    ) -> Any:
        """
        Verify the Stripe webhook signature and return the parsed event.

        Args:
            payload: Raw request body bytes.
            signature: Value of the Stripe-Signature header.

        Returns:
            Verified stripe.Event object.

        Raises:
            stripe.error.SignatureVerificationError: If signature is invalid.
        """
        stripe.api_key = StripeService._get_stripe_key()
        webhook_secret = getattr(settings, "STRIPE_WEBHOOK_SECRET", "")

        event = stripe.Webhook.construct_event(
            payload,
            signature,
            webhook_secret,
        )
        return event

    @staticmethod
    @transaction.atomic
    def handle_payment_success(event_data: Dict[str, Any]) -> Any:
        """
        Handle a payment_intent.succeeded webhook event.

        Creates a Payment record (status=succeeded) and a linked Enrollment.
        Uses atomic transaction so both records are committed together.

        Args:
            event_data: The ``data`` dict from the Stripe webhook event
                        (i.e. ``event.data``).

        Returns:
            Created Enrollment instance.

        Raises:
            ValueError: If payment was already processed or required data is missing.
        """
        # Import inside method to avoid circular imports
        from django.contrib.auth import get_user_model

        from apps.courses.models import Course
        from apps.enrollments.models import Enrollment

        User = get_user_model()
        from .models import Payment

        payment_intent = event_data["object"]
        metadata = payment_intent.get("metadata", {})

        user_id = int(metadata["user_id"])
        course_id = int(metadata["course_id"])
        payment_intent_id = payment_intent["id"]

        # Idempotency: skip already-processed intents
        if Payment.objects.filter(
            stripe_payment_intent_id=payment_intent_id
        ).exists():
            raise ValueError(
                f"Payment {payment_intent_id} already processed"
            )

        user = User.objects.get(id=user_id)
        course = Course.objects.get(id=course_id)

        # Create payment record
        payment = Payment.objects.create(
            user=user,
            course=course,
            amount=payment_intent["amount"] / 100,  # Convert cents to BRL
            currency=payment_intent.get("currency", "brl"),
            stripe_payment_intent_id=payment_intent_id,
            status=Payment.Status.SUCCEEDED,
        )

        # Create enrollment
        enrollment, created = Enrollment.objects.get_or_create(
            user=user,
            course=course,
            defaults={"payment": payment},
        )

        if not created and enrollment.payment is None:
            enrollment.payment = payment
            enrollment.save(update_fields=["payment"])

        logger.info(
            "Enrollment %s %s after payment %s",
            enrollment.id,
            "created" if created else "updated",
            payment.id,
        )

        return enrollment
