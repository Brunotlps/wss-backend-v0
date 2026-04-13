"""
Certificate Signals Module.

Listens to Enrollment post_save events and creates a Certificate record
when an enrollment is completed. PDF generation is delegated to a Celery
task to avoid blocking the request/response cycle.

Signal flow:
    Enrollment saved (completed=True)
      -> create_certificate_on_completion
        -> Certificate.objects.create()
        -> generate_certificate_pdf_async.delay(certificate.id)
"""

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.certificates.models import Certificate
from apps.certificates.utils import generate_certificate_code
from apps.enrollments.models import Enrollment

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Enrollment)
def create_certificate_on_completion(sender, instance, created, **kwargs):
    """Create a certificate and enqueue PDF generation when enrollment completes.

    Args:
        sender: Enrollment model class.
        instance: The saved Enrollment instance.
        created: True if this is a new record.
        **kwargs: Extra signal arguments.
    """
    if not instance.completed or not instance.completed_at:
        return

    if Certificate.objects.filter(enrollment=instance).exists():
        logger.debug("Certificate already exists for enrollment %d.", instance.id)
        return

    code = generate_certificate_code()
    certificate = Certificate.objects.create(
        enrollment=instance, certificate_code=code, is_valid=False
    )

    logger.info(
        "Certificate %s created for enrollment %d — queuing PDF generation.",
        code,
        instance.id,
    )

    from apps.certificates.tasks import generate_certificate_pdf_async

    generate_certificate_pdf_async.delay(certificate.id)
