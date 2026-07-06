from django.db.models import QuerySet
from django.http import FileResponse
from django.shortcuts import get_object_or_404

from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
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

    def get_queryset(self) -> "QuerySet[Certificate]":
        """Return the requesting user's certificates with related data."""
        user = self.request.user
        return Certificate.objects.filter(enrollment__user=user).select_related(
            "enrollment__user", "enrollment__course", "enrollment__course__instructor"
        )

    @action(detail=True, methods=["get"])
    def download(
        self, request: Request, pk: "str | None" = None
    ) -> "FileResponse | Response":
        """Serve the certificate PDF directly from Django (#74, #116).

        ``get_object()`` enforces ``IsCertificateOwner`` (staff or owner only).
        The PDF is streamed with a ``FileResponse`` rather than an Nginx
        ``X-Accel-Redirect`` so the CORS header added by ``corsheaders`` on the
        Django response actually reaches the browser — Nginx drops it when it
        serves a file from an internal location, breaking the frontend's
        authenticated XHR download (#116). Certificates are tiny (~5KB), so the
        Nginx offload is unnecessary, and the ``/media/certificates/`` location
        stays ``internal`` (defense-in-depth, #74): the PDF is never exposed at
        a guessable public ``/media/`` URL.

        Revoked certificates (``is_valid`` is False) return ``410 Gone`` and are
        not served, so revocation is honoured on the download path (#81).
        """
        certificate = self.get_object()

        if not certificate.is_valid:
            return Response(
                {"detail": "This certificate has been revoked"},
                status=status.HTTP_410_GONE,
            )

        if not certificate.pdf_file:
            return Response(
                {"detail": "PDF file not available for this certificate"},
                status=status.HTTP_404_NOT_FOUND,
            )

        return FileResponse(
            certificate.pdf_file.open("rb"),
            as_attachment=True,
            filename=f"certificate_{certificate.certificate_code}.pdf",
            content_type="application/pdf",
        )

    @action(detail=True, methods=["post"], url_path="validate")
    def validate_ownership(self, request: Request, pk: "str | None" = None) -> Response:
        """Confirm the authenticated owner's certificate (object-permission gated)."""
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
    def validate_by_code(self, request: Request, code: "str | None" = None) -> Response:
        """Public certificate validation by code (no PII beyond the holder name)."""
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
