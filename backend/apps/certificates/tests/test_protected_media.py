"""Deny-tests for protected certificate PDF delivery (#74, #116).

The certificate PDF embeds PII (student name, course, instructor, date). It must
never be reachable through a public ``/media/`` URL: the serializer must not
advertise ``pdf_file``/``pdf_url``, and the authenticated ``download`` action
streams the bytes directly from Django via ``FileResponse`` (gated by
``IsCertificateOwner``) rather than exposing the raw media path. It deliberately
does NOT use ``X-Accel-Redirect``: Nginx drops the CORS header when it serves a
file from an internal location, breaking the frontend's authenticated XHR
download (#116). The ``/media/certificates/`` location stays ``internal``.
"""

from django.core.files.base import ContentFile

from rest_framework import status

import pytest

from apps.certificates.factories import CertificateFactory
from apps.enrollments.factories import EnrollmentFactory

URL = "/api/certificates/"

PDF_BYTES = b"%PDF-1.4 fake certificate bytes"


def _cert_with_pdf(user, name="certificates/2026/06/WSS-2026-ABC123.pdf"):
    """Create a certificate owned by ``user`` with a (name-only) stored PDF.

    Used by tests that only need ``pdf_file`` to be truthy (e.g. download_url
    presence) and never read the file from disk.
    """
    enrollment = EnrollmentFactory(user=user)
    cert = CertificateFactory(enrollment=enrollment)
    cert.pdf_file = name
    cert.save(update_fields=["pdf_file"])
    return cert


def _cert_with_real_pdf(user, basename="WSS-2026-XYZ999.pdf"):
    """Create a certificate owned by ``user`` with real PDF bytes on disk."""
    enrollment = EnrollmentFactory(user=user)
    cert = CertificateFactory(enrollment=enrollment)
    cert.pdf_file.save(basename, ContentFile(PDF_BYTES), save=True)
    return cert


@pytest.mark.django_db
class TestSerializerDoesNotLeakPdfURL:
    """The serializer must not expose a directly-fetchable media URL (#74)."""

    def test_retrieve_hides_raw_pdf_fields(self, auth_client):
        """Detail view exposes no ``pdf_file`` and no raw ``pdf_url``."""
        cert = _cert_with_pdf(auth_client.user)

        response = auth_client.get(f"{URL}{cert.pk}/")

        assert response.status_code == status.HTTP_200_OK
        assert "pdf_file" not in response.data
        assert "pdf_url" not in response.data

    def test_retrieve_exposes_gated_download_url(self, auth_client):
        """Detail view exposes a gated ``download_url`` pointing at the action."""
        cert = _cert_with_pdf(auth_client.user)

        response = auth_client.get(f"{URL}{cert.pk}/")

        assert "download_url" in response.data
        assert response.data["download_url"].endswith(
            f"/api/certificates/{cert.pk}/download/"
        )

    def test_download_url_is_none_without_pdf(self, auth_client):
        """``download_url`` is None when no PDF has been generated yet."""
        enrollment = EnrollmentFactory(user=auth_client.user)
        cert = CertificateFactory(enrollment=enrollment, pdf_file=None)

        response = auth_client.get(f"{URL}{cert.pk}/")

        assert response.data["download_url"] is None


@pytest.mark.django_db
class TestProtectedDownload:
    """The download action streams PDF bytes from Django, owner-gated (#74, #116)."""

    def test_owner_download_streams_pdf_bytes(self, auth_client):
        """Owner download → 200 streaming the PDF bytes, NOT an X-Accel handoff."""
        cert = _cert_with_real_pdf(auth_client.user)

        response = auth_client.get(f"{URL}{cert.pk}/download/")

        assert response.status_code == status.HTTP_200_OK
        assert response["Content-Type"] == "application/pdf"
        assert "attachment" in response["Content-Disposition"]
        # Bytes come from Django (FileResponse), so Nginx never substitutes the
        # response and cannot strip the CORS header (#116).
        assert "X-Accel-Redirect" not in response
        assert b"".join(response.streaming_content) == PDF_BYTES

    def test_non_owner_download_denied(self, auth_client):
        """Another user's certificate download → 404 from the filtered queryset."""
        other = CertificateFactory()
        other.pdf_file = "certificates/2026/06/WSS-2026-OTHER1.pdf"
        other.save(update_fields=["pdf_file"])

        response = auth_client.get(f"{URL}{other.pk}/download/")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_anonymous_download_denied(self, api_client):
        """Anonymous download → 401 (authentication required)."""
        cert = CertificateFactory()
        cert.pdf_file = "certificates/2026/06/WSS-2026-ANON01.pdf"
        cert.save(update_fields=["pdf_file"])

        response = api_client.get(f"{URL}{cert.pk}/download/")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
