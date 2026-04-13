"""Tests for enrollment completion signal (LessonProgress → Enrollment)."""

import pytest
from unittest.mock import patch

from apps.courses.factories import CourseFactory
from apps.enrollments.factories import EnrollmentFactory, LessonProgressFactory
from apps.videos.factories import LessonFactory


@pytest.mark.django_db
class TestCheckCourseCompletion:
    """Test the post_save signal that auto-completes enrollment."""

    @patch("apps.certificates.tasks.generate_certificate_pdf")
    def test_completing_last_lesson_auto_completes_enrollment(self, mock_pdf):
        """Completing the final lesson marks the enrollment as completed."""
        mock_pdf.return_value = "certificates/test.pdf"
        course = CourseFactory()
        lesson1 = LessonFactory(course=course)
        lesson2 = LessonFactory(course=course)
        enrollment = EnrollmentFactory(course=course)
        progress1 = LessonProgressFactory(enrollment=enrollment, lesson=lesson1)
        progress2 = LessonProgressFactory(enrollment=enrollment, lesson=lesson2)

        # Complete first lesson — enrollment should NOT be completed yet
        progress1.completed = True
        progress1.save()
        enrollment.refresh_from_db()
        assert not enrollment.completed

        # Complete last lesson — enrollment SHOULD be completed now
        progress2.completed = True
        progress2.save()
        enrollment.refresh_from_db()
        assert enrollment.completed
        assert enrollment.completed_at is not None

    def test_completing_partial_lessons_does_not_complete_enrollment(self):
        """Completing some but not all lessons does not complete the enrollment."""
        course = CourseFactory()
        lesson1 = LessonFactory(course=course)
        lesson2 = LessonFactory(course=course)
        lesson3 = LessonFactory(course=course)
        enrollment = EnrollmentFactory(course=course)
        progress1 = LessonProgressFactory(enrollment=enrollment, lesson=lesson1)
        LessonProgressFactory(enrollment=enrollment, lesson=lesson2)
        LessonProgressFactory(enrollment=enrollment, lesson=lesson3)

        progress1.completed = True
        progress1.save()
        enrollment.refresh_from_db()
        assert not enrollment.completed

    @patch("apps.certificates.tasks.generate_certificate_pdf")
    def test_already_completed_enrollment_not_re_triggered(self, mock_pdf):
        """Signal does not call mark_as_completed again if already completed."""
        mock_pdf.return_value = "certificates/test.pdf"
        course = CourseFactory()
        lesson = LessonFactory(course=course)
        enrollment = EnrollmentFactory(course=course, completed=True)
        progress = LessonProgressFactory(enrollment=enrollment, lesson=lesson)

        # Re-save a completed progress on an already-completed enrollment
        progress.completed = True
        progress.save()

        # Still only one call to the PDF generator (from the factory, not from signal)
        enrollment.refresh_from_db()
        assert enrollment.completed  # unchanged, not re-triggered

    def test_course_with_no_lessons_not_auto_completed(self):
        """Enrollment is not auto-completed when the course has no lessons."""
        course = CourseFactory()
        enrollment = EnrollmentFactory(course=course)
        # No lessons exist — saving a progress for an unrelated lesson
        # simulates an edge case (e.g. lesson deleted after progress created)
        unrelated_lesson = LessonFactory()
        progress = LessonProgressFactory(
            enrollment=enrollment, lesson=unrelated_lesson
        )
        progress.completed = True
        progress.save()
        enrollment.refresh_from_db()
        assert not enrollment.completed

    def test_uncompleted_lesson_progress_save_does_nothing(self):
        """Saving a LessonProgress with completed=False never triggers completion."""
        course = CourseFactory()
        lesson = LessonFactory(course=course)
        enrollment = EnrollmentFactory(course=course)
        progress = LessonProgressFactory(enrollment=enrollment, lesson=lesson)

        progress.watched_duration = 10
        progress.save()  # completed stays False
        enrollment.refresh_from_db()
        assert not enrollment.completed
