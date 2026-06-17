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
    - download_url: Gated download endpoint for the PDF (None if not generated)

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

    download_url = serializers.SerializerMethodField()

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
            "download_url",
        ]

        read_only_fields = [
            "id",
            "certificate_code",
            "issued_at",
        ]

    def get_download_url(self, obj):
        """
        Return the gated download endpoint URL for the PDF (#74).

        The raw ``pdf_file``/``pdf_url`` are never exposed: the PDF embeds PII
        and was reachable at a guessable public ``/media/`` path. Clients must
        go through the authenticated, owner-checked ``download`` action, which
        serves the bytes via Nginx X-Accel-Redirect.

        Args:
            obj (Certificate): Certificate instance.

        Returns:
            str | None: Absolute (or relative) URL of the download action, or
            None if no PDF has been generated yet.
        """
        if not obj.pdf_file:
            return None
        request = self.context.get("request")
        path = f"/api/certificates/{obj.pk}/download/"
        if request:
            return request.build_absolute_uri(path)
        return path
