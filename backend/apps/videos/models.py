"""
Video and Lesson models for WSS Backend.

This module contains models for course content delivery:
- Video: Stores video files and metadata (duration, thumbnail, file)
- Lesson: Organizes videos into ordered lessons within courses

Relationships:
- Course ←→ Lesson (One-to-Many): A course has many lessons in order
- Lesson ←→ Video (One-to-One): Each lesson has one associated video file

Note: We separate Video (media file) from Lesson (pedagogical structure) to allow
future flexibility (e.g., lessons with PDFs, quizzes, or multiple videos).
"""

from django.db import models
from django.utils.translation import gettext_lazy as _ 
from django.core.validators import MinValueValidator

from apps.core.models import TimeStampedModel
from apps.courses.models import Course


class Video(TimeStampedModel):
  """
  Video file and metadata.
  
  Stores the actual video file along with its metadata like duration,
  thumbnail, and processing status. Separated from Lesson to allow
  reusability and future features (video library, previews, etc).
  
  Attributes:
      title (CharField): Video title (can differ from lesson title).
      file (FileField): Actual video file (MP4, WebM, etc).
      duration (DurationField): Video length (auto-extracted or manual).
      thumbnail (ImageField): Video preview image (auto-generated or uploaded).
      file_size (PositiveIntegerField): File size in bytes.
      is_processed (BooleanField): Whether video encoding is complete.
  
  Notes:
      - Use Celery tasks to process videos after upload (encoding, thumbnails)
      - Consider using django-storages + S3 for production video hosting
      - file_size stored for quota management and UI display
  
  """

  title = models.CharField(
      _('title'),
      max_length=200,
      help_text=_('Video title')
  )
  
  file = models.FileField(
      _('video file'),
      upload_to='videos/%Y/%m/',  # Organized by year/month
      help_text=_('Video file (MP4, WebM, AVI, etc)')
  )
  
  duration = models.DurationField(
      _('duration'),
      null=True,
      blank=True,
      help_text=_('Video duration (auto-extracted from file)')
  )
  
  thumbnail = models.ImageField(
      _('thumbnail'),
      upload_to='videos/thumbnails/%Y/%m/',
      blank=True,
      null=True,
      help_text=_('Video preview thumbnail (auto-generated or custom)')
  )
  
  file_size = models.PositiveIntegerField(
      _('file size'),
      default=0,
      help_text=_('File size in bytes')
  )
  
  is_processed = models.BooleanField(
      _('processed'),
      default=False,
      help_text=_('Whether video has been processed and encoded')
  )
  
  class Meta:
      verbose_name = _('video')
      verbose_name_plural = _('videos')
      ordering = ['-created_at']
  
  def __str__(self):
      return self.title
  
  @property
  def file_size_mb(self):
      """Return file size in megabytes."""
      return round(self.file_size / (1024 * 1024), 2) if self.file_size else 0
  
  @property
  def duration_formatted(self):
      """Return duration in HH:MM:SS format."""
      if not self.duration:
          return "00:00:00"
      
      total_seconds = int(self.duration.total_seconds())
      hours = total_seconds // 3600
      minutes = (total_seconds % 3600) // 60
      seconds = total_seconds % 60
      return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
  
class Lesson(TimeStampedModel):
  """
  Individual lesson within a course.
  
  Represents a single learning unit in a course. Lessons are ordered
  sequentially and contain one video. Future versions could include
  PDFs, quizzes, or other content types.
  
  Attributes:
      title (CharField): Lesson title (e.g., "Introduction to Django Models").
      course (ForeignKey): Course this lesson belongs to.
      video (OneToOneField): Associated video file.
      order (PositiveIntegerField): Lesson order within the course (1, 2, 3...).
      description (TextField): Detailed lesson description.
      is_free_preview (BooleanField): Whether non-enrolled users can watch.
      duration (PositiveIntegerField): Estimated lesson duration in minutes.
  
  Notes:
      - order + course must be unique (no duplicate orders in same course)
      - Use signals to auto-update Course.duration_hours when lessons change
      - is_free_preview allows marketing (show first lesson to attract students)
  """
  title = models.CharField(
      _('title'),
      max_length=200,
      help_text=_('Lesson title')
  )
  
  course = models.ForeignKey(
      Course,
      on_delete=models.CASCADE,
      related_name='lessons',
      verbose_name=_('course'),
      help_text=_('Course this lesson belongs to')
  )
  
  video = models.OneToOneField(
      Video,
      on_delete=models.CASCADE,
      related_name='lesson',
      verbose_name=_('video'),
      help_text=_('Video file for this lesson')
  )
  
  order = models.PositiveIntegerField(
      _('order'),
      validators=[MinValueValidator(1)],
      help_text=_('Lesson order within the course (starts at 1)')
  )
  
  description = models.TextField(
      _('description'),
      blank=True,
      help_text=_('Detailed lesson description (what will be covered)')
  )
  
  is_free_preview = models.BooleanField(
      _('free preview'),
      default=False,
      help_text=_('Allow non-enrolled users to watch this lesson')
  )
  
  duration = models.PositiveIntegerField(
      _('duration (minutes)'),
      default=0,
      help_text=_('Estimated lesson duration in minutes')
  )
  
  class Meta:
      verbose_name = _('lesson')
      verbose_name_plural = _('lessons')
      ordering = ['course', 'order']  # Order by course, then by lesson order
      unique_together = [['course', 'order']]  # Prevent duplicate orders
      indexes = [
          models.Index(fields=['course', 'order']),
          models.Index(fields=['is_free_preview']),
      ]
  
  def __str__(self):
      return f"{self.course.title} - Lesson {self.order}: {self.title}"
  
  def get_next_lesson(self):
      """Return the next lesson in the course."""
      return Lesson.objects.filter(
          course=self.course,
          order__gt=self.order
      ).order_by('order').first()
  
  def get_previous_lesson(self):
      """Return the previous lesson in the course."""
      return Lesson.objects.filter(
          course=self.course,
          order__lt=self.order
      ).order_by('-order').first()
  
  @property
  def duration_formatted(self):
      """Return duration in 'Xh Ymin' format."""
      hours = self.duration // 60
      minutes = self.duration % 60
      if hours > 0:
          return f"{hours}h {minutes}min"
      return f"{minutes}min"
