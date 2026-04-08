"""Tests for enrollments permissions."""

import pytest
from rest_framework import status

from apps.courses.factories import CourseFactory
from apps.enrollments.factories import EnrollmentFactory, LessonProgressFactory
from apps.users.factories import InstructorFactory, UserFactory
from apps.videos.factories import LessonFactory


@pytest.mark.django_db
class TestIsEnrollmentOwner:
    """Tests for IsEnrollmentOwner permission via EnrollmentViewSet."""

    URL = "/api/enrollments/"

    def test_owner_can_retrieve_own_enrollment(self, auth_client):
        """Enrollment owner can access their own enrollment."""
        enrollment = EnrollmentFactory(user=auth_client.user)
        response = auth_client.get(f"{self.URL}{enrollment.pk}/")
        assert response.status_code == status.HTTP_200_OK

    def test_non_owner_student_cannot_retrieve(self, auth_client):
        """Another student cannot access someone else's enrollment (queryset filtered → 404)."""
        other_enrollment = EnrollmentFactory()
        response = auth_client.get(f"{self.URL}{other_enrollment.pk}/")
        # Queryset restricts to own enrollments; other's enrollment isn't found → 404
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_staff_can_retrieve_any_enrollment(self, staff_client):
        """Staff has full access to any enrollment."""
        enrollment = EnrollmentFactory()
        response = staff_client.get(f"{self.URL}{enrollment.pk}/")
        assert response.status_code == status.HTTP_200_OK

    def test_staff_can_delete_any_enrollment(self, staff_client):
        """Staff can delete any enrollment."""
        enrollment = EnrollmentFactory()
        response = staff_client.delete(f"{self.URL}{enrollment.pk}/")
        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_instructor_can_read_own_course_enrollment(
        self, instructor_client
    ):
        """Instructor can view enrollments for their course (read-only)."""
        course = CourseFactory(instructor=instructor_client.user)
        enrollment = EnrollmentFactory(course=course)
        response = instructor_client.get(f"{self.URL}{enrollment.pk}/")
        assert response.status_code == status.HTTP_200_OK

    def test_instructor_cannot_delete_course_enrollment(
        self, instructor_client
    ):
        """Instructor cannot delete a student's enrollment from their course."""
        course = CourseFactory(instructor=instructor_client.user)
        enrollment = EnrollmentFactory(course=course)
        response = instructor_client.delete(f"{self.URL}{enrollment.pk}/")
        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestIsEnrolledOrInstructor:
    """Tests for IsEnrolledOrInstructor permission via LessonProgressViewSet."""

    URL = "/api/progress/"

    def test_enrolled_student_can_access_own_progress(self, auth_client):
        """Student can access their own lesson progress."""
        enrollment = EnrollmentFactory(user=auth_client.user)
        lesson = LessonFactory(course=enrollment.course)
        progress = LessonProgressFactory(
            enrollment=enrollment, lesson=lesson
        )
        response = auth_client.get(f"{self.URL}{progress.pk}/")
        assert response.status_code == status.HTTP_200_OK

    def test_student_cannot_access_other_progress(self, auth_client):
        """Student cannot access another student's progress (queryset filtered → 404)."""
        other_progress = LessonProgressFactory()
        response = auth_client.get(f"{self.URL}{other_progress.pk}/")
        # Queryset restricts to own progress; other's record isn't found → 404
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_staff_can_access_any_progress(self, staff_client):
        """Staff can access any lesson progress record."""
        progress = LessonProgressFactory()
        response = staff_client.get(f"{self.URL}{progress.pk}/")
        assert response.status_code == status.HTTP_200_OK

    def test_instructor_can_read_course_progress(self, instructor_client):
        """Instructor can read progress from students in their courses."""
        course = CourseFactory(instructor=instructor_client.user)
        enrollment = EnrollmentFactory(course=course)
        lesson = LessonFactory(course=course, order=1)
        progress = LessonProgressFactory(
            enrollment=enrollment, lesson=lesson
        )
        response = instructor_client.get(f"{self.URL}{progress.pk}/")
        assert response.status_code == status.HTTP_200_OK
