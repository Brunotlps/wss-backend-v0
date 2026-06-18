"""Tests for certificate auto-generation signal."""

from unittest.mock import patch

from django.utils import timezone

import pytest

from apps.certificates.factories import CertificateFactory
from apps.certificates.models import Certificate
from apps.enrollments.factories import EnrollmentFactory


@pytest.mark.django_db
class TestCreateCertificateOnCompletion:
    """Test the post_save signal that auto-generates certificates."""

    @patch("apps.certificates.tasks.generate_certificate_pdf")
    def test_certificate_created_when_enrollment_completed(self, mock_pdf):
        """Certificate is created when enrollment.completed becomes True."""
        mock_pdf.return_value = "certificates/2026/01/WSS-2026-ABC123.pdf"
        enrollment = EnrollmentFactory()
        enrollment.completed = True
        enrollment.completed_at = timezone.now()
        enrollment.save()
        assert Certificate.objects.filter(enrollment=enrollment).exists()

    @patch("apps.certificates.tasks.generate_certificate_pdf")
    def test_certificate_not_duplicated_on_second_save(self, mock_pdf):
        """Signal does not create duplicate certificate on subsequent saves."""
        mock_pdf.return_value = "certificates/2026/01/WSS-2026-ABC123.pdf"
        enrollment = EnrollmentFactory()
        enrollment.completed = True
        enrollment.completed_at = timezone.now()
        enrollment.save()
        # Save again — should not create a second certificate
        enrollment.review = "Great course!"
        enrollment.save()
        assert Certificate.objects.filter(enrollment=enrollment).count() == 1

    def test_no_certificate_when_not_completed(self):
        """Signal does not create certificate for incomplete enrollments."""
        enrollment = EnrollmentFactory(completed=False)
        enrollment.save()
        assert not Certificate.objects.filter(enrollment=enrollment).exists()

    def test_no_certificate_when_completed_at_is_none(self):
        """Signal requires completed_at to be set (guards against partial saves)."""
        enrollment = EnrollmentFactory()
        enrollment.completed = True
        enrollment.completed_at = None
        enrollment.save()
        assert not Certificate.objects.filter(enrollment=enrollment).exists()

    @patch("apps.certificates.tasks.generate_certificate_pdf")
    def test_pdf_generation_called_with_certificate(self, mock_pdf):
        """PDF generation function is called with the created certificate."""
        mock_pdf.return_value = "certificates/2026/01/WSS-2026-ABC123.pdf"
        enrollment = EnrollmentFactory()
        enrollment.completed = True
        enrollment.completed_at = timezone.now()
        enrollment.save()
        cert = Certificate.objects.get(enrollment=enrollment)
        mock_pdf.assert_called_once_with(cert)

    @patch("apps.certificates.tasks.generate_certificate_pdf")
    def test_certificate_has_pdf_and_stays_valid_after_generation(self, mock_pdf):
        """After PDF generation the file is stored and is_valid (revocation)
        is untouched — PDF readiness is tracked by pdf_file, not is_valid (#73).
        """
        mock_pdf.return_value = "certificates/2026/01/WSS-2026-ABC123.pdf"
        enrollment = EnrollmentFactory()
        enrollment.completed = True
        enrollment.completed_at = timezone.now()
        enrollment.save()
        cert = Certificate.objects.get(enrollment=enrollment)
        cert.refresh_from_db()
        assert bool(cert.pdf_file) is True
        assert cert.is_valid is True

    @patch("apps.certificates.tasks.generate_certificate_pdf")
    def test_certificate_valid_even_before_pdf_is_generated(self, mock_pdf):
        """A freshly issued certificate is valid (not revoked) regardless of
        PDF state — closes the false-"revoked" window during generation (#73).
        """
        enrollment = EnrollmentFactory()
        with patch(
            "apps.certificates.tasks.generate_certificate_pdf_async.delay"
        ) as mock_delay:
            mock_delay.return_value = None  # PDF generation not run yet
            enrollment.completed = True
            enrollment.completed_at = timezone.now()
            enrollment.save()
        cert = Certificate.objects.get(enrollment=enrollment)
        assert cert.is_valid is True
        assert not cert.pdf_file

    @patch("apps.certificates.tasks.generate_certificate_pdf")
    def test_pdf_generation_failure_does_not_revoke(self, mock_pdf):
        """A PDF generation failure records pdf_generation_failed_at but must
        NOT revoke the certificate — is_valid stays True (failure is not
        revocation) (#73).
        """
        mock_pdf.side_effect = Exception("ReportLab error")
        enrollment = EnrollmentFactory()
        enrollment.completed = True
        enrollment.completed_at = timezone.now()
        enrollment.save()
        cert = Certificate.objects.get(enrollment=enrollment)
        cert.refresh_from_db()
        assert cert.pdf_generation_failed_at is not None
        assert cert.is_valid is True
        assert not cert.pdf_file

    @patch("apps.certificates.tasks.generate_certificate_pdf")
    def test_task_skips_when_pdf_present_and_never_unrevokes(self, mock_pdf):
        """The task idempotency guard checks pdf_file presence, not is_valid:
        a revoked certificate that already has a PDF is left untouched — the
        task must not regenerate the PDF nor flip is_valid back to True (#73).
        """
        from apps.certificates.tasks import generate_certificate_pdf_async

        cert = CertificateFactory(is_valid=False)
        cert.pdf_file = "certificates/2026/01/existing.pdf"
        cert.save(update_fields=["pdf_file"])

        generate_certificate_pdf_async.delay(cert.id)

        cert.refresh_from_db()
        mock_pdf.assert_not_called()
        assert cert.is_valid is False
        assert bool(cert.pdf_file) is True
