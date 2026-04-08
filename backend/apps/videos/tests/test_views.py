"""Tests for Video and Lesson API views."""

import pytest
from rest_framework import status

from apps.courses.factories import CourseFactory
from apps.users.factories import InstructorFactory, UserFactory
from apps.videos.factories import LessonFactory, VideoFactory


@pytest.mark.django_db
class TestVideoViewSet:
    """Tests for /api/videos/ CRUD."""

    URL = "/api/videos/"

    def test_list_videos_is_public(self, api_client):
        """Anonymous users can list videos."""
        VideoFactory.create_batch(3)
        response = api_client.get(self.URL)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 3

    def test_retrieve_video_is_public(self, api_client):
        """Single video can be retrieved without authentication."""
        video = VideoFactory(title="Public Video")
        response = api_client.get(f"{self.URL}{video.pk}/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["title"] == "Public Video"

    def test_create_video_as_instructor_returns_201(self, instructor_client):
        """Instructor can create a video."""
        payload = {"title": "New Video"}
        response = instructor_client.post(self.URL, payload)
        assert response.status_code == status.HTTP_201_CREATED

    def test_create_video_as_student_returns_403(self, auth_client):
        """Regular user cannot create a video."""
        payload = {"title": "Unauthorized Video"}
        response = auth_client.post(self.URL, payload)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_create_video_unauthenticated_returns_401(self, api_client):
        """Unauthenticated user cannot create a video."""
        payload = {"title": "No Auth Video"}
        response = api_client.post(self.URL, payload)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_update_video_as_instructor_returns_200(self, instructor_client):
        """Instructor can update a video."""
        video = VideoFactory(title="Old Title")
        response = instructor_client.patch(
            f"{self.URL}{video.pk}/", {"title": "New Title"}
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["title"] == "New Title"

    def test_delete_video_as_instructor_returns_204(self, instructor_client):
        """Instructor can delete a video."""
        video = VideoFactory()
        response = instructor_client.delete(f"{self.URL}{video.pk}/")
        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_search_videos_by_title(self, api_client):
        """Search param filters videos by title."""
        VideoFactory(title="Django Signals")
        VideoFactory(title="React Hooks")
        response = api_client.get(self.URL, {"search": "Django"})
        assert response.data["count"] == 1
        assert "Django" in response.data["results"][0]["title"]


@pytest.mark.django_db
class TestLessonViewSet:
    """Tests for /api/lessons/ CRUD and visibility."""

    URL = "/api/lessons/"

    def test_list_lessons_only_published_courses_for_anonymous(self, api_client):
        """Anonymous users see only lessons from published courses."""
        course_pub = CourseFactory(is_published=True)
        course_unp = CourseFactory(is_published=False)
        LessonFactory(course=course_pub, order=1)
        LessonFactory(course=course_unp, order=1)
        response = api_client.get(self.URL)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1

    def test_list_lessons_only_published_courses_for_student(self, auth_client):
        """Students see only lessons from published courses."""
        course_pub = CourseFactory(is_published=True)
        course_unp = CourseFactory(is_published=False)
        LessonFactory(course=course_pub, order=1)
        LessonFactory(course=course_unp, order=1)
        response = auth_client.get(self.URL)
        assert response.data["count"] == 1

    def test_instructor_sees_own_unpublished_course_lessons(
        self, instructor_client
    ):
        """Instructor sees lessons from their own unpublished courses."""
        own_course = CourseFactory(
            instructor=instructor_client.user, is_published=False
        )
        other_pub_course = CourseFactory(is_published=True)
        LessonFactory(course=own_course, order=1)
        LessonFactory(course=other_pub_course, order=1)
        response = instructor_client.get(self.URL)
        assert response.data["count"] == 2

    def test_staff_sees_all_lessons(self, staff_client):
        """Staff sees lessons from all courses."""
        course_pub = CourseFactory(is_published=True)
        course_unp = CourseFactory(is_published=False)
        LessonFactory(course=course_pub, order=1)
        LessonFactory(course=course_unp, order=1)
        response = staff_client.get(self.URL)
        assert response.data["count"] == 2

    def test_create_lesson_as_instructor_returns_201(self, instructor_client):
        """Instructor can create a lesson in their own course."""
        course = CourseFactory(instructor=instructor_client.user)
        video = VideoFactory()
        payload = {
            "title": "New Lesson",
            "course": course.pk,
            "video": video.pk,
            "order": 1,
            "duration": 15,
        }
        response = instructor_client.post(self.URL, payload)
        assert response.status_code == status.HTTP_201_CREATED

    def test_create_lesson_as_student_returns_403(self, auth_client):
        """Regular user cannot create a lesson."""
        course = CourseFactory(is_published=True)
        video = VideoFactory()
        payload = {
            "title": "Unauthorized Lesson",
            "course": course.pk,
            "video": video.pk,
            "order": 1,
        }
        response = auth_client.post(self.URL, payload)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_retrieve_first_lesson_is_free_preview(self, api_client):
        """First lesson (order=1) can be accessed without enrollment."""
        course = CourseFactory(is_published=True)
        lesson = LessonFactory(course=course, order=1, is_free_preview=True)
        response = api_client.get(f"{self.URL}{lesson.pk}/")
        assert response.status_code == status.HTTP_200_OK

    def test_filter_lessons_by_course(self, api_client):
        """Lessons can be filtered by course ID."""
        course1 = CourseFactory(is_published=True)
        course2 = CourseFactory(is_published=True)
        LessonFactory(course=course1, order=1)
        LessonFactory(course=course1, order=2)
        LessonFactory(course=course2, order=1)
        response = api_client.get(self.URL, {"course": course1.pk})
        assert response.data["count"] == 2
