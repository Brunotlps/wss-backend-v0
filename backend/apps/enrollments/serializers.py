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
from django.utils import timezone
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


class EnrollmentDetailSerializer(serializers.ModelSerializer):
    """
    Detailed enrollment serializer for individual enrollment views.
    
    Provides complete enrollment information including full progress
    tracking for all lessons and next lesson recommendation.
    
    Fields:
        - id: Enrollment identifier
        - course: Nested course information
        - enrolled_at: Enrollment timestamp
        - is_active: Whether enrollment is active
        - completed: Whether course is completed
        - completed_at: Course completion timestamp
        - certificate_issued: Whether certificate was generated
        - rating: Student's course rating (1-5, nullable)
        - review: Written review text
        - progress_percentage: % of lessons completed
        - total_watched_duration: Total minutes watched
        - lesson_progress: List of all lesson progress records (nested)
        - next_lesson: Next incomplete lesson (computed)
    
    Used in:
        - GET /api/enrollments/{id}/ (enrollment details)
    """
    
    # Nested course info
    course = CourseListSerializer(read_only=True)
    
    # @properties from Enrollment model
    progress_percentage = serializers.FloatField(source='progress_percentage', read_only=True)
    
    total_watched_duration = serializers.IntegerField(source='total_watched_duration', read_only=True)
    
    # Nested list of all lesson progress (many=True)
    lesson_progress = LessonProgressListSerializer(many=True, read_only=True)
    
    # Navigation helper (SerializerMethodField)
    next_lesson = serializers.SerializerMethodField()
    
    class Meta:
        model = Enrollment
        fields = [
            'id',
            'course',
            'enrolled_at',
            'is_active',
            'completed',
            'completed_at',
            'certificate_issued',
            'rating',
            'review',
            'progress_percentage',
            'total_watched_duration',
            'lesson_progress',
            'next_lesson'
        ]
        read_only_fields = [
            'id',
            'enrolled_at',
            'completed_at',
            'certificate_issued'
        ]
    
    def get_next_lesson(self, obj):
        """
        Return the next lesson to watch (first incomplete lesson).
        
        Uses the model's get_next_lesson() method to find the next
        incomplete lesson based on progress tracking.
        
        Args:
            obj (Enrollment): The enrollment instance
            
        Returns:
            dict or None: Serialized lesson data if exists, None if all completed
        """
        next_lesson_obj = obj.get_next_lesson()
        if next_lesson_obj:
            return LessonListSerializer(next_lesson_obj).data
        return None
    

