"""
Stripe payment service layer for WSS Backend.

This module encapsulates all Stripe API interactions, keeping views thin
and business logic centralized and testable.

Classes:
    StripeService: Static methods for Stripe Payment Intent operations.
"""

import logging
from decimal import Decimal
from typing import Any, Dict

from django.conf import settings
from django.db import IntegrityError, transaction

import stripe

logger = logging.getLogger(__name__)


class NonRetryableWebhookError(Exception):
    """A signature-valid webhook event that can never be processed.

    Raised when the payload is structurally unusable (malformed metadata) or
    references data that no longer exists (deleted user/course). Retrying can
    never help, so the caller logs at ERROR (for alerting) and returns HTTP
    200 to stop Stripe from redelivering the event for days (#18).
    """


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
                # Deterministic key: repeated calls for the same user+course
                # (second tab, frontend retry) return the SAME intent instead
                # of a second live one, preventing a double charge (#12).
                idempotency_key=f"pi:{user.id}:{course.id}",
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
    def _resolve_succeeded_intent(
        payment_intent: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Validate a succeeded PaymentIntent payload and resolve its refs.

        Parses the metadata, loads the referenced user/course and computes the
        exact Decimal amount. Structurally unusable or orphaned events raise
        NonRetryableWebhookError so the caller can acknowledge them with 200
        instead of looping on retries (#18).

        Args:
            payment_intent: The ``object`` dict of the Stripe event.

        Returns:
            Dict with keys: user, course, payment_intent_id, amount, currency.

        Raises:
            NonRetryableWebhookError: If metadata is malformed or the
                referenced user/course no longer exists.
        """
        # Import inside method to avoid circular imports
        from django.contrib.auth import get_user_model

        from apps.courses.models import Course

        User = get_user_model()

        metadata = payment_intent.get("metadata", {})

        # Non-retryable: malformed metadata or missing id (#18). The signature
        # is valid but the event is structurally unusable, so a retry can
        # never succeed — surface it distinctly from a transient failure.
        try:
            user_id = int(metadata["user_id"])
            course_id = int(metadata["course_id"])
            payment_intent_id = payment_intent["id"]
        except (KeyError, ValueError, TypeError) as exc:
            raise NonRetryableWebhookError(
                f"Malformed payment_intent metadata: {exc}"
            ) from exc

        # Non-retryable: event references a user/course that no longer
        # exists (orphaned event) — retrying will never resolve it (#18).
        try:
            user = User.objects.get(id=user_id)
            course = Course.objects.get(id=course_id)
        except (User.DoesNotExist, Course.DoesNotExist) as exc:
            raise NonRetryableWebhookError(
                f"Orphaned event {payment_intent_id}: {exc}"
            ) from exc

        # Exact money: cents → BRL via Decimal, never float (#14). Stripe
        # sends integer cents; the explicit int() guards against a stray float
        # ever reintroducing binary imprecision via Decimal(float).
        amount = Decimal(int(payment_intent["amount"])) / 100
        currency = payment_intent.get("currency", "brl")

        # Defense-in-depth (#27): the amount is server-controlled at intent
        # creation, so a divergence from the course price signals an
        # integration bug or a mid-flight price change. Warn for ops, but
        # never refuse a charge that has already been captured.
        if amount != course.price:
            logger.warning(
                "Amount mismatch for intent %s: captured %s, course %s price %s",
                payment_intent_id,
                amount,
                course.id,
                course.price,
            )
        if currency.lower() != "brl":
            logger.warning(
                "Unexpected currency for intent %s: %s",
                payment_intent_id,
                currency,
            )

        return {
            "user": user,
            "course": course,
            "payment_intent_id": payment_intent_id,
            "amount": amount,
            "currency": currency,
        }

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
            ValueError: If the payment intent was already processed (idempotent
                duplicate).
            NonRetryableWebhookError: If the event is malformed or references a
                user/course that no longer exists (caller should ack with 200).
        """
        # Import inside method to avoid circular imports
        from apps.enrollments.models import Enrollment

        from .models import Payment

        payment_intent = event_data["object"]

        # Validate + resolve the event (raises NonRetryableWebhookError for
        # malformed/orphaned events — #18) and compute the exact amount (#14).
        context = StripeService._resolve_succeeded_intent(payment_intent)
        user = context["user"]
        course = context["course"]
        payment_intent_id = context["payment_intent_id"]

        # Race-safe idempotency (#13): insert directly and let the unique
        # constraint on stripe_payment_intent_id arbitrate. A concurrent or
        # repeated delivery (or an already-processed intent) collides on the
        # constraint; we convert that to the idempotent ValueError instead of
        # letting IntegrityError bubble into a spurious 500 that Stripe
        # retries. The check-then-create TOCTOU window is removed entirely.
        try:
            payment = Payment.objects.create(
                user=user,
                course=course,
                amount=context["amount"],
                currency=context["currency"],
                stripe_payment_intent_id=payment_intent_id,
                status=Payment.Status.SUCCEEDED,
            )
        except IntegrityError as exc:
            raise ValueError(f"Payment {payment_intent_id} already processed") from exc

        # Create enrollment
        enrollment, created = Enrollment.objects.get_or_create(
            user=user,
            course=course,
            defaults={"payment": payment},
        )

        if not created and enrollment.payment is None:
            enrollment.payment = payment
            enrollment.save(update_fields=["payment"])
        elif not created:
            # Already enrolled WITH a linked payment, yet a second succeeded
            # intent (different pi_id) arrived → a genuine duplicate charge.
            # The new Payment is kept as an audit trail for the refund; log
            # a loud, alertable ERROR so ops can refund it (#12). Automatic
            # refund is intentionally deferred (product decision).
            logger.error(
                "Duplicate charge detected: user %s already enrolled in "
                "course %s (enrollment %s, original payment %s); second "
                "payment %s (intent %s) requires a refund.",
                user.id,
                course.id,
                enrollment.id,
                enrollment.payment_id,
                payment.id,
                payment_intent_id,
            )
            return enrollment

        logger.info(
            "Enrollment %s %s after payment %s",
            enrollment.id,
            "created" if created else "updated",
            payment.id,
        )

        return enrollment
