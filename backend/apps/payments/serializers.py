"""Serializers for the payments app."""

from rest_framework import serializers

from .models import Payment


class PaymentSerializer(serializers.ModelSerializer):
    """Read serializer for Payment records."""

    class Meta:
        model = Payment
        fields = [
            "id",
            "user",
            "course",
            "amount",
            "currency",
            "stripe_payment_intent_id",
            "status",
            "created_at",
        ]
        read_only_fields = fields


class PaymentIntentRequestSerializer(serializers.Serializer):
    """Validates the body for POST /api/payments/create-intent/."""

    course_id = serializers.IntegerField(
        help_text="ID of the course to purchase."
    )


class PaymentIntentResponseSerializer(serializers.Serializer):
    """Shape of the response from POST /api/payments/create-intent/."""

    client_secret = serializers.CharField()
    payment_intent_id = serializers.CharField()
    amount = serializers.IntegerField(help_text="Amount in cents.")
    currency = serializers.CharField()
