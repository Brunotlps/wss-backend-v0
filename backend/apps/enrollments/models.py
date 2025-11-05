"""
Enrollment and Progress models for WSS Backend.

This module manages student enrollment and learning progress:
- Enrollment: Represents a student's enrollment in a course
- LessonProgress: Tracks individual lesson completion and watch time

Relationships:
- User ←→ Course (Many-to-Many via Enrollment)
- User ←→ Lesson (Many-to-Many via LessonProgress)
- Enrollment ←→ LessonProgress (One-to-Many)

Business Rules:
- A user can only enroll once per course (unique_together)
- Progress is tracked per lesson (watched duration, completion status)
- Course completion requires all lessons marked as completed
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator, MaxValueValidator

from apps.core.models import TimeStampedModel
from apps.courses.models import Course
from apps.videos.models import Lesson

User = get_user_model()


class Enrollment(TimeStampedModel):
  """
  Student enrollment in a course.
  
  Represents the relationship between a user and a course. This is the
  "through" model for the Many-to-Many relationship between users and courses.
  Stores enrollment metadata like date, completion status, and progress.
  
  Attributes:
    user (ForeignKey): Student enrolled in the course.
    course (ForeignKey): Course the student is enrolled in.
    enrolled_at (DateTimeField): When the enrollment occurred (auto-set).
    is_active (BooleanField): Whether enrollment is currently active.
    completed (BooleanField): Whether student completed the course.
    completed_at (DateTimeField): When the course was completed.
    certificate_issued (BooleanField): Whether certificate was generated.
    rating (PositiveSmallIntegerField): Student's course rating (1-5 stars).
    review (TextField): Written review/feedback from student.
  
  Notes:
    - user + course must be unique (can't enroll twice in same course)
    - Use signals to auto-mark completed when all lessons are done
    - certi'ficate_issued triggers certificate generation task
  """
  
  user = models.ForeignKey(
      User,
      on_delete=models.CASCADE,
      related_name='enrollments',
      verbose_name=_('student'),
      help_text=_('Student enrolled in this course')
  )
  
  course = models.ForeignKey(
      Course,
      on_delete=models.CASCADE,
      related_name='enrollments',
      verbose_name=_('course'),
      help_text=_('Course the student is enrolled in')
  )
  
  enrolled_at = models.DateTimeField(
      _('enrolled at'),
      auto_now_add=True,
      help_text=_('When the enrollment occurred')
  )
  
  is_active = models.BooleanField(
      _('active'),
      default=True,
      help_text=_('Whether this enrollment is currently active')
  )
  
  completed = models.BooleanField(
      _('completed'),
      default=False,
      help_text=_('Whether the student completed the course')
  )
  
  completed_at = models.DateTimeField(
      _('completed at'),
      null=True,
      blank=True,
      help_text=_('When the course was completed')
  )
  
  certificate_issued = models.BooleanField(
      _('certificate issued'),
      default=False,
      help_text=_('Whether completion certificate was generated')
  )
  
  rating = models.PositiveSmallIntegerField(
      _('rating'),
      null=True,
      blank=True,
      validators=[MinValueValidator(1), MaxValueValidator(5)],
      help_text=_('Course rating from 1 to 5 stars')
  )
  
  review = models.TextField(
      _('review'),
      blank=True,
      help_text=_('Written review/feedback from student')
  )
  
  class Meta:
      verbose_name = _('enrollment')
      verbose_name_plural = _('enrollments')
      ordering = ['-enrolled_at']  # Newest enrollments first
      unique_together = [['user', 'course']]  # One enrollment per user per course
      indexes = [
          models.Index(fields=['user', 'is_active']),
          models.Index(fields=['course', 'is_active']),
          models.Index(fields=['completed']),
      ]
  
  def __str__(self):
      return f"{self.user.get_full_name()} → {self.course.title}"
  
  @property
  def progress_percentage(self):
      """Calculate course completion percentage based on completed lessons."""
      total_lessons = self.course.lessons.count()
      if total_lessons == 0:
          return 0
      
      completed_lessons = self.lesson_progress.filter(completed=True).count()
      return round((completed_lessons / total_lessons) * 100, 2)
  
  @property
  def total_watched_duration(self):
      """Return total minutes watched across all lessons."""
      total = self.lesson_progress.aggregate(
          models.Sum('watched_duration')
      )['watched_duration__sum']
      return total or 0
  
  def mark_as_completed(self):
      """Mark enrollment as completed and set completion timestamp."""
      from django.utils import timezone
      
      self.completed = True
      self.completed_at = timezone.now()
      self.save(update_fields=['completed', 'completed_at'])
  
  def get_next_lesson(self):
      """
      Return the next lesson to watch (first incomplete lesson).
      Returns None if all lessons are completed.
      """
      completed_lesson_ids = self.lesson_progress.filter(
          completed=True
      ).values_list('lesson_id', flat=True)
      
      return self.course.lessons.exclude(
          id__in=completed_lesson_ids
      ).order_by('order').first()


class LessonProgress(TimeStampedModel):
  """
  Track student progress on individual lessons.
  
  Records viewing progress for each lesson, including whether it's been
  completed and how much time was spent watching. This enables features
  like "resume where you left off" and progress tracking.
  
  Attributes:
      enrollment (ForeignKey): The enrollment this progress belongs to.
      lesson (ForeignKey): The specific lesson being tracked.
      completed (BooleanField): Whether student marked lesson as done.
      completed_at (DateTimeField): When the lesson was completed.
      watched_duration (PositiveIntegerField): Minutes watched (for resume).
      last_watched_at (DateTimeField): Last time student watched this lesson.
  
  Notes:
      - enrollment + lesson must be unique (one progress record per lesson)
      - watched_duration allows "resume" functionality
      - Use signals to update Enrollment.completed when all lessons done
  """
  
  enrollment = models.ForeignKey(
      Enrollment,
      on_delete=models.CASCADE,
      related_name='lesson_progress',
      verbose_name=_('enrollment'),
      help_text=_('Enrollment this progress belongs to')
  )
  
  lesson = models.ForeignKey(
      Lesson,
      on_delete=models.CASCADE,
      related_name='student_progress',
      verbose_name=_('lesson'),
      help_text=_('Lesson being tracked')
  )
  
  completed = models.BooleanField(
      _('completed'),
      default=False,
      help_text=_('Whether the student completed this lesson')
  )
  
  completed_at = models.DateTimeField(
      _('completed at'),
      null=True,
      blank=True,
      help_text=_('When the lesson was marked as completed')
  )
  
  watched_duration = models.PositiveIntegerField(
      _('watched duration (minutes)'),
      default=0,
      help_text=_('Total minutes watched (for resume functionality)')
  )
  
  last_watched_at = models.DateTimeField(
      _('last watched at'),
      null=True,
      blank=True,
      help_text=_('Last time this lesson was watched')
  )
  
  class Meta:
      verbose_name = _('lesson progress')
      verbose_name_plural = _('lesson progress')
      ordering = ['enrollment', 'lesson__order']  # Order by course, then lesson order
      unique_together = [['enrollment', 'lesson']]  # One progress per lesson per enrollment
      indexes = [
          models.Index(fields=['enrollment', 'completed']),
          models.Index(fields=['lesson', 'completed']),
      ]
  
  def __str__(self):
      status = "✓" if self.completed else "○"
      return f"{status} {self.enrollment.user.get_full_name()} - {self.lesson.title}"
  
  @property
  def progress_percentage(self):
      """Calculate progress percentage based on watched duration vs lesson duration."""
      if not self.lesson.duration or self.lesson.duration == 0:
          return 100 if self.completed else 0
      
      percentage = (self.watched_duration / self.lesson.duration) * 100
      return min(round(percentage, 2), 100)  # Cap at 100%
  
  def mark_as_completed(self):
      """Mark lesson as completed and set completion timestamp."""
      from django.utils import timezone
      
      self.completed = True
      self.completed_at = timezone.now()
      self.watched_duration = self.lesson.duration  # Mark as fully watched
      self.save(update_fields=['completed', 'completed_at', 'watched_duration'])
  
  def update_watched_duration(self, minutes):
      """
      Update watched duration and last watched timestamp.
      
      Args:
          minutes (int): Minutes watched in this session.
      """
      from django.utils import timezone
      
      self.watched_duration = min(
          self.watched_duration + minutes,
          self.lesson.duration
      )  # Don't exceed lesson duration
      self.last_watched_at = timezone.now()
      self.save(update_fields=['watched_duration', 'last_watched_at'])