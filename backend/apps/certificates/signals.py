"""
Certificate Signals Module

This module contains Django signal handlers for the certificates application.
It is responsible for automating the certificate generation process when
enrollments are completed.

Purpose:
    - Listens to post_save signals from the Enrollment model
    - Automatically generates certificates when an enrollment reaches completion
    - Ensures certificate code uniqueness and prevents duplicate certificate generation
    - Orchestrates PDF generation and storage

Integration:
    - Works with apps.enrollments.models.Enrollment: Listens for completion status changes
    - Works with apps.certificates.models.Certificate: Creates and manages certificate records
    - Works with apps.certificates.utils: Uses utility functions for code generation and PDF creation
    - Integrates seamlessly with Django's signal dispatcher for automatic triggers

Signal Flow:
    Enrollment marked as completed -> post_save signal triggered -> Certificate created ->
    PDF generated and associated -> Certificate fully persisted to database
"""

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from apps.certificates.models import Certificate
from apps.certificates.utils import generate_certificate_code, generate_certificate_pdf
from apps.enrollments.models import Enrollment

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Enrollment)
def create_certificate_on_completion(sender, instance, created, **kwargs):
    """
    Signal to automatically generate a certificate when an enrollment is completed.

    Logic:
    - Detects when enrollment.completed changes to True
    - Verifies if a certificate already exists for this enrollment
    - Generates a unique code
    - Creates a Certificate object
    - Generates and saves the PDF automatically

    Args:
        sender: Model class (Enrollment)
        instance: Instance of the saved Enrollment
        created: Boolean indicating if it is a new record
        **kwargs: Extra signal arguments
    """

    if not instance.completed or not instance.completed_at:
        return

    if Certificate.objects.filter(enrollment=instance).exists():
        logger.debug(f"Certificate already exists for enrollment {instance.id}")
        return

    logger.info(
        f"Starting certificate generation for enrollment {instance.id} "
        f"(user: {instance.user.email}, course: {instance.course.title})"
    )

    code = generate_certificate_code()

    certificate = Certificate.objects.create(
        enrollment=instance, certificate_code=code, is_valid=False
    )
    logger.info(f"Certificate object created with code: {code}")

    max_retries = 1
    attempt = 0

    while attempt <= max_retries:
        try:
            attempt += 1
            logger.info(f"Generating PDF (attempt {attempt}/{max_retries + 1})")

            pdf_path = generate_certificate_pdf(certificate)

            certificate.pdf_file = pdf_path
            certificate.is_valid = True
            certificate.save()

            logger.info(
                f"Certificate {code} generated successfully on attempt {attempt}"
            )
            break
        except Exception as e:
            logger.error(
                f"PDF generation failed (attempt {attempt}): {str(e)}", exc_info=True
            )

            if attempt > max_retries:
                certificate.pdf_generation_failed_at = timezone.now()
                certificate.save()

                logger.error(
                    f"Certificate {code} failed after {max_retries + 1} attempts. "
                    f"Manual intervention required."
                )
