"""
Enrollment Signals Module.

Listens to LessonProgress saves and auto-completes the parent Enrollment
when all lessons in the course have been marked as completed.

Signal flow:
    LessonProgress saved (completed=True)
      → check_course_completion
        → enrollment.mark_as_completed()
          → Enrollment.save() (completed=True)
            → create_certificate_on_completion (certificates/signals.py)
              → Certificate created + PDF generated
"""

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import LessonProgress

logger = logging.getLogger(__name__)


@receiver(post_save, sender=LessonProgress)
def check_course_completion(sender, instance, **kwargs):
    """Auto-complete enrollment when all course lessons are finished.

    Args:
        sender: LessonProgress model class.
        instance: The saved LessonProgress instance.
        **kwargs: Extra signal arguments.
    """
    if not instance.completed:
        return

    enrollment = instance.enrollment

    if enrollment.completed:
        return

    if not enrollment.is_active:
        # #32: defense in depth (mirrors the #29 cross-course guard) — the
        # serializer already blocks new progress writes on an inactive
        # (e.g. refunded) enrollment, but a progress record could still be
        # marked completed some other way (admin edit, direct ORM access).
        # Revoked access must never auto-complete the course or queue a
        # certificate.
        logger.info(
            "Skipping auto-completion for enrollment %d: inactive.",
            enrollment.id,
        )
        return

    total_lessons = enrollment.course.lessons.count()
    if total_lessons == 0:
        return

    # Defense in depth: count only progress on lessons of THIS enrollment's
    # course, so progress on foreign-course lessons can never complete it
    # (the serializer guard is the primary fix — see #29).
    completed_count = enrollment.lesson_progress.filter(
        completed=True, lesson__course=enrollment.course
    ).count()

    if completed_count >= total_lessons:
        logger.info(
            "Auto-completing enrollment %d: all %d lessons completed "
            "(user: %s, course: %s).",
            enrollment.id,
            total_lessons,
            enrollment.user.email,
            enrollment.course.title,
        )
        enrollment.mark_as_completed()
