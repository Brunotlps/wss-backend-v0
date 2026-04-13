"""Tests for Enrollment and LessonProgress API views."""

import pytest
from django.core.cache import cache
from rest_framework import status

from apps.courses.factories import CourseFactory
from apps.enrollments.factories import EnrollmentFactory, LessonProgressFactory
from apps.enrollments.models import Enrollment
from apps.payments.factories import PaymentFactory
from apps.payments.models import Payment
from apps.users.factories import InstructorFactory, UserFactory
from apps.videos.factories import LessonFactory


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.mark.django_db
class TestEnrollmentViewSet:
    """Tests for /api/enrollments/ CRUD with role-based access."""

    URL = "/api/enrollments/"

    def test_list_requires_authentication(self, api_client):
        """Unauthenticated requests are rejected."""
        response = api_client.get(self.URL)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_student_sees_only_own_enrollments(self, auth_client):
        """Students see only their own enrollments."""
        EnrollmentFactory(user=auth_client.user)
        EnrollmentFactory()  # Another user's enrollment
        response = auth_client.get(self.URL)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1

    def test_instructor_sees_own_and_course_enrollments(
        self, instructor_client
    ):
        """Instructors see their own enrollments and enrollments in their courses."""
        course = CourseFactory(instructor=instructor_client.user)
        student_enrollment = EnrollmentFactory(course=course)
        own_enrollment = EnrollmentFactory(user=instructor_client.user)
        other_enrollment = EnrollmentFactory()  # Unrelated
        response = instructor_client.get(self.URL)
        assert response.data["count"] == 2  # student's + own

    def test_staff_sees_all_enrollments(self, staff_client):
        """Staff can see all enrollments."""
        EnrollmentFactory.create_batch(3)
        response = staff_client.get(self.URL)
        assert response.data["count"] == 3

    def test_create_enrollment_sets_user_to_current(self, auth_client):
        """Creating enrollment auto-assigns authenticated user."""
        course = CourseFactory(free=True)
        response = auth_client.post(self.URL, {"course_id": course.pk})
        assert response.status_code == status.HTTP_201_CREATED
        enrollment = Enrollment.objects.get(pk=response.data["id"])
        assert enrollment.user == auth_client.user

    def test_create_enrollment_free_course_returns_201(self, auth_client):
        """Free course can be enrolled without any payment."""
        course = CourseFactory(free=True)
        response = auth_client.post(self.URL, {"course_id": course.pk})
        assert response.status_code == status.HTTP_201_CREATED

    def test_create_enrollment_paid_course_without_payment_returns_402(self, auth_client):
        """Paid course requires a successful payment before enrollment."""
        course = CourseFactory()
        response = auth_client.post(self.URL, {"course_id": course.pk})
        assert response.status_code == status.HTTP_402_PAYMENT_REQUIRED

    def test_create_enrollment_paid_course_with_succeeded_payment_returns_201(
        self, auth_client
    ):
        """Paid course can be enrolled after a successful payment."""
        course = CourseFactory()
        PaymentFactory(
            user=auth_client.user,
            course=course,
            status=Payment.Status.SUCCEEDED,
        )
        response = auth_client.post(self.URL, {"course_id": course.pk})
        assert response.status_code == status.HTTP_201_CREATED

    def test_create_enrollment_paid_course_with_pending_payment_returns_402(
        self, auth_client
    ):
        """Pending payment does not grant enrollment access."""
        course = CourseFactory()
        PaymentFactory(
            user=auth_client.user,
            course=course,
            status=Payment.Status.PENDING,
        )
        response = auth_client.post(self.URL, {"course_id": course.pk})
        assert response.status_code == status.HTTP_402_PAYMENT_REQUIRED

    def test_retrieve_own_enrollment(self, auth_client):
        """Student can retrieve their own enrollment."""
        enrollment = EnrollmentFactory(user=auth_client.user)
        response = auth_client.get(f"{self.URL}{enrollment.pk}/")
        assert response.status_code == status.HTTP_200_OK

    def test_cannot_retrieve_other_user_enrollment(self, auth_client):
        """Student cannot see another student's enrollment (filtered out as 404)."""
        other_enrollment = EnrollmentFactory()
        response = auth_client.get(f"{self.URL}{other_enrollment.pk}/")
        # DRF returns 404 because the queryset is filtered to own enrollments only
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_instructor_can_read_course_enrollment(self, instructor_client):
        """Instructor can read enrollments in their course."""
        course = CourseFactory(instructor=instructor_client.user)
        enrollment = EnrollmentFactory(course=course)
        response = instructor_client.get(f"{self.URL}{enrollment.pk}/")
        assert response.status_code == status.HTTP_200_OK

    def test_cannot_enroll_twice_in_same_course(self, auth_client):
        """Cannot create duplicate enrollment for the same course."""
        course = CourseFactory()
        EnrollmentFactory(user=auth_client.user, course=course)
        response = auth_client.post(self.URL, {"course": course.pk})
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_search_enrollments_by_course_title(self, auth_client):
        """Enrollments can be searched by course title."""
        course1 = CourseFactory(title="Django Deep Dive")
        course2 = CourseFactory(title="React Basics")
        EnrollmentFactory(user=auth_client.user, course=course1)
        EnrollmentFactory(user=auth_client.user, course=course2)
        response = auth_client.get(self.URL, {"search": "Django"})
        assert response.data["count"] == 1


@pytest.mark.django_db
class TestLessonProgressViewSet:
    """Tests for /api/progress/ CRUD with role-based access."""

    URL = "/api/progress/"

    def test_list_requires_authentication(self, api_client):
        """Unauthenticated requests are rejected."""
        response = api_client.get(self.URL)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_student_sees_only_own_progress(self, auth_client):
        """Students see only their own lesson progress."""
        enrollment = EnrollmentFactory(user=auth_client.user)
        lesson = LessonFactory(course=enrollment.course)
        LessonProgressFactory(enrollment=enrollment, lesson=lesson)
        other_progress = LessonProgressFactory()  # Another student
        response = auth_client.get(self.URL)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1

    def test_instructor_sees_own_and_course_progress(self, instructor_client):
        """Instructors see their students' progress in their courses."""
        course = CourseFactory(instructor=instructor_client.user)
        enrollment = EnrollmentFactory(course=course)
        lesson = LessonFactory(course=course, order=1)
        student_progress = LessonProgressFactory(
            enrollment=enrollment, lesson=lesson
        )
        other_progress = LessonProgressFactory()  # Unrelated
        response = instructor_client.get(self.URL)
        assert response.data["count"] == 1

    def test_staff_sees_all_lesson_progress(self, staff_client):
        """Staff can see all lesson progress records."""
        LessonProgressFactory.create_batch(4)
        response = staff_client.get(self.URL)
        assert response.data["count"] == 4

    def test_retrieve_own_lesson_progress(self, auth_client):
        """Student can retrieve their own lesson progress."""
        enrollment = EnrollmentFactory(user=auth_client.user)
        lesson = LessonFactory(course=enrollment.course)
        progress = LessonProgressFactory(enrollment=enrollment, lesson=lesson)
        response = auth_client.get(f"{self.URL}{progress.pk}/")
        assert response.status_code == status.HTTP_200_OK

    def test_cannot_retrieve_other_student_progress(self, auth_client):
        """Student cannot access another student's progress (queryset filtered → 404)."""
        other_progress = LessonProgressFactory()
        response = auth_client.get(f"{self.URL}{other_progress.pk}/")
        assert response.status_code == status.HTTP_404_NOT_FOUND
