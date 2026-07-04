"""Tests for Enrollment and LessonProgress API views."""

from unittest.mock import patch

from django.core.cache import cache
from django.db import IntegrityError

from rest_framework import status

import pytest

from apps.courses.factories import CourseFactory
from apps.enrollments.factories import EnrollmentFactory, LessonProgressFactory
from apps.enrollments.models import Enrollment, LessonProgress
from apps.enrollments.views import EnrollmentViewSet
from apps.payments.factories import PaymentFactory
from apps.payments.models import Payment
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

    def test_instructor_sees_own_and_course_enrollments(self, instructor_client):
        """Instructors see their own enrollments and enrollments in their courses."""
        course = CourseFactory(instructor=instructor_client.user)
        EnrollmentFactory(course=course)
        EnrollmentFactory(user=instructor_client.user)
        EnrollmentFactory()  # Unrelated
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

    def test_create_enrollment_paid_course_without_payment_returns_402(
        self, auth_client
    ):
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
        """Duplicate enrollment POST returns 409 Conflict, not 500/400 (#28).

        Uses the real write field ``course_id``; a second POST must be
        rejected as a business-rule conflict, not raise an IntegrityError.
        """
        course = CourseFactory(free=True)
        EnrollmentFactory(user=auth_client.user, course=course)
        response = auth_client.post(self.URL, {"course_id": course.pk})
        assert response.status_code == status.HTTP_409_CONFLICT

    def test_duplicate_enrollment_race_returns_409(self, auth_client):
        """TOCTOU: a create slipping past the pre-check hits the unique
        constraint; the IntegrityError is mapped to 409, not 500 (#28)."""
        course = CourseFactory(free=True)
        with patch.object(
            EnrollmentViewSet,
            "perform_create",
            side_effect=IntegrityError("UNIQUE constraint failed"),
        ):
            response = auth_client.post(self.URL, {"course_id": course.pk})
        assert response.status_code == status.HTTP_409_CONFLICT

    def test_create_ignores_system_managed_fields(self, auth_client):
        """System-managed fields cannot be set on enrollment creation (#30).

        Mass-assignment: a POST must not let the client mark an enrollment
        as completed/rated/reviewed/inactive — those bypass the update
        serializer's business rules and open a fraudulent-certificate path.
        """
        course = CourseFactory(free=True)
        response = auth_client.post(
            self.URL,
            {
                "course_id": course.pk,
                "completed": True,
                "rating": 5,
                "review": "fake",
                "is_active": False,
            },
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        enrollment = Enrollment.objects.get(pk=response.data["id"])
        assert enrollment.completed is False
        assert enrollment.rating is None
        assert enrollment.review == ""
        assert enrollment.is_active is True

    def test_search_enrollments_by_course_title(self, auth_client):
        """Enrollments can be searched by course title."""
        course1 = CourseFactory(title="Django Deep Dive")
        course2 = CourseFactory(title="React Basics")
        EnrollmentFactory(user=auth_client.user, course=course1)
        EnrollmentFactory(user=auth_client.user, course=course2)
        response = auth_client.get(self.URL, {"search": "Django"})
        assert response.data["count"] == 1

    def test_rating_on_completed_enrollment_returns_200(self, auth_client):
        """Rating a completed enrollment is allowed."""
        enrollment = EnrollmentFactory(user=auth_client.user, completed=True)
        response = auth_client.patch(
            f"{self.URL}{enrollment.pk}/", {"rating": 5}, format="json"
        )
        assert response.status_code == status.HTTP_200_OK
        enrollment.refresh_from_db()
        assert enrollment.rating == 5

    def test_rating_on_incomplete_enrollment_returns_400(self, auth_client):
        """Rating an incomplete enrollment is rejected with 400."""
        enrollment = EnrollmentFactory(user=auth_client.user, completed=False)
        response = auth_client.patch(
            f"{self.URL}{enrollment.pk}/", {"rating": 4}, format="json"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_rating_none_on_incomplete_enrollment_is_allowed(self, auth_client):
        """Clearing a rating (None) is always allowed, even on incomplete enrollment."""
        enrollment = EnrollmentFactory(user=auth_client.user, completed=False, rating=3)
        response = auth_client.patch(
            f"{self.URL}{enrollment.pk}/", {"rating": None}, format="json"
        )
        assert response.status_code == status.HTTP_200_OK

    def test_enrollment_detail_exposes_next_incomplete_lesson(self, auth_client):
        """The detail view surfaces the first incomplete lesson as next_lesson."""
        enrollment = EnrollmentFactory(user=auth_client.user)
        lesson = LessonFactory(course=enrollment.course, order=1)
        response = auth_client.get(f"{self.URL}{enrollment.pk}/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["next_lesson"] is not None
        assert response.data["next_lesson"]["id"] == lesson.id

    def test_rating_out_of_range_returns_400(self, auth_client):
        """A rating above 5 is rejected regardless of completion (field range)."""
        enrollment = EnrollmentFactory(user=auth_client.user, completed=True)
        response = auth_client.patch(
            f"{self.URL}{enrollment.pk}/", {"rating": 6}, format="json"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_review_without_completed_lesson_returns_400(self, auth_client):
        """A review requires at least one completed lesson (business rule)."""
        enrollment = EnrollmentFactory(user=auth_client.user)
        response = auth_client.patch(
            f"{self.URL}{enrollment.pk}/",
            {"review": "Great course!"},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "review" in response.data

    @patch("apps.certificates.tasks.generate_certificate_pdf_async.delay")
    def test_review_with_completed_lesson_returns_200(self, mock_delay, auth_client):
        """A review is accepted once the student has completed a lesson."""
        enrollment = EnrollmentFactory(user=auth_client.user)
        lesson = LessonFactory(course=enrollment.course)
        LessonProgressFactory(enrollment=enrollment, lesson=lesson, completed=True)
        response = auth_client.patch(
            f"{self.URL}{enrollment.pk}/",
            {"review": "Great course!"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        enrollment.refresh_from_db()
        assert enrollment.review == "Great course!"


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
        LessonProgressFactory()  # Another student
        response = auth_client.get(self.URL)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1

    def test_instructor_sees_own_and_course_progress(self, instructor_client):
        """Instructors see their students' progress in their courses."""
        course = CourseFactory(instructor=instructor_client.user)
        enrollment = EnrollmentFactory(course=course)
        lesson = LessonFactory(course=course, order=1)
        LessonProgressFactory(enrollment=enrollment, lesson=lesson)
        LessonProgressFactory()  # Unrelated
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

    def test_create_completed_progress_sets_timestamp_and_duration(self, auth_client):
        """POST completed=True sets completed_at and watched_duration on create (#31)."""
        enrollment = EnrollmentFactory(user=auth_client.user)
        lesson = LessonFactory(course=enrollment.course)
        response = auth_client.post(
            self.URL,
            {
                "enrollment_id": enrollment.pk,
                "lesson_id": lesson.pk,
                "completed": True,
            },
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        progress = LessonProgress.objects.get(pk=response.data["id"])
        assert progress.completed is True
        assert progress.completed_at is not None
        assert progress.watched_duration == lesson.duration

    def test_progress_on_foreign_course_lesson_returns_400(self, auth_client):
        """Progress for a lesson outside the enrollment's course is rejected (#29).

        Otherwise a student could complete a course (and trigger a
        certificate) using progress on lessons they never had to watch.
        """
        enrollment = EnrollmentFactory(user=auth_client.user)
        LessonFactory(course=enrollment.course)  # real lesson in the course
        foreign_lesson = LessonFactory()  # belongs to a different course
        assert foreign_lesson.course_id != enrollment.course_id
        response = auth_client.post(
            self.URL,
            {
                "enrollment_id": enrollment.pk,
                "lesson_id": foreign_lesson.pk,
                "completed": True,
            },
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_progress_on_inactive_enrollment_returns_400(self, auth_client):
        """Progress cannot be recorded on a deactivated (e.g. refunded) enrollment (#32).

        is_active=False blocks video access already (IsEnrolled); it must also
        block new progress writes, or a refunded student could keep completing
        lessons and still trigger course completion / a certificate.
        """
        enrollment = EnrollmentFactory(user=auth_client.user, is_active=False)
        lesson = LessonFactory(course=enrollment.course)
        response = auth_client.post(
            self.URL,
            {
                "enrollment_id": enrollment.pk,
                "lesson_id": lesson.pk,
                "watched_duration": 5,
            },
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "enrollment" in response.data

    def test_patch_progress_on_inactive_enrollment_returns_400(self, auth_client):
        """PATCH is also blocked once the enrollment is deactivated (#32).

        Simulates a refund arriving after progress already exists: the student
        must not be able to keep updating/completing it afterwards.
        """
        enrollment = EnrollmentFactory(user=auth_client.user, is_active=False)
        lesson = LessonFactory(course=enrollment.course, duration=10)
        progress = LessonProgressFactory(
            enrollment=enrollment, lesson=lesson, watched_duration=0
        )
        response = auth_client.patch(
            f"{self.URL}{progress.pk}/",
            {"watched_duration": 6},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "enrollment" in response.data

    def test_create_progress_on_other_users_enrollment_returns_400(self, auth_client):
        """A student cannot record progress against someone else's enrollment."""
        other_enrollment = EnrollmentFactory()  # belongs to another user
        lesson = LessonFactory(course=other_enrollment.course)
        response = auth_client.post(
            self.URL,
            {
                "enrollment_id": other_enrollment.pk,
                "lesson_id": lesson.pk,
                "watched_duration": 5,
            },
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "enrollment" in response.data

    def test_create_progress_negative_watched_duration_returns_400(self, auth_client):
        """A negative watched_duration is rejected (field-level validation)."""
        enrollment = EnrollmentFactory(user=auth_client.user)
        lesson = LessonFactory(course=enrollment.course)
        response = auth_client.post(
            self.URL,
            {
                "enrollment_id": enrollment.pk,
                "lesson_id": lesson.pk,
                "watched_duration": -5,
            },
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_progress_watched_exceeds_duration_returns_400(self, auth_client):
        """watched_duration greater than the lesson duration is rejected."""
        enrollment = EnrollmentFactory(user=auth_client.user)
        lesson = LessonFactory(course=enrollment.course, duration=10)
        response = auth_client.post(
            self.URL,
            {
                "enrollment_id": enrollment.pk,
                "lesson_id": lesson.pk,
                "watched_duration": 11,
            },
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @patch("apps.certificates.tasks.generate_certificate_pdf_async.delay")
    def test_create_completed_caps_watched_duration_to_lesson_duration(
        self, mock_delay, auth_client
    ):
        """completed=True with a partial watched_duration is capped to the full
        lesson duration (a completed lesson counts as fully watched)."""
        enrollment = EnrollmentFactory(user=auth_client.user)
        lesson = LessonFactory(course=enrollment.course, duration=10)
        response = auth_client.post(
            self.URL,
            {
                "enrollment_id": enrollment.pk,
                "lesson_id": lesson.pk,
                "completed": True,
                "watched_duration": 3,
            },
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        progress = LessonProgress.objects.get(pk=response.data["id"])
        assert progress.watched_duration == 10

    def test_patch_progress_updates_watched_duration(self, auth_client):
        """PATCH updates watched_duration (resume) and stamps last_watched_at."""
        enrollment = EnrollmentFactory(user=auth_client.user)
        lesson = LessonFactory(course=enrollment.course, duration=10)
        progress = LessonProgressFactory(
            enrollment=enrollment, lesson=lesson, watched_duration=0
        )
        response = auth_client.patch(
            f"{self.URL}{progress.pk}/",
            {"watched_duration": 6},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        progress.refresh_from_db()
        assert progress.watched_duration == 6
        assert progress.last_watched_at is not None

    @patch("apps.certificates.tasks.generate_certificate_pdf_async.delay")
    def test_patch_progress_complete_sets_timestamp_and_duration(
        self, mock_delay, auth_client
    ):
        """PATCH completed=True stamps completed_at and fills watched_duration."""
        enrollment = EnrollmentFactory(user=auth_client.user)
        lesson = LessonFactory(course=enrollment.course, duration=10)
        progress = LessonProgressFactory(
            enrollment=enrollment, lesson=lesson, completed=False, watched_duration=2
        )
        response = auth_client.patch(
            f"{self.URL}{progress.pk}/",
            {"completed": True},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        progress.refresh_from_db()
        assert progress.completed is True
        assert progress.completed_at is not None
        assert progress.watched_duration == 10

    def test_patch_progress_watched_exceeds_duration_returns_400(self, auth_client):
        """PATCH raising watched_duration above the lesson duration is rejected."""
        enrollment = EnrollmentFactory(user=auth_client.user)
        lesson = LessonFactory(course=enrollment.course, duration=10)
        progress = LessonProgressFactory(enrollment=enrollment, lesson=lesson)
        response = auth_client.patch(
            f"{self.URL}{progress.pk}/",
            {"watched_duration": 11},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @patch("apps.certificates.tasks.generate_certificate_pdf_async.delay")
    def test_completing_all_lessons_completes_enrollment_and_queues_certificate(
        self, mock_delay, auth_client
    ):
        """Completing every lesson auto-completes the enrollment and enqueues the
        certificate PDF task (end-to-end, with Celery .delay mocked)."""
        enrollment = EnrollmentFactory(user=auth_client.user, completed=False)
        lesson = LessonFactory(course=enrollment.course, duration=10)

        response = auth_client.post(
            self.URL,
            {
                "enrollment_id": enrollment.pk,
                "lesson_id": lesson.pk,
                "completed": True,
            },
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED

        enrollment.refresh_from_db()
        assert enrollment.completed is True
        mock_delay.assert_called_once()

        # With every lesson done, the enrollment detail exposes no next lesson.
        detail = auth_client.get(f"/api/enrollments/{enrollment.pk}/")
        assert detail.data["next_lesson"] is None
