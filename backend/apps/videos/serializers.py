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




