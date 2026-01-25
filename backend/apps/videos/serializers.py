"""
Video Serializers Module

This module provides serializers for the Video model, handling data validation,
serialization, and deserialization for video-related API endpoints.

Key Features:
- Video file upload validation (size and format)
- Automatic file size calculation
- Computed fields for human-readable formats
- CRUD operations support
"""

from rest_framework import serializers 
from .models import Video, Lesson




class VideoSerializer(serializers.ModelSerializer):
  """
  Serializer for Video CRUD operations.

  Handles video file uploads with validation for file size and format.
  Includes computed fields for human-readable file size and duration.

  Validations:
  - File size must not exceed 500MB
  - Only video formats are accepted (mp4, webm, avi, mov)
  - file_size is automatically calculated from uploaded file
  """

  file_size_mb = serializers.SerializerMethodField()
  duration_formatted = serializers.SerializerMethodField()

  class Meta:
    model = Video
    fields = [
      'id', 'title', 'file', 'duration', 'thumbnail',
      'file_size', 'is_processed', 'file_size_mb',
      'created_at', 'updated_at', 'duration_formatted'            
    ]
    read_only_fields = ['id', 'file_size', 'is_processed', 'created_at', 'updated_at']


  def get_file_size_mb(self, obj):
    """
    Return file size in megabytes.
    
    Uses the @property method from the Video model.
    
    Args:
        obj (Video): The video instance being serialized
        
    Returns:
        float: File size in MB (e.g., 125.5)
    """
    return obj.file_size_mb

  def get_duration_formatted(self, obj):
    """
    Return duration in HH:MM:SS format.
    Uses the @property method from the Video model.
    Args:
        obj (Video): The video instance being serialized
    Returns:
        str: Duration formatted as "HH:MM:SS" (e.g., "01:30:45")
    """
    return obj.duration_formatted



  def validate_file(self, value):
    """
    Validate video file upload.
    
    Ensures uploaded file meets size and format requirements.
    This method is automatically called by DRF during validation.
    
    Args:
        value (UploadedFile): The uploaded file object
        
    Returns:
        UploadedFile: The validated file
        
    Raises:
        ValidationError: If file is too large or has invalid format
    """
    
    
    max_size = 500 * 1024 * 1024
    
    
    if value.size > max_size:
      raise serializers.ValidationError(
        f"File size must not exceed 500MB. Current size: {value.size / (1024 * 1024):.2f}MB"
      )
    
    # Accepted video formats 
    valid_extensions = ['mp4', 'webm', 'avi', 'mov']
    allowed_mimes = ['video/mp4', 'video/webm', 'video/x-msvideo']
    
    file_extension = value.name.split('.')[-1].lower()
    
    if file_extension not in valid_extensions:
      raise serializers.ValidationError(
        f"Invalid file format. Accepted formats: {', '.join(valid_extensions)}"
      )
    
    if value.content_type not in allowed_mimes:
      raise serializers.ValidationError("Invalid MIME type")
    
    # Additional validation layers to be implemented in the future, such as Magic bytes, among others...
    
    return value
  

  def create(self, validated_data):
    """
    Create video instance and auto-calculate file_size.
    
    The file_size field is automatically populated from the uploaded file's size.
    This ensures the stored value matches the actual file size.
    
    Args:
        validated_data (dict): Validated data from the serializer
        
    Returns:
        Video: Created video instance
    """    

    
    if 'file' in validated_data:
      validated_data['file_size'] = validated_data['file'].size

    return super().create(validated_data)


  def update(self, instance, validated_data):
    """
    Update video instance and recalculate file_size if file changed.
    
    If a new file is uploaded, the file_size is automatically updated.
    Other fields are updated normally.
    
    Args:
        instance (Video): Existing video instance
        validated_data (dict): Validated data from the serializer
        
    Returns:
        Video: Updated video instance
    """
    
    if 'file' in validated_data:
        validated_data['file_size'] = validated_data['file'].size
    
    return super().update(instance, validated_data)  


class VideoListSerializer(serializers.ModelSerializer):
    """
    Minimal video serializer for list views and nested relationships.
    
    Used when displaying videos in lists or as part of another resource (Lesson)
    without loading full video details.
    
    Fields:
        - id: Video identifier
        - title: Video title
        - duration_formatted: Human-readable duration (HH:MM:SS)
        - thumbnail: Preview image URL
    """
    

    duration_formatted = serializers.CharField(source='duration_formatted', read_only=True)

    class Meta:
      model = Video
      fields = [
        'id',
        'title', 
        'duration_formatted',
        'thumbnail'
      ]


