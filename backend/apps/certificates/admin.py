from django.contrib import admin

from .models import Certificate


@admin.register(Certificate)
class CertificateAdmin(admin.ModelAdmin):
    list_display = [
        "certificate_code",
        "student_name",
        "course_title",
        "issued_at",
        "is_valid",
        "pdf_generation_failed_at",
    ]
    list_filter = ["is_valid", "issued_at", "pdf_generation_failed_at"]
    search_fields = [
        "certificate_code",
        "enrollment__user__email",
        "enrollment__course__title",
    ]
    readonly_fields = [
        "certificate_code",
        "enrollment",
        "issued_at",
        "pdf_file",
        "created_at",
        "updated_at",
    ]
    ordering = ["-issued_at"]

    def student_name(self, obj):
        """Display student name (snapshot-safe once orphaned, #38)."""
        return obj.student_name

    student_name.short_description = "Student"

    def course_title(self, obj):
        """Display course title (snapshot-safe once orphaned, #38)."""
        return obj.course_title

    course_title.short_description = "Course"
