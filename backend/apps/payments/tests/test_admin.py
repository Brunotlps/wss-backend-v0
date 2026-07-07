"""Tests for the Payments app's Django admin configuration."""

from django.contrib.admin.sites import AdminSite
from django.urls import reverse

import pytest

from apps.payments.admin import PaymentAdmin
from apps.payments.factories import PaymentFactory
from apps.payments.models import Payment
from apps.users.factories import UserFactory


@pytest.mark.django_db
class TestPaymentAdminStatusReadonly:
    """Payment.status must not be silently editable from the admin."""

    def test_status_is_in_readonly_fields(self):
        """`status` is declared read-only alongside the other financial fields."""
        admin_instance = PaymentAdmin(Payment, AdminSite())
        assert "status" in admin_instance.readonly_fields

    def test_admin_change_view_does_not_update_status(self, client):
        """POSTing a different status through the admin form has no effect.

        Payment.status is exclusively driven by the Stripe webhook lifecycle
        (see services.py); the admin change form must not offer a bypass.
        """
        staff_user = UserFactory(is_staff=True, is_superuser=True)
        payment = PaymentFactory(status=Payment.Status.SUCCEEDED)
        client.force_login(staff_user)

        url = reverse("admin:payments_payment_change", args=[payment.pk])
        response = client.post(url, data={"status": Payment.Status.REFUNDED})

        assert response.status_code == 302  # form processed and saved, not blocked
        payment.refresh_from_db()
        assert payment.status == Payment.Status.SUCCEEDED
