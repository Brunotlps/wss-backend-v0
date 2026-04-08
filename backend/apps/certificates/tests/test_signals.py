"""Tests for certificate auto-generation signal."""

import pytest
from unittest.mock import patch

from django.utils import timezone

from apps.certificates.models import Certificate
from apps.enrollments.factories import EnrollmentFactory


@pytest.mark.django_db
class TestCreateCertificateOnCompletion:
    """Test the post_save signal that auto-generates certificates."""

    @patch("apps.certificates.signals.generate_certificate_pdf")
    def test_certificate_created_when_enrollment_completed(self, mock_pdf):
        """Certificate is created when enrollment.completed becomes True."""
        mock_pdf.return_value = "certificates/2026/01/WSS-2026-ABC123.pdf"
        enrollment = EnrollmentFactory()
        enrollment.completed = True
        enrollment.completed_at = timezone.now()
        enrollment.save()
        assert Certificate.objects.filter(enrollment=enrollment).exists()

    @patch("apps.certificates.signals.generate_certificate_pdf")
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

    @patch("apps.certificates.signals.generate_certificate_pdf")
    def test_pdf_generation_called_with_certificate(self, mock_pdf):
        """PDF generation function is called with the created certificate."""
        mock_pdf.return_value = "certificates/2026/01/WSS-2026-ABC123.pdf"
        enrollment = EnrollmentFactory()
        enrollment.completed = True
        enrollment.completed_at = timezone.now()
        enrollment.save()
        cert = Certificate.objects.get(enrollment=enrollment)
        mock_pdf.assert_called_once_with(cert)

    @patch("apps.certificates.signals.generate_certificate_pdf")
    def test_certificate_is_valid_after_pdf_generation(self, mock_pdf):
        """Certificate.is_valid is True after successful PDF generation."""
        mock_pdf.return_value = "certificates/2026/01/WSS-2026-ABC123.pdf"
        enrollment = EnrollmentFactory()
        enrollment.completed = True
        enrollment.completed_at = timezone.now()
        enrollment.save()
        cert = Certificate.objects.get(enrollment=enrollment)
        cert.refresh_from_db()
        assert cert.is_valid is True

    @patch("apps.certificates.signals.generate_certificate_pdf")
    def test_certificate_pdf_generation_failure_marks_failed_at(self, mock_pdf):
        """When PDF generation fails, pdf_generation_failed_at is set."""
        mock_pdf.side_effect = Exception("ReportLab error")
        enrollment = EnrollmentFactory()
        enrollment.completed = True
        enrollment.completed_at = timezone.now()
        enrollment.save()
        cert = Certificate.objects.get(enrollment=enrollment)
        cert.refresh_from_db()
        assert cert.pdf_generation_failed_at is not None
        assert cert.is_valid is False
