from django.http import HttpResponse
from django.shortcuts import get_object_or_404

from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Certificate
from .permissions import IsCertificateOwner
from .serializers import CertificateSerializer
from .throttles import VerifyThrottle


class CertificateViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for certificate management.

    Provides:
    - list: GET /api/certificates/
    - retrieve: GET /api/certificates/{id}/
    - download: GET /api/certificates/{id}/download/ (custom action)
    - validate_ownership: POST /api/certificates/{id}/validate/ (custom action)
    - validate_by_code: GET /api/certificates/validate/{code}/ (custom action)
    """

    serializer_class = CertificateSerializer
    permission_classes = [permissions.IsAuthenticated, IsCertificateOwner]

    def get_queryset(self):

        user = self.request.user
        return Certificate.objects.filter(enrollment__user=user).select_related(
            "enrollment__user", "enrollment__course", "enrollment__course__instructor"
        )

    @action(detail=True, methods=["get"])
    def download(self, request, pk=None):
        """Serve the certificate PDF via Nginx X-Accel-Redirect (#74).

        ``get_object()`` enforces ``IsCertificateOwner`` (staff or owner only),
        then the bytes are delegated to Nginx's internal ``/protected/``
        location instead of being exposed at a guessable public ``/media/`` URL.
        """
        certificate = self.get_object()

        if not certificate.pdf_file:
            return Response(
                {"error": "PDF file not available for this certificate"},
                status=status.HTTP_404_NOT_FOUND,
            )

        response = HttpResponse(status=200)
        response["X-Accel-Redirect"] = f"/protected/{certificate.pdf_file.name}"
        response["Content-Disposition"] = (
            f'attachment; filename="certificate_{certificate.certificate_code}.pdf"'
        )
        # Defer the MIME type to Nginx's internal location (mime.types).
        del response["Content-Type"]
        return response

    @action(detail=True, methods=["post"], url_path="validate")
    def validate_ownership(self, request, pk=None):

        certificate = self.get_object()

        return Response(
            {
                "valid": True,
                "message": "Certificate belongs to you",
                "certificate_code": certificate.certificate_code,
            },
            status=status.HTTP_200_OK,
        )

    @action(
        detail=False,
        methods=["get"],
        permission_classes=[permissions.AllowAny],
        throttle_classes=[VerifyThrottle],
        url_path="validate/(?P<code>[^/.]+)",
    )
    def validate_by_code(self, request, code=None):

        certificate = get_object_or_404(
            Certificate.objects.select_related("enrollment__user"),
            certificate_code=code,
        )

        return Response(
            {
                "valid": certificate.is_valid,
                "message": (
                    "Certificate is valid"
                    if certificate.is_valid
                    else "Certificate has been revoked"
                ),
                "certificate_code": certificate.certificate_code,
                "student_name": certificate.enrollment.user.get_full_name(),
            },
            status=status.HTTP_200_OK,
        )
