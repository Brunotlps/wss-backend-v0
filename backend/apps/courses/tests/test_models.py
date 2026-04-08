"""Tests for Category and Course models."""

import pytest

from apps.courses.factories import CategoryFactory, CourseFactory
from apps.courses.models import Course


@pytest.mark.django_db
class TestCategoryModel:
    """Test suite for the Category model."""

    def test_create_category_with_valid_data(self):
        """Category is created with expected attributes."""
        cat = CategoryFactory(name="Web Development", slug="web-development")
        assert cat.pk is not None
        assert cat.name == "Web Development"
        assert cat.is_active is True

    def test_category_str_returns_name(self):
        """__str__ returns category name."""
        cat = CategoryFactory(name="Data Science")
        assert str(cat) == "Data Science"

    def test_slug_auto_generated_on_save(self):
        """Slug is auto-generated from name when not provided."""
        cat = CategoryFactory.build(name="Machine Learning", slug="")
        cat.save()
        assert cat.slug == "machine-learning"

    def test_category_name_is_unique(self):
        """Two categories cannot share the same name."""
        from django.db import IntegrityError

        CategoryFactory(name="Unique Cat")
        with pytest.raises(IntegrityError):
            CategoryFactory(name="Unique Cat")


@pytest.mark.django_db
class TestCourseModel:
    """Test suite for the Course model."""

    def test_create_course_with_valid_data(self):
        """Course is created with expected attributes."""
        course = CourseFactory(title="Django Basics")
        assert course.pk is not None
        assert course.title == "Django Basics"
        assert course.is_published is True

    def test_course_str_returns_title(self):
        """__str__ returns course title."""
        course = CourseFactory(title="REST APIs")
        assert str(course) == "REST APIs"

    def test_is_free_returns_true_for_zero_price(self):
        """is_free property returns True when price is 0."""
        course = CourseFactory(price=0)
        assert course.is_free is True

    def test_is_free_returns_false_for_positive_price(self):
        """is_free property returns False when price > 0."""
        course = CourseFactory(price=99.90)
        assert course.is_free is False

    def test_slug_auto_generated_on_save(self):
        """Slug is auto-generated from title when not provided."""
        course = CourseFactory(title="Django Advanced Unique", slug="")
        course.refresh_from_db()
        assert course.slug == "django-advanced-unique"

    def test_get_enrolled_count_no_enrollments(self):
        """get_enrolled_count() returns 0 when no enrollments exist."""
        course = CourseFactory()
        assert course.get_enrolled_count() == 0

    def test_difficulty_level_choices(self):
        """Course difficulty uses valid TextChoices values."""
        course = CourseFactory(difficulty=Course.DifficultyLevel.BEGINNER)
        assert course.difficulty == "BEG"

    def test_course_linked_to_instructor(self):
        """Course has an instructor FK pointing to a User."""
        course = CourseFactory()
        assert course.instructor is not None
        assert course.instructor.is_instructor is True
