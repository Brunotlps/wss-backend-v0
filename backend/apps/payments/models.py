"""
Payment models for WSS Backend.

This module manages payment records for course purchases via Stripe:
- Payment: Stores Stripe payment intent data and status

Relationships:
- User ←→ Payment (One-to-Many)
- Course ←→ Payment (One-to-Many)
- Payment ←→ Enrollment (One-to-One, optional)

Business Rules:
- Each successful payment creates exactly one enrollment
- Duplicate Stripe payment intent IDs are rejected
- Payment status follows Stripe lifecycle: pending → succeeded | failed
"""

from django.contrib.auth import get_user_model
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import TimeStampedModel

User = get_user_model()


class Payment(TimeStampedModel):
    """
    Payment record for course purchases via Stripe.

    Tracks the full lifecycle of a payment from intent creation through
    confirmation. Created when the user initiates checkout; updated via
    Stripe webhooks when payment succeeds or fails.

    Attributes:
        user (ForeignKey): Student making the payment.
        course (ForeignKey): Course being purchased.
        amount (DecimalField): Amount charged in BRL.
        currency (CharField): Currency code (default: brl).
        stripe_payment_intent_id (CharField): Stripe PI ID, unique per payment.
        status (CharField): Payment lifecycle status.

    Notes:
        - stripe_payment_intent_id must be unique to prevent duplicate processing
        - Use PROTECT on_delete to preserve financial audit trail
        - Amount stored in BRL (not cents)
    """

    class Status(models.TextChoices):
        PENDING = "pending", _("Pending")
        SUCCEEDED = "succeeded", _("Succeeded")
        FAILED = "failed", _("Failed")
        REFUNDED = "refunded", _("Refunded")

    user = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="payments",
        verbose_name=_("student"),
        help_text=_("Student who made this payment"),
    )

    course = models.ForeignKey(
        "courses.Course",
        on_delete=models.PROTECT,
        related_name="payments",
        verbose_name=_("course"),
        help_text=_("Course being purchased"),
    )

    amount = models.DecimalField(
        _("amount"),
        max_digits=10,
        decimal_places=2,
        help_text=_("Payment amount in BRL"),
    )

    currency = models.CharField(
        _("currency"),
        max_length=3,
        default="brl",
        help_text=_("ISO 4217 currency code"),
    )

    stripe_payment_intent_id = models.CharField(
        _("stripe payment intent id"),
        max_length=255,
        unique=True,
        help_text=_("Stripe Payment Intent ID (pi_...)"),
    )

    status = models.CharField(
        _("status"),
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        help_text=_("Current payment status"),
    )

    class Meta:
        verbose_name = _("payment")
        verbose_name_plural = _("payments")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"Payment {self.id}: {self.user.email} - {self.course.title} ({self.status})"

    @property
    def is_succeeded(self) -> bool:
        """Return True if payment was successful."""
        return self.status == self.Status.SUCCEEDED
