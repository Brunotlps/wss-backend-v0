"""
Permissions for the certificates module.

This module defines custom permission classes to control access to
certificate-related resources in the system. Permissions ensure that only
authorized users can access their own certificates.

Available permissions:
    - IsCertificateOwner: Only certificate owners can access their certificates

Business Rules:
    - Students can only access their own certificates
    - Staff members can access any certificate (audit/support)
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
        - Staff members can access any certificate (for support/audit)
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
            1. Staff members can access any certificate (unrestricted)
            2. Regular users can only access certificates from their enrollments
            3. Check: obj.enrollment.user == request.user

        Args:
            request (Request): DRF Request object with authenticated user
            view (APIView): ViewSet handling the request
            obj (Certificate): Certificate instance being accessed

        Returns:
            bool: True if user can access this certificate, False otherwise

        Examples:
            # Staff member accessing any certificate
            >>> request.user.is_staff = True
            >>> has_object_permission(request, view, any_certificate)
            True

            # Student accessing their own certificate
            >>> certificate.enrollment.user == request.user
            >>> has_object_permission(request, view, certificate)
            True

            # Student trying to access another student's certificate
            >>> certificate.enrollment.user != request.user
            >>> has_object_permission(request, view, certificate)
            False
        """
        # Staff members have unrestricted access (support/audit)
        if request.user.is_staff:
            return True

        # Regular users can only access their own certificates
        # Check if the certificate belongs to one of the user's enrollments
        return obj.enrollment.user == request.user
