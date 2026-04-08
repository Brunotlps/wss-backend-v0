"""Tests for Enrollment and LessonProgress models."""

import pytest
from django.core.cache import cache
from django.db import IntegrityError

from apps.courses.factories import CourseFactory
from apps.enrollments.factories import EnrollmentFactory, LessonProgressFactory
from apps.users.factories import UserFactory
from apps.videos.factories import LessonFactory


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.mark.django_db
class TestEnrollmentModel:
    """Test suite for the Enrollment model."""

    def test_create_enrollment_with_valid_data(self):
        """Enrollment is created with expected defaults."""
        enrollment = EnrollmentFactory()
        assert enrollment.pk is not None
        assert enrollment.is_active is True
        assert enrollment.completed is False
        assert enrollment.certificate_issued is False

    def test_enrollment_str_format(self):
        """__str__ returns 'FullName → CourseTitle' format."""
        user = UserFactory(first_name="Ana", last_name="Lima")
        course = CourseFactory(title="Django REST")
        enrollment = EnrollmentFactory(user=user, course=course)
        assert str(enrollment) == "Ana Lima → Django REST"

    def test_unique_together_user_course(self):
        """User cannot enroll in the same course twice."""
        user = UserFactory()
        course = CourseFactory()
        EnrollmentFactory(user=user, course=course)
        with pytest.raises(IntegrityError):
            EnrollmentFactory(user=user, course=course)

    def test_progress_percentage_no_lessons(self):
        """progress_percentage returns 0 when course has no lessons."""
        enrollment = EnrollmentFactory()
        assert enrollment.progress_percentage == 0

    def test_progress_percentage_partial(self):
        """progress_percentage reflects completed lessons ratio."""
        course = CourseFactory()
        enrollment = EnrollmentFactory(course=course)
        lesson1 = LessonFactory(course=course, order=1)
        lesson2 = LessonFactory(course=course, order=2)
        LessonProgressFactory(
            enrollment=enrollment, lesson=lesson1, completed=True
        )
        LessonProgressFactory(
            enrollment=enrollment, lesson=lesson2, completed=False
        )
        assert enrollment.progress_percentage == 50.0

    def test_progress_percentage_all_completed(self):
        """progress_percentage returns 100 when all lessons are done."""
        course = CourseFactory()
        enrollment = EnrollmentFactory(course=course)
        lesson1 = LessonFactory(course=course, order=1)
        lesson2 = LessonFactory(course=course, order=2)
        LessonProgressFactory(
            enrollment=enrollment, lesson=lesson1, completed=True
        )
        LessonProgressFactory(
            enrollment=enrollment, lesson=lesson2, completed=True
        )
        assert enrollment.progress_percentage == 100.0

    def test_total_watched_duration_returns_sum(self):
        """total_watched_duration sums watched minutes across lessons."""
        course = CourseFactory()
        enrollment = EnrollmentFactory(course=course)
        lesson1 = LessonFactory(course=course, order=1)
        lesson2 = LessonFactory(course=course, order=2)
        LessonProgressFactory(
            enrollment=enrollment, lesson=lesson1, watched_duration=20
        )
        LessonProgressFactory(
            enrollment=enrollment, lesson=lesson2, watched_duration=35
        )
        assert enrollment.total_watched_duration == 55

    def test_total_watched_duration_returns_zero_when_none(self):
        """total_watched_duration returns 0 when no progress exists."""
        enrollment = EnrollmentFactory()
        assert enrollment.total_watched_duration == 0

    def test_mark_as_completed_sets_completed_and_timestamp(self):
        """mark_as_completed sets completed=True and completed_at."""
        enrollment = EnrollmentFactory()
        enrollment.mark_as_completed()
        enrollment.refresh_from_db()
        assert enrollment.completed is True
        assert enrollment.completed_at is not None

    def test_get_next_lesson_returns_first_incomplete(self):
        """get_next_lesson returns first lesson not yet completed."""
        course = CourseFactory()
        enrollment = EnrollmentFactory(course=course)
        lesson1 = LessonFactory(course=course, order=1)
        lesson2 = LessonFactory(course=course, order=2)
        LessonProgressFactory(
            enrollment=enrollment, lesson=lesson1, completed=True
        )
        LessonProgressFactory(
            enrollment=enrollment, lesson=lesson2, completed=False
        )
        assert enrollment.get_next_lesson() == lesson2

    def test_get_next_lesson_returns_none_when_all_done(self):
        """get_next_lesson returns None when all lessons are completed."""
        course = CourseFactory()
        enrollment = EnrollmentFactory(course=course)
        lesson = LessonFactory(course=course, order=1)
        LessonProgressFactory(
            enrollment=enrollment, lesson=lesson, completed=True
        )
        assert enrollment.get_next_lesson() is None

    def test_save_invalidates_enrollment_cache(self):
        """Saving enrollment invalidates the enrollment cache."""
        enrollment = EnrollmentFactory()
        cache_key = f"enrollment:{enrollment.user_id}:{enrollment.course_id}"
        cache.set(cache_key, True, 900)
        enrollment.save()
        assert cache.get(cache_key) is None

    def test_delete_invalidates_enrollment_cache(self):
        """Deleting enrollment invalidates the enrollment cache."""
        enrollment = EnrollmentFactory()
        cache_key = f"enrollment:{enrollment.user_id}:{enrollment.course_id}"
        cache.set(cache_key, True, 900)
        enrollment.delete()
        assert cache.get(cache_key) is None

    # BUG DOCUMENTATION: enrollment has no payment verification
    def test_enrollment_created_without_payment_verification(self):
        """
        BUG: Enrollment can be created for a paid course without payment.

        This test documents the current (incorrect) behavior.
        Expected future behavior: paid courses should require payment before enrollment.
        Tracking: see CLAUDE.md > Critical Issue.
        """
        paid_course = CourseFactory(price=99.90)
        user = UserFactory()
        # Currently, enrollment is created freely regardless of price
        enrollment = EnrollmentFactory(user=user, course=paid_course)
        assert enrollment.pk is not None  # Bug: should require payment first


