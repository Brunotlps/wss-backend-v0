"""Custom DRF permissions for the payments app."""

from typing import TYPE_CHECKING

from rest_framework import permissions
from rest_framework.request import Request
from rest_framework.views import APIView

if TYPE_CHECKING:
    from .models import Payment


class IsPaymentOwner(permissions.BasePermission):
    """
    Object-level permission: only the payment owner or staff may access it.

    Permissions:
        - Staff: full access to all payments
        - Owner: read-only access to their own payments
    """

    message = "You do not have permission to access this payment."

    def has_object_permission(
        self, request: Request, view: APIView, obj: "Payment"
    ) -> bool:
        """Allow access to staff or the payment owner."""
        if request.user.is_staff:
            return True
        return obj.user == request.user
