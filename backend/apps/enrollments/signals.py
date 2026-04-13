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

    total_lessons = enrollment.course.lessons.count()
    if total_lessons == 0:
        return

    completed_count = enrollment.lesson_progress.filter(completed=True).count()

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