@pytest.mark.django_db
class TestLessonProgressModel:
    """Test suite for LessonProgress model."""

    def test_create_lesson_progress_with_defaults(self):
        """LessonProgress is created with correct defaults."""
        progress = LessonProgressFactory()
        assert progress.pk is not None
        assert progress.completed is False
        assert progress.watched_duration == 0

    def test_lesson_progress_str_format(self):
        """__str__ returns '○ Name - Lesson' or '✓ Name - Lesson'."""
        user = UserFactory(first_name="Carlos", last_name="Melo")
        course = CourseFactory()
        enrollment = EnrollmentFactory(user=user, course=course)
        lesson = LessonFactory(course=course, order=1, title="Intro")
        progress = LessonProgressFactory(
            enrollment=enrollment, lesson=lesson, completed=False
        )
        assert "Carlos Melo" in str(progress)
        assert "Intro" in str(progress)
        assert "○" in str(progress)

    def test_completed_lesson_progress_str_uses_check(self):
        """Completed LessonProgress uses '✓' in __str__."""
        progress = LessonProgressFactory(completed=True)
        assert "✓" in str(progress)

    def test_progress_percentage_with_watched_duration(self):
        """progress_percentage calculates based on watched vs total duration."""
        lesson = LessonFactory(duration=60)
        enrollment = EnrollmentFactory()
        progress = LessonProgressFactory(
            enrollment=enrollment, lesson=lesson, watched_duration=30
        )
        assert progress.progress_percentage == 50.0

    def test_progress_percentage_caps_at_100(self):
        """progress_percentage never exceeds 100%."""
        lesson = LessonFactory(duration=10)
        enrollment = EnrollmentFactory()
        progress = LessonProgressFactory(
            enrollment=enrollment, lesson=lesson, watched_duration=20
        )
        assert progress.progress_percentage == 100.0

    def test_mark_as_completed_sets_fields(self):
        """mark_as_completed sets completed, completed_at, watched_duration."""
        lesson = LessonFactory(duration=45)
        enrollment = EnrollmentFactory()
        progress = LessonProgressFactory(
            enrollment=enrollment, lesson=lesson, watched_duration=0
        )
        progress.mark_as_completed()
        progress.refresh_from_db()
        assert progress.completed is True
        assert progress.completed_at is not None
        assert progress.watched_duration == 45

    def test_update_watched_duration_accumulates(self):
        """update_watched_duration adds to existing watched time."""
        lesson = LessonFactory(duration=60)
        enrollment = EnrollmentFactory()
        progress = LessonProgressFactory(
            enrollment=enrollment, lesson=lesson, watched_duration=10
        )
        progress.update_watched_duration(20)
        progress.refresh_from_db()
        assert progress.watched_duration == 30

    def test_update_watched_duration_does_not_exceed_lesson_duration(self):
        """update_watched_duration caps at lesson.duration."""
        lesson = LessonFactory(duration=30)
        enrollment = EnrollmentFactory()
        progress = LessonProgressFactory(
            enrollment=enrollment, lesson=lesson, watched_duration=25
        )
        progress.update_watched_duration(20)  # would be 45, capped at 30
        progress.refresh_from_db()
        assert progress.watched_duration == 30

    def test_unique_together_enrollment_lesson(self):
        """Can't create two progress records for the same enrollment+lesson."""
        enrollment = EnrollmentFactory()
        lesson = LessonFactory()
        LessonProgressFactory(enrollment=enrollment, lesson=lesson)
        with pytest.raises(IntegrityError):
            LessonProgressFactory(enrollment=enrollment, lesson=lesson)
