"""
Permissions for the certificates module.

This module defines custom permission classes to control access to
certificate-related resources in the system. Permissions ensure that only
authorized users can access their own certificates.

Available permissions:
    - IsCertificateOwner: Only certificate owners can access their certificates

Business Rules:
    - Students can only access their own certificates
    - Staff/support access to other users' certificates happens via the
      Django admin (CertificateAdmin), not this API
    - Public validation endpoint bypasses this permission

Usage:
    Apply to CertificateViewSet to enforce ownership checks on detail views
    and custom actions (download, validate by ID).
"""

from rest_framework.permissions import BasePermission


class IsCertificateOwner(BasePermission):
    """
    Custom permission to only allow certificate owners to access certificates.

    This is an OBJECT-LEVEL permission (checked for specific certificate instances).
    Applied on detail views (retrieve, download) to ensure users can only access
    their own certificates.

    Business Rules:
        - Student can access only certificates from their enrollments
        - No staff bypass here: ``CertificateViewSet.get_queryset`` filters
          by owner for every request, so a certificate a staff member
          doesn't own already 404s before this ever runs. Staff/support
          access to other users' certificates goes through the Django
          admin instead.
        - Checks: certificate.enrollment.user == request.user

    Usage:
        class CertificateViewSet(viewsets.ReadOnlyModelViewSet):
            permission_classes = [IsAuthenticated, IsCertificateOwner]

            @action(detail=True)
            def download(self, request, pk=None):
                # IsCertificateOwner checked automatically
                certificate = self.get_object()
                ...

    Notes:
        - This permission is NOT checked on list views (custom queryset filtering)
        - Public validation by code endpoint should NOT use this permission
        - Returns False for anonymous users (requires IsAuthenticated)

    Attributes:
        Inherits from BasePermission

    Methods:
        has_object_permission: Determines if user can access specific certificate
    """

    def has_object_permission(self, request, view, obj):
        """
        Check if user can access this specific certificate instance.

        This is called AFTER get_object() retrieves the certificate from database.
        Called for detail views (GET /api/certificates/{id}/), custom actions
        (download, validate_ownership), and any operation on a specific certificate.

        Permission Logic:
            1. User can only access certificates from their own enrollments
            2. Check: obj.enrollment.user == request.user

        Note:
            There is deliberately no ``is_staff`` bypass here (#220): the
            queryset (``CertificateViewSet.get_queryset``) already filters
            by owner for every request, staff included, so this method never
            even runs for a certificate a staff member doesn't own —
            ``get_object()`` 404s first. Staff/support access to other
            users' certificates is handled by the Django admin instead.

        Args:
            request (Request): DRF Request object with authenticated user
            view (APIView): ViewSet handling the request
            obj (Certificate): Certificate instance being accessed

        Returns:
            bool: True if user can access this certificate, False otherwise

        Examples:
            # Student accessing their own certificate
            >>> certificate.enrollment.user == request.user
            >>> has_object_permission(request, view, certificate)
            True

            # Student trying to access another student's certificate
            >>> certificate.enrollment.user != request.user
            >>> has_object_permission(request, view, certificate)
            False
        """
        return obj.enrollment.user == request.user
