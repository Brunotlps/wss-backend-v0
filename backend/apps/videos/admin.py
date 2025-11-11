"""
Django Admin configuration for Videos app.
"""

from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import Video, Lesson

@admin.register(Video)
class VideoAdmin(admin.ModelAdmin):
  list_display = ('title', 'file_size_mb', 'duration_formatted', 'is_processed', 'created_at')
  list_filter = ('is_processed', 'created_at')
  search_fields = ('title',)
  readonly_fields = ('created_at', 'updated_at', 'file_size_mb', 'duration_formatted')
  
  fieldsets = (
      (_('Video Information'), {
          'fields': ('title', 'file', 'duration')
      }),
      (_('Media'), {
          'fields': ('thumbnail',)
      }),
      (_('Processing'), {
          'fields': ('file_size', 'is_processed')
      }),
      (_('Metadata'), {
          'fields': ('file_size_mb', 'duration_formatted', 'created_at', 'updated_at'),
          'classes': ('collapse',)
      }),
  )

@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
  list_display = ('title', 'course', 'order', 'duration', 'is_free_preview', 'created_at')
  list_filter = ('is_free_preview', 'course', 'created_at')
  search_fields = ('title', 'description', 'course__title')
  readonly_fields = ('created_at', 'updated_at')
  list_editable = ('order', 'is_free_preview')
  ordering = ('course', 'order')
  
  fieldsets = (
      (_('Lesson Information'), {
          'fields': ('title', 'course', 'video', 'order')
      }),
      (_('Content'), {
          'fields': ('description', 'duration', 'is_free_preview')
      }),
      (_('Timestamps'), {
          'fields': ('created_at', 'updated_at'),
          'classes': ('collapse',)
      }),
  )
  
  def get_queryset(self, request):
      """Optimize queries with select_related."""
      qs = super().get_queryset(request)
      return qs.select_related('course', 'video')