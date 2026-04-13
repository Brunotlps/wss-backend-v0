"""
Celery tasks for the certificates app.

Handles asynchronous certificate PDF generation so that enrollment
completion does not block the request/response cycle.
"""

import logging

from celery import shared_task
from django.utils import timezone

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
        logger.error("Certificate %d not found — skipping PDF generation.", certificate_id)
        return

    if certificate.is_valid:
        logger.debug("Certificate %d already has a valid PDF — skipping.", certificate_id)
        return

    logger.info(
        "Generating PDF for certificate %d (code: %s).",
        certificate_id,
        certificate.certificate_code,
    )

    try:
        pdf_path = generate_certificate_pdf(certificate)
        certificate.pdf_file = pdf_path
        certificate.is_valid = True
        certificate.save(update_fields=["pdf_file", "is_valid"])
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
