from django.contrib import admin
from .models import Certificate


@admin.register(Certificate)
class CertificateAdmin(admin.ModelAdmin):
    list_display = ['certificate_code', 'student_name', 'course_title', 'issued_at', 'is_valid']
    list_filter = ['is_valid', 'issued_at']
    search_fields = ['certificate_code', 'enrollment__user__email', 'enrollment__course__title']
    readonly_fields = ['certificate_code', 'enrollment', 'issued_at', 'pdf_file', 'created_at', 'updated_at']
    ordering = ['-issued_at']
    
    def student_name(self, obj):
        """Display student name from enrollment"""
        return obj.enrollment.user.get_full_name()
    student_name.short_description = 'Student'
    
    def course_title(self, obj):
        """Display course title from enrollment"""
        return obj.enrollment.course.title
    course_title.short_description = 'Course'
