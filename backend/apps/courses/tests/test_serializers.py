"""Tests for Module serializers."""

from rest_framework.test import APIRequestFactory

import pytest

from apps.courses.factories import CourseFactory, ModuleFactory
from apps.courses.serializers import (
    CourseUpdateSerializer,
    ModuleSerializer,
    ModuleWithLessonsSerializer,
)
from apps.users.factories import InstructorFactory
from apps.videos.factories import LessonFactory


def _build_context(user):
    """Build a serializer context with an authenticated request."""
    request = APIRequestFactory().post("/api/modules/")
    request.user = user
    return {"request": request}


@pytest.mark.django_db
class TestModuleSerializer:
    """Tests for ModuleSerializer (CRUD).

    Ownership is enforced by IsModuleCourseInstructorOrReadOnly, not here
    (#122) — see apps/courses/tests/test_views.py::TestModuleViewSet for
    the 403-on-non-owner-create coverage.
    """

    def test_valid_payload_passes(self):
        """Instructor of the course passes validation."""
        course = CourseFactory()
        payload = {
            "course": course.pk,
            "title": "Fundamentals",
            "description": "Intro module",
            "order": 1,
        }
        serializer = ModuleSerializer(
            data=payload, context=_build_context(course.instructor)
        )
        assert serializer.is_valid(), serializer.errors
        module = serializer.save()
        assert module.title == "Fundamentals"
        assert module.course == course

    def test_duplicate_order_rejected(self):
        """Two modules with same (course, order) are rejected at validation."""
        course = CourseFactory()
        ModuleFactory(course=course, order=1)
        payload = {
            "course": course.pk,
            "title": "Dup",
            "order": 1,
        }
        serializer = ModuleSerializer(
            data=payload, context=_build_context(course.instructor)
        )
        assert not serializer.is_valid()
        # DRF's UniqueTogetherValidator surfaces the error as non_field_errors
        assert "non_field_errors" in serializer.errors

    def test_lessons_count_returned(self):
        """lessons_count reflects related lessons."""
        course = CourseFactory()
        module = ModuleFactory(course=course, order=1)
        LessonFactory(course=course, module=module, order=1)
        LessonFactory(course=course, module=module, order=2)
        serializer = ModuleSerializer(module)
        assert serializer.data["lessons_count"] == 2

    def test_update_does_not_conflict_with_self(self):
        """Updating the same module without changing order is allowed."""
        course = CourseFactory()
        module = ModuleFactory(course=course, order=2, title="Old")
        payload = {
            "course": course.pk,
            "title": "New",
            "order": 2,
        }
        serializer = ModuleSerializer(
            module, data=payload, context=_build_context(course.instructor)
        )
        assert serializer.is_valid(), serializer.errors
        updated = serializer.save()
        assert updated.title == "New"


@pytest.mark.django_db
class TestCourseUpdateSerializer:
    """CourseUpdateSerializer must not perform authorization (that belongs to permissions)."""

    def _context(self, user):
        request = APIRequestFactory().patch("/api/courses/1/")
        request.user = user
        return {"request": request}

    def test_does_not_enforce_ownership_at_validation(self):
        """A non-owner is not rejected at validation (authz returns 403 via permissions)."""
        course = CourseFactory()
        other_instructor = InstructorFactory()
        serializer = CourseUpdateSerializer(
            course,
            data={"title": "Renamed"},
            partial=True,
            context=self._context(other_instructor),
        )
        assert serializer.is_valid(), serializer.errors


@pytest.mark.django_db
class TestModuleWithLessonsSerializer:
    """Tests for the nested read-only Module serializer."""

    def test_lessons_are_nested_and_ordered(self):
        """Nested lessons are returned ordered by 'order'."""
        course = CourseFactory()
        module = ModuleFactory(course=course, order=1)
        LessonFactory(course=course, module=module, order=2, title="Second")
        LessonFactory(course=course, module=module, order=1, title="First")
        data = ModuleWithLessonsSerializer(module).data
        titles = [lesson["title"] for lesson in data["lessons"]]
        assert titles == ["First", "Second"]
