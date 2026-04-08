"""Tests for Certificate model."""

import pytest

from apps.certificates.factories import CertificateFactory
from apps.courses.factories import CourseFactory
from apps.enrollments.factories import EnrollmentFactory
from apps.users.factories import InstructorFactory, UserFactory


@pytest.mark.django_db
class TestCertificateModel:
    """Test suite for the Certificate model."""

    def test_create_certificate_with_valid_data(self):
        """Certificate is created with expected defaults."""
        cert = CertificateFactory()
        assert cert.pk is not None
        assert cert.is_valid is True
        assert cert.certificate_code.startswith("WSS-")

    def test_certificate_str_format(self):
        """__str__ returns 'CODE - FullName' format."""
        user = UserFactory(first_name="Maria", last_name="Silva")
        enrollment = EnrollmentFactory(user=user)
        cert = CertificateFactory(enrollment=enrollment)
        assert cert.certificate_code in str(cert)
        assert "Maria Silva" in str(cert)

    def test_certificate_code_format(self):
        """Certificate code follows WSS-YYYY-XXXXXX format."""
        import re

        cert = CertificateFactory()
        assert re.match(r"WSS-\d{4}-[A-Z0-9]{6}$", cert.certificate_code)

    def test_certificate_code_is_unique(self):
        """Two certificates cannot share the same code."""
        from django.db import IntegrityError

        cert1 = CertificateFactory()
        enrollment2 = EnrollmentFactory()
        with pytest.raises(IntegrityError):
            CertificateFactory(
                enrollment=enrollment2,
                certificate_code=cert1.certificate_code,
            )

    def test_student_name_property(self):
        """student_name returns user's full name."""
        user = UserFactory(first_name="João", last_name="Costa")
        enrollment = EnrollmentFactory(user=user)
        cert = CertificateFactory(enrollment=enrollment)
        assert cert.student_name == "João Costa"

    def test_student_name_falls_back_to_username_when_no_name(self):
        """student_name returns username when first/last name are empty (get_full_name fallback)."""
        user = UserFactory(first_name="", last_name="")
        enrollment = EnrollmentFactory(user=user)
        cert = CertificateFactory(enrollment=enrollment)
        # get_full_name() falls back to username (not email) per User model
        assert cert.student_name == user.username

    def test_course_title_property(self):
        """course_title returns course title."""
        course = CourseFactory(title="Advanced Django")
        enrollment = EnrollmentFactory(course=course)
        cert = CertificateFactory(enrollment=enrollment)
        assert cert.course_title == "Advanced Django"

    def test_instructor_name_property(self):
        """instructor_name returns instructor's full name."""
        instructor = InstructorFactory(first_name="Prof", last_name="Santos")
        course = CourseFactory(instructor=instructor)
        enrollment = EnrollmentFactory(course=course)
        cert = CertificateFactory(enrollment=enrollment)
        assert cert.instructor_name == "Prof Santos"

    def test_completion_date_property(self):
        """completion_date returns enrollment.completed_at."""
        from django.utils import timezone

        enrollment = EnrollmentFactory()
        now = timezone.now()
        enrollment.completed_at = now
        enrollment.save()
        cert = CertificateFactory(enrollment=enrollment)
        assert cert.completion_date == now
