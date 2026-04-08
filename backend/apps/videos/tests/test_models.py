"""Tests for Video and Lesson models."""

import pytest
from datetime import timedelta

from apps.videos.factories import LessonFactory, VideoFactory
from apps.courses.factories import CourseFactory


@pytest.mark.django_db
class TestVideoModel:
    """Test suite for the Video model."""

    def test_create_video_with_valid_data(self):
        """Video is created with expected attributes."""
        video = VideoFactory(title="Intro to Django")
        assert video.pk is not None
        assert video.title == "Intro to Django"
        assert video.is_processed is False

    def test_video_str_returns_title(self):
        """__str__ returns video title."""
        video = VideoFactory(title="REST Framework Basics")
        assert str(video) == "REST Framework Basics"

    def test_file_size_mb_returns_correct_value(self):
        """file_size_mb property converts bytes to MB."""
        video = VideoFactory(file_size=10 * 1024 * 1024)  # 10 MB
        assert video.file_size_mb == 10.0

    def test_file_size_mb_returns_zero_when_no_file(self):
        """file_size_mb returns 0 when file_size is 0."""
        video = VideoFactory(file_size=0)
        assert video.file_size_mb == 0

    def test_duration_formatted_with_duration(self):
        """duration_formatted returns HH:MM:SS string."""
        video = VideoFactory()
        video.duration = timedelta(hours=1, minutes=30, seconds=45)
        assert video.duration_formatted == "01:30:45"

    def test_duration_formatted_without_duration(self):
        """duration_formatted returns 00:00:00 when no duration set."""
        video = VideoFactory()
        video.duration = None
        assert video.duration_formatted == "00:00:00"


@pytest.mark.django_db
class TestLessonModel:
    """Test suite for the Lesson model."""

    def test_create_lesson_with_valid_data(self):
        """Lesson is created with expected attributes."""
        lesson = LessonFactory(title="Django ORM")
        assert lesson.pk is not None
        assert lesson.title == "Django ORM"
        assert lesson.is_free_preview is False

    def test_lesson_str_returns_formatted_string(self):
        """__str__ returns 'Course - Lesson N: Title' format."""
        course = CourseFactory(title="Django Mastery")
        lesson = LessonFactory(course=course, order=3, title="Signals")
        assert str(lesson) == "Django Mastery - Lesson 3: Signals"

    def test_get_next_lesson_returns_next(self):
        """get_next_lesson returns the subsequent lesson by order."""
        course = CourseFactory()
        lesson1 = LessonFactory(course=course, order=1)
        lesson2 = LessonFactory(course=course, order=2)
        assert lesson1.get_next_lesson() == lesson2

    def test_get_next_lesson_returns_none_when_last(self):
        """get_next_lesson returns None for the last lesson."""
        course = CourseFactory()
        LessonFactory(course=course, order=1)
        lesson2 = LessonFactory(course=course, order=2)
        assert lesson2.get_next_lesson() is None

    def test_get_previous_lesson_returns_previous(self):
        """get_previous_lesson returns the preceding lesson by order."""
        course = CourseFactory()
        lesson1 = LessonFactory(course=course, order=1)
        lesson2 = LessonFactory(course=course, order=2)
        assert lesson2.get_previous_lesson() == lesson1

    def test_get_previous_lesson_returns_none_when_first(self):
        """get_previous_lesson returns None for the first lesson."""
        course = CourseFactory()
        lesson1 = LessonFactory(course=course, order=1)
        assert lesson1.get_previous_lesson() is None

    def test_duration_formatted_in_minutes(self):
        """duration_formatted returns 'Xmin' when under 1 hour."""
        lesson = LessonFactory(duration=45)
        assert lesson.duration_formatted == "45min"

    def test_duration_formatted_in_hours_and_minutes(self):
        """duration_formatted returns 'Xh Ymin' when >= 1 hour."""
        lesson = LessonFactory(duration=90)
        assert lesson.duration_formatted == "1h 30min"

    def test_free_preview_trait(self):
        """Trait 'free_preview' sets is_free_preview=True and order=1."""
        lesson = LessonFactory(free_preview=True)
        assert lesson.is_free_preview is True
        assert lesson.order == 1

    def test_unique_together_course_order(self):
        """Two lessons in the same course cannot have the same order."""
        from django.db import IntegrityError

        course = CourseFactory()
        LessonFactory(course=course, order=5)
        with pytest.raises(IntegrityError):
            LessonFactory(course=course, order=5)
