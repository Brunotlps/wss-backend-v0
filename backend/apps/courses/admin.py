"""
Django Admin configuration for Courses app.
"""

from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import Category, Course

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
  
  list_display = ('name', 'slug', 'is_active', 'created_at')
  list_filter = ('is_active', 'created_at')
  search_fields = ('name', 'description')
  prepopulated_fields = {'slug': ('name',)}  # Auto-generate slug from name
  readonly_fields = ('created_at', 'updated_at')
  
  fieldsets = (
      (None, {
          'fields': ('name', 'slug', 'description', 'is_active')
      }),
      (_('Timestamps'), {
          'fields': ('created_at', 'updated_at'),
          'classes': ('collapse',)
      }),
  )

@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):

  list_display = ('title', 'instructor', 'category', 'difficulty', 'price', 'is_published', 'created_at')
  list_filter = ('is_published', 'difficulty', 'category', 'created_at')
  search_fields = ('title', 'description', 'instructor__email', 'instructor__username')
  prepopulated_fields = {'slug': ('title',)}
  readonly_fields = ('created_at', 'updated_at')
  list_editable = ('is_published',)  # Edit directly in list view
  
  fieldsets = (
      (_('Basic Information'), {
          'fields': ('title', 'slug', 'description', 'instructor', 'category')
      }),
      (_('Media'), {
          'fields': ('thumbnail',)
      }),
      (_('Course Details'), {
          'fields': ('price', 'difficulty', 'duration_hours', 'what_you_will_learn', 'requirements')
      }),
      (_('Publishing'), {
          'fields': ('is_published',)
      }),
      (_('Timestamps'), {
          'fields': ('created_at', 'updated_at'),
          'classes': ('collapse',)
      }),
  )
  
  def get_queryset(self, request):
      """
      Optimize queries with select_related.
      
      This reduces database queries by fetching related objects
      (instructor, category) in a single query using SQL JOIN.
      """
      qs = super().get_queryset(request)
      return qs.select_related('instructor', 'category')