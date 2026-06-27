"""
Certificate Signals Module.

Listens to Enrollment post_save events and creates a Certificate record
when an enrollment is completed. PDF generation is delegated to a Celery
task to avoid blocking the request/response cycle.

Signal flow:
    Enrollment saved (completed=True)
      -> create_certificate_on_completion
        -> Certificate.objects.get_or_create()  (lightweight, race-safe)
        -> generate_certificate_pdf_async.delay(certificate.id)
"""

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.certificates.models import Certificate
from apps.enrollments.models import Enrollment

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Enrollment)
def create_certificate_on_completion(sender, instance, created, **kwargs):
    """Create a certificate and enqueue PDF generation when enrollment completes.

    The signal stays lightweight: it only persists the certificate row (with a
    denormalized snapshot) and delegates the heavier work — unique code
    generation and PDF rendering — to the Celery task (#80).

    Args:
        sender: Enrollment model class.
        instance: The saved Enrollment instance.
        created: True if this is a new record.
        **kwargs: Extra signal arguments.
    """
    if not instance.completed or not instance.completed_at:
        return

    # Capture a denormalized snapshot at issue time so the certificate is an
    # immutable, durable document — later edits/deletes of the source
    # course/user/enrollment never change it (#77). is_valid is left at its
    # default (True = not revoked); PDF readiness is tracked separately by
    # pdf_file (#73). The certificate_code is assigned by the task (#80).
    user = instance.user
    instructor = instance.course.instructor
    certificate, was_created = Certificate.objects.get_or_create(
        enrollment=instance,
        defaults={
            "student_name_snapshot": user.get_full_name() or user.email,
            "course_title_snapshot": instance.course.title,
            "instructor_name_snapshot": (
                (instructor.get_full_name() or instructor.email) if instructor else ""
            ),
            "completion_date_snapshot": instance.completed_at,
        },
    )

    # get_or_create is race-safe: a concurrent double-save no-ops instead of
    # raising a raw IntegrityError to the caller (#79).
    if not was_created:
        logger.debug("Certificate already exists for enrollment %d.", instance.id)
        return

    logger.info(
        "Certificate created for enrollment %d — queuing PDF generation.",
        instance.id,
    )

    from apps.certificates.tasks import generate_certificate_pdf_async

    generate_certificate_pdf_async.delay(certificate.id)