class LessonListSerializer(serializers.ModelSerializer):
  """
  Minimal lesson serializer for list views.
  
  Shows essential lesson information for displaying in course content lists.
  Includes course title and video thumbnail without loading full related objects.
  
  Fields:
      - id: Lesson identifier
      - title: Lesson title
      - order: Position in the course sequence
      - course_title: Name of the course this lesson belongs to
      - duration_formatted: Human-readable duration (e.g., "45min", "1h 30min")
      - is_free_preview: Whether non-enrolled users can watch
      - video_thumbnail: Preview image from the associated video
  """
  
  
  course_title = serializers.CharField(source='course.title', read_only=True)
  
  duration_formatted = serializers.CharField(source='duration_formatted', read_only=True)
  
  video_thumbnail = serializers.ImageField(
    source='video.thumbnail',  
    read_only=True,
    allow_null=True  
  )
  
  class Meta:
    model = Lesson
    fields = [
      'id',
      'title',
      'order',
      'course_title',     
      'duration_formatted',  
      'is_free_preview',
      'video_thumbnail'   
    ]


class LessonDetailSerializer(serializers.ModelSerializer):
  """
  Detailed lesson serializer for individual lesson views.
  
  Provides comprehensive lesson information including full video details
  and navigation to adjacent lessons in the course.
  
  Features:
      - Complete lesson information (title, description, duration, order)
      - Nested video details using VideoListSerializer
      - Course title reference
      - Next/Previous lesson navigation
  
  Used in:
      - GET /api/lessons/{id}/ - Retrieve specific lesson details
  """
  

  course_title = serializers.CharField(source='course.title', read_only=True)
  duration_formatted = serializers.CharField(source='duration_formatted', read_only=True)
  video = VideoListSerializer(read_only=True)
  
  next_lesson = serializers.SerializerMethodField()
  previous_lesson = serializers.SerializerMethodField()
  
  class Meta:
    model = Lesson
    fields = [
      'id',
      'title',
      'description',
      'order',
      'is_free_preview',
      'duration',
      'duration_formatted',
      'course_title',
      'video',
      'next_lesson',
      'previous_lesson',
      'created_at',
      'updated_at'
    ]
    read_only_fields = ['id', 'created_at', 'updated_at']
  
  def get_next_lesson(self, obj):
    """
    Return the next lesson in the course.
    
    Uses the model's get_next_lesson() method to find the subsequent
    lesson based on order field. Returns serialized lesson data or None.
    
    Args:
        obj (Lesson): The current lesson instance
        
    Returns:
        dict or None: Serialized lesson data if exists, None otherwise
    """


    next_lesson = obj.get_next_lesson()
    if next_lesson:
      return LessonListSerializer(next_lesson).data
    return None
  
  def get_previous_lesson(self, obj):
    """
    Return the previous lesson in the course.
    
    Uses the model's get_previous_lesson() method to find the preceding
    lesson based on order field. Returns serialized lesson data or None.
    
    Args:
        obj (Lesson): The current lesson instance
        
    Returns:
        dict or None: Serialized lesson data if exists, None otherwise
    """
    previous_lesson = obj.get_previous_lesson()
    if previous_lesson:
      return LessonListSerializer(previous_lesson).data
    return None
  

class LessonCreateSerializer(serializers.ModelSerializer):
  """
  Serializer for creating new lessons.
  
  Enforces business rules and data integrity constraints:
  - User can only create lessons in their own courses
  - Order must be unique within the course
  - Video can only be used in one lesson (OneToOneField constraint)
  
  Validations:
  - Ownership: course.instructor must match request.user
  - unique_together: [course, order] must be unique
  - OneToOne: video must not already have a lesson
  """


  class Meta:
    model = Lesson
    fields = [
      'title', 'course', 'video', 'order',
      'description', 'is_free_preview', 'duration'      
    ]
  

  def validate_video(self, value):
    """
    Validate video is not already used in another lesson.
    
    OneToOneField constraint: a video can only belong to one lesson.
    
    Args:
        value (Video): The video instance
        
    Returns:
        Video: Validated video instance
        
    Raises:
        ValidationError: If video is already associated with a lesson
    """


    if hasattr(value, 'lesson'):
      raise serializers.ValidationError(
        f"This video is already associated with lesson: {value.lesson.title}"
      )
    
    return value
  
  def validate(self, data):
    """
    Validate combined field constraints.

    Checks:
    1. Ownership: User can only create lessons in their own courses
    2. unique_together: [course, order] must be unique

    Args:
        data (dict): Validated field data

    Returns:
        dict: Validated data

    Raises:
        ValidationError: If ownership or uniqueness constraints fail
    """

    # Validate ownership: user can only create lessons in their own courses
    request = self.context.get('request')
    course = data.get('course')
    
    if request and course:
      if not hasattr(request, 'user') or not request.user.is_authenticated:
        raise serializers.ValidationError(
          "Authentication required to create lessons."
        )
      
      if course.instructor != request.user:
        raise serializers.ValidationError({
          'course': f"You can only create lessons in your own courses. This course belongs to {course.instructor.get_full_name() or course.instructor.username}."
        })
    
    # Validate unique_together: [course, order] must be unique
    order = data.get('order')
    if course and order is not None:
      if Lesson.objects.filter(course=course, order=order).exists():
        raise serializers.ValidationError({
            'order': f"A lesson with order {order} already exists in this course. Please choose a different order number."
        })
    
    return data

    