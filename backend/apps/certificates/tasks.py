"""
Celery tasks for the certificates app.

Handles asynchronous certificate PDF generation so that enrollment
completion does not block the request/response cycle.
"""

import logging

from django.utils import timezone

from celery import shared_task

from apps.certificates.utils import generate_certificate_pdf

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=2, default_retry_delay=60)
def generate_certificate_pdf_async(self, certificate_id: int) -> None:
    """Generate and store the PDF for a certificate asynchronously.

    Retries up to 2 times with a 60-second delay on failure.
    On final failure, sets pdf_generation_failed_at and logs for
    manual intervention.

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

    logger.info(
        "Generating PDF for certificate %d (code: %s).",
        certificate_id,
        certificate.certificate_code,
    )

    try:
        pdf_path = generate_certificate_pdf(certificate)
        certificate.pdf_file = pdf_path
        # Do NOT touch is_valid here — it is the revocation flag, independent
        # of PDF generation (#73).
        certificate.save(update_fields=["pdf_file"])
        logger.info("PDF generated successfully for certificate %d.", certificate_id)
    except Exception as exc:
        logger.error(
            "PDF generation failed for certificate %d: %s",
            certificate_id,
            str(exc),
            exc_info=True,
        )
        if self.request.retries >= self.max_retries:
            certificate.pdf_generation_failed_at = timezone.now()
            certificate.save(update_fields=["pdf_generation_failed_at"])
            logger.error(
                "Certificate %d failed after %d retries. Manual intervention required.",
                certificate_id,
                self.max_retries + 1,
            )
        raise self.retry(exc=exc)
