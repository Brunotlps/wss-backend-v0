"""
Celery tasks for the certificates app.

Handles asynchronous certificate PDF generation so that enrollment
completion does not block the request/response cycle.
"""

import logging

from django.utils import timezone

import sentry_sdk
from celery import shared_task

from apps.certificates.utils import generate_certificate_code, generate_certificate_pdf

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=2, default_retry_delay=60)
def generate_certificate_pdf_async(self, certificate_id: int) -> None:
    """Generate and store the PDF for a certificate asynchronously.

    Assigns the unique validation code if the request signal left it unset
    (#80), then renders the PDF. Retries up to 2 times with a 60-second delay
    on a transient failure; on the final attempt it records
    pdf_generation_failed_at, alerts Sentry, and stops — it does not retry
    again (#78).

    Args:
        certificate_id: Primary key of the Certificate to generate PDF for.
    """
    from apps.certificates.models import Certificate

    try:
        certificate = Certificate.objects.get(id=certificate_id)
    except Certificate.DoesNotExist:
        logger.error(
            "Certificate %d not found — skipping PDF generation.", certificate_id
        )
        return

    # Idempotency guard keyed on PDF presence, NOT is_valid (which means
    # revocation only). This prevents a re-run from regenerating the PDF and
    # silently un-revoking a revoked certificate (#73).
    if certificate.pdf_file:
        logger.debug(
            "Certificate %d already has a PDF — skipping generation.", certificate_id
        )
        return

    try:
        # Code generation lives here, off the request hot path (#80). Done
        # once; a retry after a later failure keeps the already-assigned code.
        # Kept inside the try so a code-collision/allocation failure flows
        # through the same retry / final-failure handling as PDF errors (#78).
        if not certificate.certificate_code:
            certificate.certificate_code = generate_certificate_code()
            certificate.save(update_fields=["certificate_code"])

        logger.info(
            "Generating PDF for certificate %d (code: %s).",
            certificate_id,
            certificate.certificate_code,
        )

        pdf_path = generate_certificate_pdf(certificate)
        certificate.pdf_file = pdf_path
        # Do NOT touch is_valid here — it is the revocation flag, independent
        # of PDF generation (#73).
        certificate.save(update_fields=["pdf_file"])
        logger.info("PDF generated successfully for certificate %d.", certificate_id)
    except Exception as exc:
        logger.error(
            "Certificate %d generation failed: %s",
            certificate_id,
            str(exc),
            exc_info=True,
        )
        # Retry and final-failure are mutually exclusive (#78).
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc)

        certificate.pdf_generation_failed_at = timezone.now()
        certificate.save(update_fields=["pdf_generation_failed_at"])
        sentry_sdk.capture_exception(exc)
        logger.error(
            "Certificate %d failed after %d attempts. Manual intervention required.",
            certificate_id,
            self.max_retries + 1,
        )
        return
