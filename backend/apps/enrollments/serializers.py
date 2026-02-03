"""
Enrollment Serializers Module

This module provides serializers for enrollment and progress tracking,
handling student-course relationships and lesson completion tracking.

Key Features:
- Enrollment management (create, list, detail)
- Progress tracking per lesson
- Course completion calculation
- Rating and review functionality
"""

from rest_framework import serializers
from .models import Enrollment, LessonProgress, Course
from apps.videos.serializers import LessonListSerializer


class LessonProgressListSerializer(serializers.ModelSerializer):
  """
  Minimal lesson progress serializer for list views.
  
  Shows essential progress information for displaying in progress lists
  or as nested data within enrollment details. Includes lesson basic info
  and progress status without full lesson details.
  
  Fields:
      - id: Progress record identifier
      - lesson: Nested lesson basic info (title, order, duration)
      - completed: Whether lesson was completed
      - watched_duration: Minutes watched (for resume)
      - progress_percentage: Calculated % watched
      - last_watched_at: Last viewing timestamp
  
  Used in:
      - Nested in EnrollmentDetailSerializer
      - GET /api/enrollments/{id}/progress/ (list progress)
  """

  progress_percentage = serializers.FloatField(source='progress_percentage', read_only=True) 
  lesson = LessonListSerializer(read_only=True) # Nested Serializer
  
  class Meta:
      model = LessonProgress
      fields = [
          'id',
          'lesson',
          'completed',
          'watched_duration',
          'progress_percentage',
          'last_watched_at'
      ]
      
      read_only_fields = ['id', 'last_watched_at']  


class CourseListSerializer(serializers.ModelSerializer):
    """
    Minimal course serializer for nested use in enrollments.
    
    Provides essential course information without full details.
    Includes instructor name for display purposes.
    
    Fields:
        - id: Course identifier
        - title: Course name
        - slug: URL-friendly identifier
        - thumbnail: Course cover image
        - instructor_name: Full name of course instructor
        - difficulty: Course difficulty level
    
    Used in:
        - Nested in EnrollmentListSerializer
        - Nested in EnrollmentDetailSerializer
    """
    
    instructor_name = serializers.CharField(source='instructor.get_full_name', read_only=True)
    
    class Meta:
        model = Course
        fields = [
            'id',
            'title',
            'slug',
            'thumbnail',
            'instructor_name',
            'difficulty'
        ]
        read_only_fields = ['id', 'slug']


class EnrollmentListSerializer(serializers.ModelSerializer):
    """
    Enrollment list serializer for "My Courses" dashboard.
    
    Shows active and completed enrollments with progress information
    and basic course details.
    
    Fields:
        - id: Enrollment identifier
        - course: Nested course information
        - enrolled_at: Enrollment timestamp
        - is_active: Whether enrollment is active
        - completed: Whether course is completed
        - progress_percentage: % of lessons completed
        - total_watched_duration: Total minutes watched
    
    Used in:
        - GET /api/enrollments/ (list user's courses)
    """
    
    # Nested course info
    course = CourseListSerializer(read_only=True)
    
    # @properties from Enrollment model
    progress_percentage = serializers.FloatField(source='progress_percentage', read_only=True)
    
    total_watched_duration = serializers.IntegerField(source='total_watched_duration', read_only=True)
    
    class Meta:
        model = Enrollment
        fields = [
            'id',
            'course',
            'enrolled_at',
            'is_active',
            'completed',
            'progress_percentage',
            'total_watched_duration'
        ]
        read_only_fields = ['id', 'enrolled_at']