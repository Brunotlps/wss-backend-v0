"""
Certificate Model for WSS Backend.

This module defines the Certificate model which represents digital certificates
issued to students upon course completion.

Certificates are automatically generated via Django signals when an enrollment
is marked as completed. Each certificate contains:
- Unique validation code
- PDF file with student/course information
- Issue date
- Validity status (allows revocation without deletion)

Relationships:
- Certificate ←→ Enrollment (One-to-One): Each enrollment has one certificate
"""

from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import TimeStampedModel
from apps.enrollments.models import Enrollment


class Certificate(TimeStampedModel):
    """
    Digital certificate of course completion.

    Generated automatically when enrollment.completed = True.
    Contains PDF with student data, course information, instructor,
    and unique validation code.

    Attributes:
        enrollment (OneToOneField): The enrollment this certificate belongs to.
        certificate_code (CharField): Unique code for validation (e.g., WSS-2026-ABC123).
        issued_at (DateTimeField): When the certificate was issued.
        pdf_file (FileField): PDF file stored in media/certificates/.
        is_valid (BooleanField): Allows certificate revocation without deletion.

    Notes:
        - Certificate is generated via Signal in signals.py
        - PDF is generated via utils.generate_certificate_pdf()
        - Validation is public (no authentication required)
    """

    enrollment = models.OneToOneField(
        Enrollment,
        on_delete=models.CASCADE,
        related_name="certificate",
        verbose_name=_("enrollment"),
        help_text=_("Enrollment this certificate belongs to"),
    )

    certificate_code = models.CharField(
        _("certificate code"),
        max_length=24,
        unique=True,
        db_index=True,
        null=True,
        blank=True,
        help_text=_("Unique validation code (format: WSS-YYYY-XXXXXXXXXXXX)"),
    )

    issued_at = models.DateTimeField(
        _("issued at"),
        auto_now_add=True,
        help_text=_("Date and time when certificate was issued"),
    )

    pdf_file = models.FileField(
        _("PDF file"),
        upload_to="certificates/%Y/%m/",
        blank=True,
        null=True,
        help_text=_("PDF file of the certificate"),
    )

    is_valid = models.BooleanField(
        _("is valid"),
        default=True,
        help_text=_("Whether this certificate is valid (allows revocation)"),
    )

    pdf_generation_failed_at = models.DateTimeField(
        _("PDF generation failed at"),
        null=True,
        blank=True,
        help_text=_("Timestamp of the last PDF generation failure"),
    )

    # Denormalized snapshot, populated once at issue time and never rewritten,
    # so an issued certificate is an immutable, durable legal document: editing
    # or deleting the source course/user/enrollment does not change it (#77).
    # The public properties below prefer the snapshot and fall back to the live
    # lookup only when it is empty (legacy rows before backfill).
    student_name_snapshot = models.CharField(
        _("student name (snapshot)"),
        max_length=255,
        blank=True,
        default="",
        help_text=_("Student full name captured when the certificate was issued"),
    )

    course_title_snapshot = models.CharField(
        _("course title (snapshot)"),
        max_length=200,
        blank=True,
        default="",
        help_text=_("Course title captured when the certificate was issued"),
    )

    instructor_name_snapshot = models.CharField(
        _("instructor name (snapshot)"),
        max_length=255,
        blank=True,
        default="",
        help_text=_("Instructor name captured when the certificate was issued"),
    )

    completion_date_snapshot = models.DateTimeField(
        _("completion date (snapshot)"),
        null=True,
        blank=True,
        help_text=_("Completion date captured when the certificate was issued"),
    )

    class Meta:
        verbose_name = _("certificate")
        verbose_name_plural = _("certificates")
        ordering = ["-issued_at"]  # Newest first
        indexes = [
            models.Index(fields=["certificate_code"]),
            models.Index(fields=["enrollment"]),
            models.Index(fields=["-issued_at"]),
        ]

    def __str__(self):
        code = self.certificate_code or "(pending)"
        return f"{code} - {self.enrollment.user.get_full_name()}"

    @property
    def student_name(self):
        """Issued student name: stored snapshot, else live lookup (#77)."""
        if self.student_name_snapshot:
            return self.student_name_snapshot
        if self.enrollment_id:
            return self.enrollment.user.get_full_name() or self.enrollment.user.email
        return ""

    @property
    def course_title(self):
        """Issued course title: stored snapshot, else live lookup (#77)."""
        if self.course_title_snapshot:
            return self.course_title_snapshot
        if self.enrollment_id:
            return self.enrollment.course.title
        return ""

    @property
    def instructor_name(self):
        """Issued instructor name: stored snapshot, else live lookup (#77)."""
        if self.instructor_name_snapshot:
            return self.instructor_name_snapshot
        if self.enrollment_id:
            instructor = self.enrollment.course.instructor
            if instructor:
                return instructor.get_full_name() or instructor.email
        return ""

    @property
    def completion_date(self):
        """Issued completion date: stored snapshot, else live lookup (#77)."""
        if self.completion_date_snapshot:
            return self.completion_date_snapshot
        if self.enrollment_id:
            return self.enrollment.completed_at
        return None
