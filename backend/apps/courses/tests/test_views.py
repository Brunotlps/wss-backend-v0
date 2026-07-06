"""Tests for Courses API views."""

from django.db import connection
from django.test.utils import CaptureQueriesContext

from rest_framework import status

import pytest

from apps.courses.factories import CategoryFactory, CourseFactory, ModuleFactory
from apps.courses.models import Course, Module
from apps.enrollments.factories import EnrollmentFactory
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

    def test_list_course_counts_have_no_n_plus_one(self, api_client):
        """List must not issue a per-course COUNT for enrolled_count (#64).

        Query count for one course must equal the count for several courses;
        if it grows with the number of rows, enrolled_count is an N+1.
        """

        def make_course():
            course = CourseFactory(is_published=True)
            EnrollmentFactory(course=course, is_active=True)

        make_course()
        with CaptureQueriesContext(connection) as ctx:
            response = api_client.get(self.URL)
        assert response.status_code == status.HTTP_200_OK
        baseline = len(ctx.captured_queries)

        for _ in range(4):
            make_course()
        with CaptureQueriesContext(connection) as ctx:
            response = api_client.get(self.URL)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 5
        assert len(ctx.captured_queries) == baseline, (
            f"N+1 detected: {baseline} queries for 1 course, "
            f"{len(ctx.captured_queries)} for 5"
        )

    def test_retrieve_counts_use_annotations_no_extra_count_queries(self, api_client):
        """Detail endpoint reads annotated counts, no per-relation COUNT (#64)."""
        course = CourseFactory(is_published=True)
        EnrollmentFactory.create_batch(2, course=course, is_active=True)
        EnrollmentFactory(course=course, is_active=False)
        LessonFactory(course=course, order=1)
        LessonFactory(course=course, order=2)
        LessonFactory(course=course, order=3)

        with CaptureQueriesContext(connection) as ctx:
            response = api_client.get(f"{self.URL}{course.pk}/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["enrolled_count"] == 2
        assert response.data["lessons_count"] == 3
        count_queries = [
            q["sql"]
            for q in ctx.captured_queries
            if "COUNT(*)" in q["sql"]
            and ("enrollments_enrollment" in q["sql"] or "videos_lesson" in q["sql"])
        ]
        assert (
            count_queries == []
        ), f"counts should come from annotations, got: {count_queries}"

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

    def test_filter_is_free_true_returns_only_free(self, api_client):
        """?is_free=true returns only courses priced at 0 (#72)."""
        free = CourseFactory(price=0, is_published=True)
        CourseFactory(price=99, is_published=True)
        response = api_client.get(self.URL, {"is_free": "true"})
        assert response.data["count"] == 1
        assert response.data["results"][0]["id"] == free.id

    def test_filter_is_free_false_returns_only_paid(self, api_client):
        """?is_free=false returns only courses priced above 0 (#72)."""
        CourseFactory(price=0, is_published=True)
        paid = CourseFactory(price=99, is_published=True)
        response = api_client.get(self.URL, {"is_free": "false"})
        assert response.data["count"] == 1
        assert response.data["results"][0]["id"] == paid.id

    def test_filter_is_free_empty_returns_all(self, api_client):
        """An empty ?is_free= is a no-op and returns every course (#72)."""
        CourseFactory(price=0, is_published=True)
        CourseFactory(price=99, is_published=True)
        response = api_client.get(self.URL, {"is_free": ""})
        assert response.data["count"] == 2

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
class TestCoursePriceGuard:
    """Soft-freeze on PATCH + audited adjust-price action (#69)."""

    URL = "/api/courses/"

    def test_patch_price_blocked_when_course_has_active_enrollments(
        self, instructor_client
    ):
        """PATCH price is rejected (400) when the course has active enrollments."""
        course = CourseFactory(instructor=instructor_client.user, price="100.00")
        EnrollmentFactory(course=course, is_active=True)
        response = instructor_client.patch(
            f"{self.URL}{course.pk}/", {"price": "150.00"}
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "price" in response.data
        course.refresh_from_db()
        assert str(course.price) == "100.00"

    def test_patch_price_allowed_when_no_enrollments(self, instructor_client):
        """PATCH price succeeds when the course has no active enrollments."""
        course = CourseFactory(instructor=instructor_client.user, price="100.00")
        response = instructor_client.patch(
            f"{self.URL}{course.pk}/", {"price": "150.00"}
        )
        assert response.status_code == status.HTTP_200_OK
        course.refresh_from_db()
        assert str(course.price) == "150.00"

    def test_adjust_price_owner_no_enrollments_succeeds(self, instructor_client):
        """Owner can adjust price without confirm when no active enrollments."""
        course = CourseFactory(instructor=instructor_client.user, price="100.00")
        response = instructor_client.post(
            f"{self.URL}{course.pk}/adjust-price/", {"new_price": "120.00"}
        )
        assert response.status_code == status.HTTP_200_OK
        assert str(response.data["price"]) == "120.00"
        course.refresh_from_db()
        assert str(course.price) == "120.00"

    def test_adjust_price_with_enrollments_requires_confirm(self, instructor_client):
        """Adjusting price on an enrolled course without confirm is rejected (400)."""
        course = CourseFactory(instructor=instructor_client.user, price="100.00")
        EnrollmentFactory(course=course, is_active=True)
        response = instructor_client.post(
            f"{self.URL}{course.pk}/adjust-price/", {"new_price": "120.00"}
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        course.refresh_from_db()
        assert str(course.price) == "100.00"

    def test_adjust_price_with_enrollments_and_confirm_succeeds(
        self, instructor_client
    ):
        """Adjusting price on an enrolled course succeeds with confirm=true."""
        course = CourseFactory(instructor=instructor_client.user, price="100.00")
        EnrollmentFactory(course=course, is_active=True)
        response = instructor_client.post(
            f"{self.URL}{course.pk}/adjust-price/",
            {"new_price": "120.00", "confirm": True},
        )
        assert response.status_code == status.HTTP_200_OK
        course.refresh_from_db()
        assert str(course.price) == "120.00"

    def test_adjust_price_non_owner_denied(self, instructor_client):
        """A non-owner instructor cannot adjust another course's price (403)."""
        course = CourseFactory(price="100.00")  # owned by a different instructor
        response = instructor_client.post(
            f"{self.URL}{course.pk}/adjust-price/", {"new_price": "10.00"}
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN
        course.refresh_from_db()
        assert str(course.price) == "100.00"

    def test_adjust_price_negative_rejected(self, instructor_client):
        """A negative new_price is rejected (400)."""
        course = CourseFactory(instructor=instructor_client.user, price="100.00")
        response = instructor_client.post(
            f"{self.URL}{course.pk}/adjust-price/", {"new_price": "-10.00"}
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        course.refresh_from_db()
        assert str(course.price) == "100.00"


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

    def test_create_module_as_non_owner_returns_403(self, instructor_client):
        """Instructor that does not own the course is rejected with 403 (#122).

        Authorization failures return 403 (api-conventions.md), consistent
        with the update path (test_update_module_as_non_owner_returns_403) —
        not 400, which was the serializer wrongly performing authz.
        """
        course = CourseFactory()  # different instructor
        payload = {
            "course": course.pk,
            "title": "Not Mine",
            "order": 1,
        }
        response = instructor_client.post(self.URL, payload)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_create_module_missing_course_returns_400(self, instructor_client):
        """Missing course is a validation error (400), not an authz failure."""
        payload = {"title": "No Course", "order": 1}
        response = instructor_client.post(self.URL, payload)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_module_nonexistent_course_returns_400(self, instructor_client):
        """A non-existent course id is a validation error (400), not 403."""
        payload = {"course": 999999, "title": "Ghost Course", "order": 1}
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
