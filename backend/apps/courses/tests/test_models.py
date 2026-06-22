"""Tests for Category, Course and Module models."""

import pytest

from apps.courses.factories import CategoryFactory, CourseFactory, ModuleFactory
from apps.courses.models import Course, Module


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

    def test_slug_collision_gets_unique_suffix(self):
        """Distinct names that slugify to the same base get unique slugs."""
        cat1 = CategoryFactory(name="Programação", slug="")
        cat2 = CategoryFactory(name="Programacao", slug="")
        assert cat1.slug == "programacao"
        assert cat2.slug == "programacao-2"


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

    def test_slug_collision_gets_unique_suffix(self):
        """Distinct titles that slugify to the same base get unique slugs."""
        course1 = CourseFactory(title="Programação", slug="")
        course2 = CourseFactory(title="Programacao", slug="")
        assert course1.slug == "programacao"
        assert course2.slug == "programacao-2"

    def test_negative_price_fails_full_clean(self):
        """A negative price is rejected by model validation (admin/full_clean)."""
        from decimal import Decimal

        from django.core.exceptions import ValidationError

        course = CourseFactory()
        course.price = Decimal("-5.00")
        with pytest.raises(ValidationError):
            course.full_clean()

    def test_clean_blocks_publishing_without_lessons(self):
        """Publishing a course with zero lessons is rejected (admin/full_clean)."""
        from django.core.exceptions import ValidationError

        course = CourseFactory(is_published=False)
        course.is_published = True
        with pytest.raises(ValidationError):
            course.full_clean()

    def test_clean_allows_publishing_with_lessons(self):
        """A course with at least one lesson can be published."""
        from apps.videos.factories import LessonFactory

        course = CourseFactory(is_published=False)
        LessonFactory(course=course, order=1)
        course.is_published = True
        course.full_clean()  # must not raise

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


@pytest.mark.django_db
class TestModuleModel:
    """Test suite for the Module model."""

    def test_create_module_with_valid_data(self):
        """Module is created with expected attributes."""
        module = ModuleFactory(title="Fundamentals", order=1)
        assert module.pk is not None
        assert module.title == "Fundamentals"
        assert module.order == 1

    def test_module_str_returns_formatted_string(self):
        """__str__ returns 'Course - Module N: Title' format."""
        course = CourseFactory(title="Django Mastery")
        module = ModuleFactory(course=course, order=2, title="Advanced Topics")
        assert str(module) == "Django Mastery - Module 2: Advanced Topics"

    def test_modules_ordered_by_course_then_order(self):
        """Module Meta.ordering returns modules sorted by course and order."""
        course = CourseFactory()
        m2 = ModuleFactory(course=course, order=2)
        m1 = ModuleFactory(course=course, order=1)
        assert list(Module.objects.filter(course=course)) == [m1, m2]

    def test_unique_together_course_order(self):
        """Two modules in the same course cannot share the same order."""
        from django.db import IntegrityError

        course = CourseFactory()
        ModuleFactory(course=course, order=1)
        with pytest.raises(IntegrityError):
            ModuleFactory(course=course, order=1)

    def test_same_order_allowed_in_different_courses(self):
        """Modules from different courses may share an order value."""
        c1 = CourseFactory()
        c2 = CourseFactory()
        m1 = ModuleFactory(course=c1, order=1)
        m2 = ModuleFactory(course=c2, order=1)
        assert m1.pk != m2.pk
        assert m1.order == m2.order == 1

    def test_course_modules_reverse_relation(self):
        """Course exposes its modules via 'modules' related_name."""
        course = CourseFactory()
        ModuleFactory(course=course, order=1)
        ModuleFactory(course=course, order=2)
        assert course.modules.count() == 2

    def test_cascade_delete_with_course(self):
        """Deleting a course also deletes its modules."""
        course = CourseFactory()
        ModuleFactory(course=course, order=1)
        ModuleFactory(course=course, order=2)
        course_id = course.id
        course.delete()
        assert Module.objects.filter(course_id=course_id).count() == 0
