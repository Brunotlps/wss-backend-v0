"""Tests for courses permissions."""

import pytest
from rest_framework import status

from apps.courses.factories import CourseFactory
from apps.users.factories import InstructorFactory, UserFactory


@pytest.mark.django_db
class TestIsInstructorOrReadOnly:
    """Test IsInstructorOrReadOnly permission via CourseViewSet."""

    URL = "/api/courses/"

    def test_student_cannot_create_course(self, auth_client):
        """Regular user (not instructor) gets 403 on POST."""
        instructor = InstructorFactory()
        payload = {
            "title": "New Course",
            "description": "desc",
            "price": "50.00",
            "instructor": instructor.pk,
        }
        response = auth_client.post(self.URL, payload)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_unauthenticated_cannot_create_course(self, api_client):
        """Unauthenticated user gets 401 on POST."""
        response = api_client.post(self.URL, {"title": "x"})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_instructor_can_create_course(self, instructor_client):
        """Instructor can create a course."""
        payload = {
            "title": "My Course",
            "description": "A great course",
            "price": "99.00",
            "instructor": instructor_client.user.pk,
        }
        response = instructor_client.post(self.URL, payload)
        assert response.status_code == status.HTTP_201_CREATED


@pytest.mark.django_db
class TestIsCourseOwnerOrReadOnly:
    """Test IsCourseOwnerOrReadOnly permission."""

    def test_owner_can_update_course(self, instructor_client):
        """Course instructor can update their own course."""
        course = CourseFactory(instructor=instructor_client.user)
        url = f"/api/courses/{course.pk}/"
        response = instructor_client.patch(url, {"title": "Updated Title"})
        assert response.status_code == status.HTTP_200_OK
        assert response.data["title"] == "Updated Title"

    def test_non_owner_cannot_update_course(self, instructor_client):
        """Another instructor cannot update someone else's course."""
        other_instructor = InstructorFactory()
        course = CourseFactory(instructor=other_instructor)
        url = f"/api/courses/{course.pk}/"
        response = instructor_client.patch(url, {"title": "Hacked"})
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_owner_can_delete_course(self, instructor_client):
        """Course instructor can delete their own course."""
        course = CourseFactory(instructor=instructor_client.user)
        url = f"/api/courses/{course.pk}/"
        response = instructor_client.delete(url)
        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_non_owner_cannot_delete_course(self, auth_client):
        """Regular user cannot delete a course."""
        course = CourseFactory()
        url = f"/api/courses/{course.pk}/"
        response = auth_client.delete(url)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_anyone_can_read_published_course(self, api_client):
        """Any user (including anonymous) can read published courses."""
        course = CourseFactory(is_published=True)
        response = api_client.get(f"/api/courses/{course.pk}/")
        assert response.status_code == status.HTTP_200_OK
