"""
Course models for WSS Backend.

This module contains models related to courses and their organization:
- Category: Organizes courses into topics (e.g., "Web Development", "Data Science")
- Course: Represents a complete online course with videos, lessons, and enrollment

Relationships:
- Category ←→ Course (One-to-Many): A category can have many courses
- User ←→ Course (One-to-Many via instructor): An instructor can create many courses
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _ 
from django.utils.text import slugify

from apps.core.models import TimeStampedModel

User = get_user_model()

class Category(TimeStampedModel):
  """
    Course category for organizing courses by topic.
    
    Categories help users find courses by subject area. Examples:
    - Web Development
    - Data Science
    - Mobile Development
    - Design
    
    Attributes:
        name (CharField): Category name. Must be unique.
        slug (SlugField): URL-friendly version of the name. Auto-generated.
        description (TextField): Detailed description of what courses fit in this category.
        is_active (BooleanField): Whether this category is visible to users.
    
    Notes:
        - Use Django signals or admin save() to auto-generate slug from name
  """

  name = models.CharField(
    _('name'),
    max_length=100,
    unique=True,
    help_text=_('Category name')
  )

  slug = models.SlugField(
    _('slug'),
    max_length=120,
    unique=True,
    help_text=_('URL-friendly version of the name (auto-generated)')
  )

  description = models.TextField(
    _('description'),
    max_length=500,
    blank=True,
    help_text=_('Brief description of the category')
  )  

  is_active = models.BooleanField(
    _('is_active'),
    default=True,
    help_text=_('Designates whether this category should be visible')
  )

  class Meta:
    verbose_name = _('category')
    verbose_name_plural = _('categories')
    ordering = ['name']  # Alphabetical order
  
  def __str__(self):
    return self.name
  
  def save(self, *args, **kwargs):
    """Override save to auto-generate slug from name."""
    if not self.slug:
        self.slug = slugify(self.name)
    super().save(*args, **kwargs)
  
class Course(TimeStampedModel):
    """
    Represents a complete online course.
    
    A course is created by an instructor and contains multiple videos/lessons
    organized into modules. Students can enroll in courses to access content.
    
    Attributes:
        title (CharField): Course title. Must be unique.
        slug (SlugField): URL-friendly version of title.
        description (TextField): Full course description (what you'll learn, etc.)
        instructor (ForeignKey): User who created and teaches this course.
                                Must have is_instructor=True.
        category (ForeignKey): Category this course belongs to.
        thumbnail (ImageField): Course cover image.
        price (DecimalField): Course price in BRL. Use Decimal for precision.
        difficulty (CharField): Difficulty level (Beginner/Intermediate/Advanced).
        is_published (BooleanField): Whether course is visible to students.
        duration_hours (PositiveIntegerField): Estimated course duration.
        what_you_will_learn (TextField): Bullet points of learning outcomes.
        requirements (TextField): Prerequisites for taking this course.
    
    Notes:
        - instructor must be a User with is_instructor=True
        - price uses DecimalField for exact currency calculations
        - Use signals to validate instructor.is_instructor before saving
    """

    class DifficultyLevel(models.TextChoices):
       BEGINNER = 'BEG', _('Beginner')
       INTERMEDIATE = 'INT', _('Intermediate')
       ADVANCED = 'ADV', _('Advanced')
    
    title = models.CharField(
       _('title'),
       max_length=200,
       unique=True,
       help_text=_('Course title')
    )

    slug = models.SlugField(
        _('slug'),
        max_length=220,
        unique=True,
        help_text=_('URL-friendly version of the title (auto-generated)')
    )
    
    description = models.TextField(
        _('description'),
        help_text=_('Full course description')
    )
    
    instructor = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='courses_created',
        verbose_name=_('instructor'),
        help_text=_('User who created this course')
    )
    
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='courses',
        verbose_name=_('category'),
        help_text=_('Course category')
    )
    
    thumbnail = models.ImageField(
        _('thumbnail'),
        upload_to='courses/thumbnails/',
        blank=True,
        null=True,
        help_text=_('Course cover image (recommended: 1920x1080px)')
    )
    
    price = models.DecimalField(
        _('price'),
        max_digits=10,
        decimal_places=2,
        default=0.00,
        help_text=_('Course price in BRL (use 0.00 for free courses)')
    )
    
    difficulty = models.CharField(
        _('difficulty level'),
        max_length=3,
        choices=DifficultyLevel.choices,
        default=DifficultyLevel.INTERMEDIATE,
        help_text=_('Course difficulty level')
    )
    
    is_published = models.BooleanField(
        _('published'),
        default=False,
        help_text=_('Designates whether this course is visible to students')
    )
    
    duration_hours = models.PositiveIntegerField(
        _('duration (hours)'),
        default=0,
        help_text=_('Estimated course duration in hours')
    )
    
    what_you_will_learn = models.TextField(
        _('what you will learn'),
        blank=True,
        help_text=_('Bullet points of learning outcomes')
    )
    
    requirements = models.TextField(
        _('requirements'),
        blank=True,
        help_text=_('Prerequisites for this course')
    )
    
    class Meta:
        verbose_name = _('course')
        verbose_name_plural = _('courses')
        ordering = ['-created_at']  # Newest first
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['is_published', '-created_at']),
        ]
    
    def __str__(self):
        return self.title
    
    def save(self, *args, **kwargs):
        """Override save to auto-generate slug from title."""
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)
    
    @property
    def is_free(self):
        """Check if course is free."""
        return self.price == 0
    
    def get_enrolled_count(self):
        """Return number of students enrolled."""
        return self.enrollments.filter(is_active=True).count()