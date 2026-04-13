"""Admin registration for the payments app."""

from django.contrib import admin

from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    """Admin interface for Payment records."""

    list_display = [
        "id",
        "user",
        "course",
        "amount",
        "currency",
        "status",
        "created_at",
    ]
    list_filter = ["status", "currency", "created_at"]
    search_fields = [
        "user__email",
        "course__title",
        "stripe_payment_intent_id",
    ]
    readonly_fields = [
        "user",
        "course",
        "amount",
        "currency",
        "stripe_payment_intent_id",
        "created_at",
        "updated_at",
    ]
    ordering = ["-created_at"]

    def get_queryset(self, request):
        """Optimize admin queryset."""
        return super().get_queryset(request).select_related("user", "course")

    def has_add_permission(self, request):
        """Payments are created via Stripe only — disable manual creation."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Payments must not be deleted — financial audit trail."""
        return False
