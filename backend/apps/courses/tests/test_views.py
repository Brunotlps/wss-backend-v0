"""Tests for Courses API views."""

import pytest
from rest_framework import status

from apps.courses.factories import CategoryFactory, CourseFactory
from apps.courses.models import Course
from apps.users.factories import InstructorFactory, UserFactory


@pytest.mark.django_db
class TestCategoryViewSet:
    """Tests for GET /api/categories/."""

    URL = "/api/categories/"

    def test_list_active_categories(self, api_client):
        """Lists only active categories."""
        CategoryFactory.create_batch(3, is_active=True)
        CategoryFactory(is_active=False)
        response = api_client.get(self.URL)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 3

    def test_retrieve_category(self, api_client):
        """Single category can be retrieved."""
        cat = CategoryFactory(name="Backend")
        response = api_client.get(f"{self.URL}{cat.pk}/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["name"] == "Backend"

    def test_categories_are_public(self, api_client):
        """No authentication required for categories."""
        CategoryFactory()
        response = api_client.get(self.URL)
        assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestCourseViewSet:
    """Tests for /api/courses/ CRUD and visibility."""

    URL = "/api/courses/"

    def test_list_returns_only_published_for_anonymous(self, api_client):
        """Anonymous users see only published courses."""
        CourseFactory(is_published=True)
        CourseFactory(is_published=False)
        response = api_client.get(self.URL)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1

    def test_list_returns_only_published_for_student(self, auth_client):
        """Regular students see only published courses."""
        CourseFactory(is_published=True)
        CourseFactory(is_published=False)
        response = auth_client.get(self.URL)
        assert response.data["count"] == 1

    def test_instructor_sees_own_unpublished_courses(self, instructor_client):
        """Instructor sees their own unpublished courses too."""
        CourseFactory(instructor=instructor_client.user, is_published=False)
        CourseFactory(is_published=True)
        response = instructor_client.get(self.URL)
        assert response.data["count"] == 2

    def test_staff_sees_all_courses(self, staff_client):
        """Staff sees all courses regardless of publish status."""
        CourseFactory(is_published=True)
        CourseFactory(is_published=False)
        response = staff_client.get(self.URL)
        assert response.data["count"] == 2

    def test_create_course_as_instructor_returns_201(self, instructor_client):
        """Instructor can create a course."""
        payload = {
            "title": "New Course",
            "description": "Learn stuff",
            "price": "79.00",
            "instructor": instructor_client.user.pk,
        }
        response = instructor_client.post(self.URL, payload)
        assert response.status_code == status.HTTP_201_CREATED
        assert Course.objects.filter(title="New Course").exists()

    def test_retrieve_published_course(self, api_client):
        """Published course can be retrieved by anyone."""
        course = CourseFactory(is_published=True)
        response = api_client.get(f"{self.URL}{course.pk}/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["title"] == course.title

    def test_search_courses_by_title(self, api_client):
        """Search param filters by title."""
        CourseFactory(title="Django REST Framework", is_published=True)
        CourseFactory(title="React Basics", is_published=True)
        response = api_client.get(self.URL, {"search": "Django"})
        assert response.data["count"] == 1
        assert "Django" in response.data["results"][0]["title"]

    def test_filter_free_courses(self, api_client):
        """Filtering by price_max=0 returns only free courses."""
        CourseFactory(price=0, is_published=True)
        CourseFactory(price=99, is_published=True)
        response = api_client.get(self.URL, {"price_max": "0"})
        assert response.data["count"] == 1

    def test_lessons_action_returns_course_lessons(self, api_client):
        """GET /api/courses/{id}/lessons/ returns lesson list."""
        course = CourseFactory(is_published=True)
        response = api_client.get(f"{self.URL}{course.pk}/lessons/")
        assert response.status_code == status.HTTP_200_OK
        assert isinstance(response.data, list)
