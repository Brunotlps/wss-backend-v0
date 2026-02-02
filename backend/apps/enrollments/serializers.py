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
from .models import Enrollment, LessonProgress
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