class LessonProgressSerializer(serializers.ModelSerializer):
    """
    Serializer for creating and updating lesson progress.
    
    Handles student progress tracking with the following features:
    - Progress creation when starting a lesson
    - Watched duration updates (resume functionality)
    - Lesson completion marking
    - Automatic timestamp management
    
    Business Rules:
        - watched_duration cannot exceed lesson.duration
        - Only enrollment owner can update progress
        - completed=True auto-sets completed_at timestamp
        - last_watched_at updates on every watched_duration change
    
    Used in:
        - POST /api/progress/ (create new progress)
        - PATCH /api/progress/{id}/ (update progress)
    """
    

    progress_percentage = serializers.FloatField(source='progress_percentage', read_only=True)
    
    
    class Meta:
        model = LessonProgress
        fields = [
            'id', 'enrollment', 'lesson', 'completed', 'completed_at',
            'watched_duration', 'last_watched_at', 'progress_percentage'
        ]
        
        read_only_fields = ['id', 'completed_at', 'last_watched_at', 'progress_percentage']
        
        extra_kwargs = {
            'enrollment': {'write_only': True},
            'lesson': {'write_only': True}
        }

    
    
    def validate_watched_duration(self, value):
        """
        Validate watched_duration is not negative.
        
        Field-level validation (Nível 1).
        
        Args:
            value (int): The watched duration in minutes
            
        Returns:
            int: Validated watched duration
            
        Raises:
            ValidationError: If duration is negative
        """
        if value < 0:
            raise serializers.ValidationError("Watched duration cannot be negative.")
        return value
 
    
    
    def validate(self, attrs):
        """
        Validate object-level business rules.
        
        Object-level validation (Nível 2):
        - watched_duration cannot exceed lesson.duration
        - Only enrollment owner can create/update progress
        
        Args:
            attrs (dict): Validated field data from level 1
            
        Returns:
            dict: Validated attributes
            
        Raises:
            ValidationError: If business rules are violated
        """


        request = self.context.get('request')
        user = request.user if request else None

        enrollment = attrs.get('enrollment') if 'enrollment' in attrs else (self.instance.enrollment if self.instance else None)
        lesson = attrs.get('lesson') if 'lesson' in attrs else (self.instance.lesson if self.instance else None)

        if enrollment and user and enrollment.user != user:
            raise serializers.ValidationError({
                'enrollment': "You can only update your own progress."
            })
        
        if lesson:
            watched_duration = attrs.get('watched_duration', self.instance.watched_duration if self.instance else 0)
            if watched_duration > lesson.duration:
                raise serializers.ValidationError({
                    'watched_duration': f"Watched duration cannot exceed lesson duration of {lesson.duration} minutes."
                })
            
        if attrs.get('completed') and 'watched_duration' in attrs:
            if attrs['watched_duration'] != lesson.duration:
                attrs['watched_duration'] = lesson.duration

        return attrs
    
    
    def update(self, instance, validated_data):
        """
        Update lesson progress with automatic timestamp management.
        
        Auto-sets:
        - completed_at when completed changes from False to True
        - last_watched_at when watched_duration changes
        - watched_duration = lesson.duration when completed=True
        
        Args:
            instance (LessonProgress): Existing progress record
            validated_data (dict): Validated data to update
            
        Returns:
            LessonProgress: Updated progress instance
        """

        if validated_data.get('completed') and not instance.completed:
            validated_data['completed_at'] = timezone.now()
        

        if 'watched_duration' in validated_data:
            validated_data['last_watched_at'] = timezone.now()
        
        if validated_data.get('completed'):
            validated_data['watched_duration'] = instance.lesson.duration
        

        return super().update(instance, validated_data)
    

class EnrollmentUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating enrollments (rating, review, activation).
    
    Allows students to:
    - Rate courses (1-5 stars)
    - Write reviews/feedback
    - Activate/deactivate enrollments
    
    Business Rules:
        - Only enrollment owner can update
        - Rating must be between 1-5
        - Review requires at least one completed lesson
        - Cannot modify user, course, or system-managed fields
    
    Used in:
        - PATCH /api/enrollments/{id}/ (update enrollment)
    """
    
    # @property from Enrollment model (useful for frontend after update)
    progress_percentage = serializers.FloatField(source='progress_percentage', read_only=True)
    
    class Meta:
        model = Enrollment
        fields = [
            'id',
            'is_active',
            'rating',
            'review',
            'completed',
            'completed_at',
            'progress_percentage'
        ]
        read_only_fields = ['id', 'completed', 'completed_at', 'progress_percentage']
    

    def validate_rating(self, value):
        """
        Validate rating is within 1-5 range.
        
        Field-level validation (Nível 1).
        
        Args:
            value (int or None): Rating value
            
        Returns:
            int or None: Validated rating
            
        Raises:
            ValidationError: If rating is out of range
        """
        if value is not None and (value < 1 or value > 5):
            raise serializers.ValidationError("Rating must be between 1 and 5 stars.")
        return value
    
    def validate(self, attrs):
        """
        Validate object-level business rules.
        
        Validations:
        - Only enrollment owner can update
        - Review requires at least one completed lesson
        
        Args:
            attrs (dict): Validated field data
            
        Returns:
            dict: Validated attributes
            
        Raises:
            ValidationError: If business rules are violated
        """


        request = self.context.get('request')
        user = request.user if request else None
        
        if self.instance and user and self.instance.user != user:
            raise serializers.ValidationError({
                'enrollment': "You can only update your own enrollment."
            })
        
        if 'review' in attrs and attrs['review']:
            if self.instance.lesson_progress.filter(completed=True).count() == 0:
                raise serializers.ValidationError({
                    'review': "You must complete at least one lesson before reviewing the course."
                })
        
        return attrs


