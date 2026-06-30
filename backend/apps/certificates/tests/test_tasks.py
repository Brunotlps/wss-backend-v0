"""Tests for the certificate PDF-generation Celery task.

Covers code generation moved into the task (#80) and the clean
retry-vs-final-failure branching with alerting (#78).
"""

import logging
from unittest.mock import patch

import pytest
from celery.exceptions import Retry

from apps.certificates.factories import CertificateFactory
from apps.certificates.tasks import generate_certificate_pdf_async


@pytest.mark.django_db
class TestGenerateCertificateCodeInTask:
    """Code generation happens in the task, not the request signal (#80)."""

    @patch("apps.certificates.tasks.generate_certificate_pdf")
    def test_task_assigns_code_when_missing(self, mock_pdf):
        """The task fills certificate_code when the row was created without one."""
        mock_pdf.return_value = "certificates/2026/01/x.pdf"
        cert = CertificateFactory(certificate_code=None)

        generate_certificate_pdf_async.run(cert.id)

        cert.refresh_from_db()
        assert cert.certificate_code is not None
        assert cert.certificate_code.startswith("WSS-")
        assert bool(cert.pdf_file) is True

    @patch("apps.certificates.tasks.generate_certificate_code")
    @patch("apps.certificates.tasks.generate_certificate_pdf")
    def test_task_keeps_existing_code(self, mock_pdf, mock_code):
        """An already-coded certificate keeps its code (no regeneration)."""
        mock_pdf.return_value = "certificates/2026/01/x.pdf"
        cert = CertificateFactory(certificate_code="WSS-2026-EXISTINGCODE")

        generate_certificate_pdf_async.run(cert.id)

        cert.refresh_from_db()
        assert cert.certificate_code == "WSS-2026-EXISTINGCODE"
        mock_code.assert_not_called()


@pytest.mark.django_db
class TestTaskRetryBranching:
    """Retry and final-failure paths are mutually exclusive and alert (#78)."""

    def test_retries_while_attempts_remain(self):
        """With retries left, the task raises self.retry (does not give up)."""
        cert = CertificateFactory(certificate_code="WSS-2026-RETRYTEST01")

        generate_certificate_pdf_async.push_request(retries=0)
        try:
            with (
                patch(
                    "apps.certificates.tasks.generate_certificate_pdf",
                    side_effect=Exception("boom"),
                ),
                patch.object(
                    generate_certificate_pdf_async, "retry", side_effect=Retry
                ) as mock_retry,
            ):
                with pytest.raises(Retry):
                    generate_certificate_pdf_async.run(cert.id)
            mock_retry.assert_called_once()
        finally:
            generate_certificate_pdf_async.pop_request()

        cert.refresh_from_db()
        assert cert.pdf_generation_failed_at is None

    def test_final_failure_does_not_retry_and_alerts(self):
        """On the last attempt the task marks failure, alerts Sentry, and stops.

        It must NOT call self.retry again (the old code double-retried, raising
        MaxRetriesExceededError instead of recording a clean permanent failure).
        """
        cert = CertificateFactory(certificate_code="WSS-2026-FINALTEST01")
        max_retries = generate_certificate_pdf_async.max_retries

        generate_certificate_pdf_async.push_request(retries=max_retries)
        try:
            with (
                patch(
                    "apps.certificates.tasks.generate_certificate_pdf",
                    side_effect=Exception("boom"),
                ),
                patch.object(generate_certificate_pdf_async, "retry") as mock_retry,
                patch(
                    "apps.certificates.tasks.sentry_sdk.capture_exception"
                ) as mock_capture,
            ):
                # Must return cleanly, not raise.
                generate_certificate_pdf_async.run(cert.id)

            mock_retry.assert_not_called()
            mock_capture.assert_called_once()
        finally:
            generate_certificate_pdf_async.pop_request()

        cert.refresh_from_db()
        assert cert.pdf_generation_failed_at is not None
        assert cert.is_valid is True
        # The code assigned before the PDF step persists across the failure.
        assert cert.certificate_code == "WSS-2026-FINALTEST01"

    @patch("apps.certificates.tasks.generate_certificate_pdf")
    def test_task_noops_when_pdf_present(self, mock_pdf):
        """Idempotency guard: an existing PDF is never regenerated (#73)."""
        cert = CertificateFactory(certificate_code="WSS-2026-HASPDF0001")
        cert.pdf_file = "certificates/2026/01/existing.pdf"
        cert.save(update_fields=["pdf_file"])

        generate_certificate_pdf_async.run(cert.id)

        mock_pdf.assert_not_called()


@pytest.mark.django_db
class TestTaskMissingCertificate:
    """A certificate deleted between enqueue and execution is swallowed."""

    @patch("apps.certificates.tasks.generate_certificate_pdf")
    def test_missing_certificate_is_swallowed(self, mock_pdf, caplog):
        """A non-existent id returns cleanly (no exception, no PDF render).

        The signal enqueues by id; if the row is deleted before the worker
        runs, the task must log and stop instead of crashing the worker.
        """
        cert = CertificateFactory(certificate_code="WSS-2026-DELETED001")
        stale_id = cert.id
        cert.delete()

        with caplog.at_level(logging.ERROR, logger="apps.certificates.tasks"):
            result = generate_certificate_pdf_async.run(stale_id)

        assert result is None
        mock_pdf.assert_not_called()
        assert any(str(stale_id) in record.getMessage() for record in caplog.records)
