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
        related_name='certificate',
        verbose_name=_('enrollment'),
        help_text=_('Enrollment this certificate belongs to')
    )
    
    certificate_code = models.CharField(
        _('certificate code'),
        max_length=15,
        unique=True,
        db_index=True,
        help_text=_('Unique validation code (format: WSS-YYYY-XXXXXX)')
    )
    
    issued_at = models.DateTimeField(
        _('issued at'),
        auto_now_add=True,
        help_text=_('Date and time when certificate was issued')
    )
    
    pdf_file = models.FileField(
        _('PDF file'),
        upload_to='certificates/%Y/%m/',
        blank=True,
        null=True,
        help_text=_('PDF file of the certificate')
    )
    
    is_valid = models.BooleanField(
        _('is valid'),
        default=True,
        help_text=_('Whether this certificate is valid (allows revocation)')
    )
    
    pdf_generation_failed_at = models.DateTimeField(
        _('PDF generation failed at'),
        null=True,
        blank=True,
        help_text=_('Timestamp of the last PDF generation failure')
    )

    class Meta:
        verbose_name = _('certificate')
        verbose_name_plural = _('certificates')
        ordering = ['-issued_at']  # Newest first
        indexes = [
            models.Index(fields=['certificate_code']),
            models.Index(fields=['enrollment']),
            models.Index(fields=['-issued_at']),
        ]
    
    def __str__(self):
        return f"{self.certificate_code} - {self.enrollment.user.get_full_name()}"
    
    @property
    def student_name(self):
        return self.enrollment.user.get_full_name() or self.enrollment.user.email
    
    @property
    def course_title(self):
        return self.enrollment.course.title
    
    @property
    def instructor_name(self):
        instructor = self.enrollment.course.instructor
        return instructor.get_full_name() or instructor.email
    
    @property
    def completion_date(self):
        return self.enrollment.completed_at