"""
Certificate Serializers Module

Handles serialization of Certificate model for API responses.
Exposes computed properties from the model for client consumption.

All fields are read-only since certificates are auto-generated via signals.
Clients cannot create or modify certificates through the API.
"""

from rest_framework import serializers

from .models import Certificate


class CertificateSerializer(serializers.ModelSerializer):
    """
    Serializer for Certificate model with computed properties.

    Exposes model properties as read-only fields for API consumption:
    - student_name: Student's full name from enrollment.user
    - course_title: Course title from enrollment.course
    - instructor_name: Instructor's name from enrollment.course.instructor
    - completion_date: When enrollment was completed
    - pdf_url: Absolute URL to PDF file (if exists)

    All fields are read-only since certificates are automatically generated
    via Django signals when enrollment.completed = True.

    Usage:
        # List certificates
        serializer = CertificateSerializer(certificates, many=True)

        # Single certificate with request context for absolute URLs
        serializer = CertificateSerializer(certificate, context={'request': request})
    """

    student_name = serializers.CharField(read_only=True)
    course_title = serializers.CharField(read_only=True)
    instructor_name = serializers.CharField(read_only=True)
    completion_date = serializers.DateTimeField(read_only=True)

    pdf_url = serializers.SerializerMethodField()

    class Meta:
        model = Certificate
        fields = [
            "id",
            "certificate_code",
            "student_name",
            "course_title",
            "instructor_name",
            "issued_at",
            "completion_date",
            "is_valid",
            "pdf_file",
            "pdf_url",
        ]

        read_only_fields = [
            "id",
            "certificate_code",
            "issued_at",
            "pdf_file",
        ]

    def get_pdf_url(self, obj):
        """
        Return absolute URL to PDF file if it exists.

        If request context is available, builds absolute URI with domain.
        Otherwise returns relative file URL from MEDIA_URL.
        Returns None if PDF was not generated (pdf_generation_failed_at is set).

        Args:
            obj (Certificate): Certificate instance

        Returns:
            str | None: Absolute URL to PDF or None if file doesn't exist
        """
        if obj.pdf_file:
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(obj.pdf_file.url)
            return obj.pdf_file.url
        return None
