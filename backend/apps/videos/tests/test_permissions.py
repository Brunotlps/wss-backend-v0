"""Tests for videos permissions: IsEnrolled, IsCourseInstructorOrReadOnly."""

from django.core.cache import cache

from rest_framework import status

import pytest

from apps.courses.factories import CourseFactory
from apps.enrollments.models import Enrollment
from apps.users.factories import InstructorFactory
from apps.videos.factories import LessonFactory, VideoFactory


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear Django cache before each test."""
    cache.clear()
    yield
    cache.clear()


@pytest.mark.django_db
class TestIsEnrolled:
    """Tests for IsEnrolled permission via LessonViewSet."""

    URL = "/api/lessons/"

    def test_free_preview_lesson_accessible_without_enrollment(self, api_client):
        """Lesson flagged is_free_preview is accessible to anyone (#56)."""
        course = CourseFactory(is_published=True)
        lesson = LessonFactory(course=course, order=1, is_free_preview=True)
        response = api_client.get(f"{self.URL}{lesson.pk}/")
        assert response.status_code == status.HTTP_200_OK

    def test_first_lesson_without_preview_flag_requires_enrollment(self, auth_client):
        """order==1 must NOT grant access on its own — only is_free_preview does (#56)."""
        course = CourseFactory(is_published=True)
        lesson = LessonFactory(course=course, order=1, is_free_preview=False)
        response = auth_client.get(f"{self.URL}{lesson.pk}/")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_non_preview_lesson_requires_enrollment(self, auth_client):
        """Non-preview lesson requires enrollment."""
        course = CourseFactory(is_published=True)
        LessonFactory(course=course, order=1, is_free_preview=True)
        lesson2 = LessonFactory(course=course, order=2, is_free_preview=False)
        response = auth_client.get(f"{self.URL}{lesson2.pk}/")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_enrolled_user_can_access_non_free_lesson(self, auth_client):
        """Enrolled user can access non-free lessons."""
        course = CourseFactory(is_published=True)
        LessonFactory(course=course, order=1)
        lesson2 = LessonFactory(course=course, order=2)
        Enrollment.objects.create(user=auth_client.user, course=course, is_active=True)
        response = auth_client.get(f"{self.URL}{lesson2.pk}/")
        assert response.status_code == status.HTTP_200_OK

    def test_staff_can_access_any_lesson(self, staff_client):
        """Staff bypasses enrollment check."""
        course = CourseFactory(is_published=True)
        LessonFactory(course=course, order=1)
        lesson2 = LessonFactory(course=course, order=2)
        response = staff_client.get(f"{self.URL}{lesson2.pk}/")
        assert response.status_code == status.HTTP_200_OK

    def test_instructor_can_access_own_course_lesson(self, instructor_client):
        """Course instructor bypasses enrollment check for their own course."""
        course = CourseFactory(instructor=instructor_client.user, is_published=True)
        LessonFactory(course=course, order=1)
        lesson2 = LessonFactory(course=course, order=2)
        response = instructor_client.get(f"{self.URL}{lesson2.pk}/")
        assert response.status_code == status.HTTP_200_OK

    def test_enrollment_cache_used_on_second_request(self, auth_client):
        """Second request uses cached enrollment check (no extra DB queries)."""
        course = CourseFactory(is_published=True)
        LessonFactory(course=course, order=1)
        lesson2 = LessonFactory(course=course, order=2)
        Enrollment.objects.create(user=auth_client.user, course=course, is_active=True)
        # First request populates cache
        auth_client.get(f"{self.URL}{lesson2.pk}/")
        cache_key = f"enrollment:{auth_client.user.id}:{course.id}"
        assert cache.get(cache_key) is True
        # Second request should still succeed (from cache)
        response = auth_client.get(f"{self.URL}{lesson2.pk}/")
        assert response.status_code == status.HTTP_200_OK

    def test_denial_does_not_mutate_shared_message_state(self, auth_client):
        """Denial must raise PermissionDenied instead of mutating self.message (#58).

        A single permission instance can be reused across multiple objects within
        the same request/view lifecycle; mutating self.message leaks one course's
        title into the next object's denial response.
        """
        from rest_framework.exceptions import PermissionDenied

        from apps.videos.permissions import IsEnrolled

        permission = IsEnrolled()
        course = CourseFactory(is_published=True, title="Django Mastery")
        lesson = LessonFactory(course=course, order=2, is_free_preview=False)

        class DummyRequest:
            method = "GET"
            user = auth_client.user

        with pytest.raises(PermissionDenied) as exc_info:
            permission.has_object_permission(DummyRequest(), None, lesson)

        assert "Django Mastery" in str(exc_info.value.detail)
        assert permission.message == IsEnrolled.message


@pytest.mark.django_db
class TestIsCourseInstructorOrReadOnly:
    """Tests for IsCourseInstructorOrReadOnly via LessonViewSet."""

    URL = "/api/lessons/"

    def test_instructor_can_update_own_course_lesson(self, instructor_client):
        """Course instructor can update their own lesson."""
        course = CourseFactory(instructor=instructor_client.user)
        lesson = LessonFactory(course=course, order=1)
        response = instructor_client.patch(
            f"{self.URL}{lesson.pk}/", {"title": "Updated Title"}
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["title"] == "Updated Title"

    def test_instructor_cannot_update_other_course_lesson(self, instructor_client):
        """Instructor cannot update a lesson from another instructor's course."""
        other_instructor = InstructorFactory()
        course = CourseFactory(instructor=other_instructor, is_published=True)
        lesson = LessonFactory(course=course, order=1)
        response = instructor_client.patch(
            f"{self.URL}{lesson.pk}/", {"title": "Hacked"}
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_student_cannot_create_lesson(self, auth_client):
        """Regular user (non-instructor) gets 403 on POST."""
        course = CourseFactory(is_published=True)
        video = VideoFactory()
        payload = {
            "title": "Unauthorized",
            "course": course.pk,
            "video": video.pk,
            "order": 1,
        }
        response = auth_client.post(self.URL, payload)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_instructor_can_delete_own_lesson(self, instructor_client):
        """Course instructor can delete their own lesson."""
        course = CourseFactory(instructor=instructor_client.user)
        lesson = LessonFactory(course=course, order=1)
        response = instructor_client.delete(f"{self.URL}{lesson.pk}/")
        assert response.status_code == status.HTTP_204_NO_CONTENT
