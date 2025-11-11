"""
Django Admin configuration for Enrollments app.
"""

from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import Enrollment, LessonProgress

@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):

  list_display = ('user', 'course', 'progress_percentage', 'is_active', 'completed', 'enrolled_at')
  list_filter = ('is_active', 'completed', 'certificate_issued', 'enrolled_at')
  search_fields = ('user__email', 'user__username', 'course__title')
  readonly_fields = ('enrolled_at', 'completed_at', 'created_at', 'updated_at', 'progress_percentage', 'total_watched_duration')
  list_editable = ('is_active',)
  
  fieldsets = (
      (_('Enrollment'), {
          'fields': ('user', 'course', 'enrolled_at')
      }),
      (_('Progress'), {
          'fields': ('is_active', 'completed', 'completed_at', 'progress_percentage', 'total_watched_duration')
      }),
      (_('Certificate'), {
          'fields': ('certificate_issued',)
      }),
      (_('Feedback'), {
          'fields': ('rating', 'review'),
          'classes': ('collapse',)
      }),
      (_('Timestamps'), {
          'fields': ('created_at', 'updated_at'),
          'classes': ('collapse',)
      }),
  )
  
  def get_queryset(self, request):
      """Optimize queries with select_related."""
      qs = super().get_queryset(request)
      return qs.select_related('user', 'course')
  
@admin.register(LessonProgress)
class LessonProgressAdmin(admin.ModelAdmin):
   
  list_display = ('get_student', 'lesson', 'progress_percentage', 'completed', 'last_watched_at')
  list_filter = ('completed', 'created_at')
  search_fields = ('enrollment__user__email', 'enrollment__user__username', 'lesson__title')
  readonly_fields = ('created_at', 'updated_at', 'completed_at', 'progress_percentage')
  
  fieldsets = (
      (_('Progress'), {
          'fields': ('enrollment', 'lesson', 'completed', 'completed_at')
      }),
      (_('Viewing Data'), {
          'fields': ('watched_duration', 'last_watched_at', 'progress_percentage')
      }),
      (_('Timestamps'), {
          'fields': ('created_at', 'updated_at'),
          'classes': ('collapse',)
      }),
  )
  
  def get_student(self, obj):
      """Display student name in list view."""
      return obj.enrollment.user.get_full_name()
  get_student.short_description = 'Student'
  get_student.admin_order_field = 'enrollment__user__email'
  
  def get_queryset(self, request):
      """Optimize queries with select_related."""
      qs = super().get_queryset(request)
      return qs.select_related('enrollment__user', 'lesson')