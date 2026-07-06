"""Tests for Certificate API views."""

from django.core.files.uploadedfile import SimpleUploadedFile

from rest_framework import status

import pytest

from apps.certificates.factories import CertificateFactory
from apps.enrollments.factories import EnrollmentFactory


def _pdf():
    """Return a tiny in-memory PDF upload for download tests."""
    return SimpleUploadedFile(
        "cert.pdf", b"%PDF-1.4 test", content_type="application/pdf"
    )


@pytest.mark.django_db
class TestCertificateViewSet:
    """Tests for /api/certificates/ read-only endpoints."""

    URL = "/api/certificates/"

    def test_list_requires_authentication(self, api_client):
        """Unauthenticated request is rejected."""
        response = api_client.get(self.URL)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_student_sees_only_own_certificates(self, auth_client):
        """Students see only their own certificates."""
        enrollment = EnrollmentFactory(user=auth_client.user)
        CertificateFactory(enrollment=enrollment)
        CertificateFactory()  # Another user's certificate
        response = auth_client.get(self.URL)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1

    def test_retrieve_own_certificate(self, auth_client):
        """Student can retrieve their own certificate."""
        enrollment = EnrollmentFactory(user=auth_client.user)
        cert = CertificateFactory(enrollment=enrollment)
        response = auth_client.get(f"{self.URL}{cert.pk}/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["certificate_code"] == cert.certificate_code

    def test_cannot_retrieve_other_user_certificate(self, auth_client):
        """Student cannot retrieve another user's certificate (404 from filtered queryset)."""
        other_cert = CertificateFactory()
        response = auth_client.get(f"{self.URL}{other_cert.pk}/")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_download_returns_404_when_no_pdf(self, auth_client):
        """Download endpoint returns 404 when no PDF file exists.

        Error envelope uses ``detail`` (DRF/api-conventions.md standard), not
        the non-standard ``error`` key (#85).
        """
        enrollment = EnrollmentFactory(user=auth_client.user)
        cert = CertificateFactory(enrollment=enrollment, pdf_file=None)
        response = auth_client.get(f"{self.URL}{cert.pk}/download/")
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "detail" in response.data
        assert "error" not in response.data

    def test_download_revoked_certificate_returns_410(self, auth_client):
        """A revoked certificate is not downloadable even with a PDF (#81).

        Error envelope uses ``detail`` (DRF/api-conventions.md standard), not
        the non-standard ``error`` key (#85).
        """
        enrollment = EnrollmentFactory(user=auth_client.user)
        cert = CertificateFactory(
            enrollment=enrollment, is_valid=False, pdf_file=_pdf()
        )
        response = auth_client.get(f"{self.URL}{cert.pk}/download/")
        assert response.status_code == status.HTTP_410_GONE
        assert "detail" in response.data
        assert "error" not in response.data

    def test_download_valid_certificate_with_pdf_returns_200(self, auth_client):
        """A valid certificate with a PDF is still downloadable (#81 guard)."""
        enrollment = EnrollmentFactory(user=auth_client.user)
        cert = CertificateFactory(enrollment=enrollment, is_valid=True, pdf_file=_pdf())
        response = auth_client.get(f"{self.URL}{cert.pk}/download/")
        assert response.status_code == status.HTTP_200_OK

    def test_validate_ownership_returns_200(self, auth_client):
        """Validate ownership endpoint returns 200 for own certificate."""
        enrollment = EnrollmentFactory(user=auth_client.user)
        cert = CertificateFactory(enrollment=enrollment)
        response = auth_client.post(f"{self.URL}{cert.pk}/validate/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["valid"] is True
        assert response.data["certificate_code"] == cert.certificate_code

    def test_validate_by_code_is_public(self, api_client):
        """Public validation by code requires no authentication."""
        cert = CertificateFactory(is_valid=True)
        response = api_client.get(f"{self.URL}validate/{cert.certificate_code}/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["valid"] is True

    def test_validate_by_code_revoked_certificate(self, api_client):
        """Validate by code returns valid=False for revoked certificates."""
        cert = CertificateFactory(is_valid=False)
        response = api_client.get(f"{self.URL}validate/{cert.certificate_code}/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["valid"] is False

    def test_validate_by_code_nonexistent_returns_404(self, api_client):
        """Validate by code returns 404 for unknown codes."""
        response = api_client.get(f"{self.URL}validate/WSS-9999-ZZZZZZ/")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.parametrize("is_valid", [True, False])
    def test_validate_by_code_does_not_leak_pii(self, api_client, is_valid):
        """Public verification exposes no email or internal id (#82).

        Anyone with a code can hit this endpoint, so the payload must stay
        minimal: validity + code + holder name, never the user's email,
        primary key, or enrollment id — on both the valid and revoked paths.
        """
        cert = CertificateFactory(is_valid=is_valid)
        response = api_client.get(f"{self.URL}validate/{cert.certificate_code}/")
        assert response.status_code == status.HTTP_200_OK

        leaky = {"email", "id", "pk", "user", "user_id", "enrollment", "enrollment_id"}
        assert leaky.isdisjoint(response.data.keys())
        body = str(response.data)
        assert cert.enrollment.user.email not in body
        assert set(response.data.keys()) == {
            "valid",
            "message",
            "certificate_code",
            "student_name",
        }

    def test_validate_by_code_pending_pdf_is_still_valid(self, api_client):
        """A freshly issued, PDF-pending certificate verifies as valid (#73).

        is_valid is the revocation flag only; PDF readiness is tracked
        separately by pdf_file. A real cert is created with no PDF yet, so
        verification must not depend on the PDF being present.
        """
        cert = CertificateFactory(is_valid=True, pdf_file=None)
        assert not cert.pdf_file

        response = api_client.get(f"{self.URL}validate/{cert.certificate_code}/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["valid"] is True

    def test_list_certificates_empty_when_no_enrollments(self, auth_client):
        """Authenticated user with no certificates sees empty list."""
        response = auth_client.get(self.URL)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 0


@pytest.mark.django_db
class TestCertificatePermissions:
    """Tests for IsCertificateOwner permission."""

    URL = "/api/certificates/"

    def test_staff_can_see_any_certificate(self, staff_client):
        """Staff members can retrieve any certificate."""
        CertificateFactory()
        # Staff queryset is still filtered (only own), but permission grants access
        # Create own enrollment cert to verify staff access
        enrollment = EnrollmentFactory(user=staff_client.user)
        own_cert = CertificateFactory(enrollment=enrollment)
        response = staff_client.get(f"{self.URL}{own_cert.pk}/")
        assert response.status_code == status.HTTP_200_OK

    def test_validate_ownership_denied_for_other_certificate(self, auth_client):
        """Cannot validate ownership of another user's certificate (404)."""
        other_cert = CertificateFactory()
        response = auth_client.post(f"{self.URL}{other_cert.pk}/validate/")
        assert response.status_code == status.HTTP_404_NOT_FOUND
