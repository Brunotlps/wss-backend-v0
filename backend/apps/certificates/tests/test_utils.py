"""Tests for the certificate PDF/code generation utilities (#82).

`utils.py` holds the two highest-risk helpers in the app:
- ``generate_certificate_code`` — the public, unguessable validation code (#75);
- ``generate_certificate_pdf`` — the ReportLab render that writes the legal PDF.

Both were effectively untested (``utils.py`` ~25% coverage). These tests lock
in the code format/entropy/collision behaviour and smoke-test that a real PDF
file is written to disk.
"""

import re
from datetime import datetime
from unittest.mock import MagicMock, patch

from django.utils import timezone

import pytest

from apps.certificates.factories import CertificateFactory
from apps.certificates.utils import generate_certificate_code, generate_certificate_pdf

CODE_RE = re.compile(r"^WSS-\d{4}-[A-Z0-9]{12}$")


@pytest.mark.django_db
class TestGenerateCertificateCode:
    """Format, entropy, uniqueness and collision-retry of the public code."""

    def test_code_matches_expected_format(self):
        """Code is WSS-<year>-<12 uppercase alphanumerics> (#75)."""
        year = datetime.now().year
        code = generate_certificate_code()
        assert CODE_RE.match(code), code
        assert code.startswith(f"WSS-{year}-")
        assert len(code) == len(f"WSS-{year}-") + 12

    def test_consecutive_codes_differ(self):
        """Distinct calls yield distinct codes (CSPRNG entropy, no repeats)."""
        codes = {generate_certificate_code() for _ in range(25)}
        assert len(codes) == 25

    @patch("apps.certificates.models.Certificate.objects")
    def test_collision_retries_then_returns_unique(self, mock_objects):
        """A first colliding draw is retried; the next free code is returned."""
        qs = MagicMock()
        qs.exists.side_effect = [True, False]
        mock_objects.filter.return_value = qs

        code = generate_certificate_code()

        assert CODE_RE.match(code), code
        assert mock_objects.filter.call_count == 2

    @patch("apps.certificates.models.Certificate.objects")
    def test_exhausting_attempts_raises_runtimeerror(self, mock_objects):
        """If every draw collides, it gives up after MAX_ATTEMPTS (=5)."""
        mock_objects.filter.return_value.exists.return_value = True

        with pytest.raises(RuntimeError):
            generate_certificate_code()

        assert mock_objects.filter.call_count == 5


@pytest.mark.django_db
class TestGenerateCertificatePDF:
    """Smoke tests that the ReportLab render writes a valid PDF file."""

    def test_writes_pdf_file_and_returns_relative_path(self, settings, tmp_path):
        """A PDF is written under MEDIA_ROOT and the relative path is returned."""
        settings.MEDIA_ROOT = str(tmp_path)
        cert = CertificateFactory(
            certificate_code="WSS-2026-PDFSMOKE001",
            completion_date_snapshot=timezone.make_aware(datetime(2026, 3, 15)),
        )

        relative_path = generate_certificate_pdf(cert)

        assert relative_path == "certificates/2026/03/WSS-2026-PDFSMOKE001.pdf"
        written = tmp_path / relative_path
        assert written.exists()
        assert written.read_bytes().startswith(b"%PDF")

    def test_falls_back_to_today_when_completion_date_missing(self, settings, tmp_path):
        """A PDF-pending cert with no completion date still renders (uses today)."""
        settings.MEDIA_ROOT = str(tmp_path)
        # Default enrollment is not completed -> completed_at is None and no
        # snapshot is set, so completion_date is None and the helper falls back.
        cert = CertificateFactory(certificate_code="WSS-2026-NODATE0001")
        assert cert.completion_date is None

        relative_path = generate_certificate_pdf(cert)

        today = datetime.today()
        expected_dir = today.strftime("certificates/%Y/%m/")
        assert relative_path == f"{expected_dir}WSS-2026-NODATE0001.pdf"
        assert (tmp_path / relative_path).read_bytes().startswith(b"%PDF")
