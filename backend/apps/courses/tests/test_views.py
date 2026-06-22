"""Tests for Courses API views."""

from rest_framework import status

import pytest

from apps.courses.factories import CategoryFactory, CourseFactory, ModuleFactory
from apps.courses.models import Course, Module
from apps.videos.factories import LessonFactory


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

    def test_create_course_with_colliding_slug_returns_201(self, instructor_client):
        """Colliding auto-slugs are disambiguated instead of raising a 500."""
        CourseFactory(instructor=instructor_client.user, title="Programação", slug="")
        payload = {
            "title": "Programacao",
            "description": "Learn stuff",
            "price": "79.00",
        }
        response = instructor_client.post(self.URL, payload)
        assert response.status_code == status.HTTP_201_CREATED
        slugs = set(Course.objects.values_list("slug", flat=True))
        assert slugs == {"programacao", "programacao-2"}

    def test_create_course_with_negative_price_returns_400(self, instructor_client):
        """A negative price is rejected with 400."""
        payload = {
            "title": "Cheap Course",
            "description": "Learn stuff",
            "price": "-10.00",
        }
        response = instructor_client.post(self.URL, payload)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_publish_course_without_lessons_returns_400(self, instructor_client):
        """Publishing an empty course is blocked with 400."""
        course = CourseFactory(instructor=instructor_client.user, is_published=False)
        response = instructor_client.patch(
            f"{self.URL}{course.pk}/", {"is_published": True}
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_publish_course_with_lessons_succeeds(self, instructor_client):
        """Publishing a course that has lessons succeeds."""
        course = CourseFactory(instructor=instructor_client.user, is_published=False)
        LessonFactory(course=course, order=1)
        response = instructor_client.patch(
            f"{self.URL}{course.pk}/", {"is_published": True}
        )
        assert response.status_code == status.HTTP_200_OK
        course.refresh_from_db()
        assert course.is_published is True

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

    def test_modules_action_returns_modules_with_lessons(self, api_client):
        """GET /api/courses/{id}/modules/ returns modules with nested lessons."""
        course = CourseFactory(is_published=True)
        module = ModuleFactory(course=course, order=1, title="Intro")
        LessonFactory(course=course, module=module, order=1, title="First")
        response = api_client.get(f"{self.URL}{course.pk}/modules/")
        assert response.status_code == status.HTTP_200_OK
        assert isinstance(response.data, list)
        assert response.data[0]["title"] == "Intro"
        assert len(response.data[0]["lessons"]) == 1
        assert response.data[0]["lessons"][0]["title"] == "First"

    def test_modules_action_empty_when_course_has_no_modules(self, api_client):
        """Empty list is returned when course has no modules."""
        course = CourseFactory(is_published=True)
        response = api_client.get(f"{self.URL}{course.pk}/modules/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data == []


@pytest.mark.django_db
class TestModuleViewSet:
    """Tests for /api/modules/ CRUD and permissions."""

    URL = "/api/modules/"

    def test_list_modules_is_public(self, api_client):
        """Anyone can list modules."""
        ModuleFactory.create_batch(3)
        response = api_client.get(self.URL)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 3

    def test_filter_modules_by_course(self, api_client):
        """Modules can be filtered by course id."""
        course = CourseFactory()
        ModuleFactory(course=course, order=1)
        ModuleFactory(course=course, order=2)
        ModuleFactory()  # unrelated module
        response = api_client.get(self.URL, {"course": course.pk})
        assert response.data["count"] == 2

    def test_create_module_as_course_instructor(self, instructor_client):
        """Course instructor can create a module."""
        course = CourseFactory(instructor=instructor_client.user)
        payload = {
            "course": course.pk,
            "title": "New Module",
            "order": 1,
        }
        response = instructor_client.post(self.URL, payload)
        assert response.status_code == status.HTTP_201_CREATED
        assert Module.objects.filter(title="New Module").exists()

    def test_create_module_as_non_owner_returns_400(self, instructor_client):
        """Instructor that does not own the course is rejected."""
        course = CourseFactory()  # different instructor
        payload = {
            "course": course.pk,
            "title": "Not Mine",
            "order": 1,
        }
        response = instructor_client.post(self.URL, payload)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_module_as_student_returns_403(self, auth_client):
        """Regular user cannot create a module."""
        course = CourseFactory()
        payload = {"course": course.pk, "title": "x", "order": 1}
        response = auth_client.post(self.URL, payload)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_create_module_unauthenticated_returns_401(self, api_client):
        """Anonymous user cannot create a module."""
        course = CourseFactory()
        payload = {"course": course.pk, "title": "x", "order": 1}
        response = api_client.post(self.URL, payload)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_update_module_as_owner(self, instructor_client):
        """Course instructor can rename their module."""
        course = CourseFactory(instructor=instructor_client.user)
        module = ModuleFactory(course=course, order=1, title="Old")
        response = instructor_client.patch(f"{self.URL}{module.pk}/", {"title": "New"})
        assert response.status_code == status.HTTP_200_OK
        module.refresh_from_db()
        assert module.title == "New"

    def test_update_module_as_non_owner_returns_403(self, instructor_client):
        """Non-owner instructor receives 403 on update."""
        module = ModuleFactory()  # owned by another instructor
        response = instructor_client.patch(f"{self.URL}{module.pk}/", {"title": "Hack"})
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_delete_module_as_owner(self, instructor_client):
        """Course instructor can delete their module."""
        course = CourseFactory(instructor=instructor_client.user)
        module = ModuleFactory(course=course, order=1)
        response = instructor_client.delete(f"{self.URL}{module.pk}/")
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Module.objects.filter(pk=module.pk).exists()
