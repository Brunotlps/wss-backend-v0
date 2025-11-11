"""
User models for WSS Backend.

This module contains user-related models including:
- Custom User model extending Django's AbstractUser
- Profile model for additional user information

The User model is configured as the AUTH_USER_MODEL in settings.py.
"""

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import TimeStampedModel


class User(AbstractUser, TimeStampedModel):
  """
  Custom User model extending Django's AbstractUser.
    
  This model extends the default Django User with additional fields
  specific to the WSS platform. It inherits all standard fields from
  AbstractUser (username, email, password, first_name, last_name, etc.)
  and adds custom fields for our application needs.
  
  Attributes:
      - email (EmailField): User's email address. Made unique and required
                         for authentication purposes.
      - is_instructor (BooleanField): Flag indicating if user can create courses.
                                    Default is False (regular student).
      - phone (CharField): Optional phone number for contact purposes.
  Notes:
      - Email is set to unique=True to prevent duplicate accounts
      - This model must be referenced in settings.py as AUTH_USER_MODEL
      - Multiple inheritance: AbstractUser provides auth functionality,
        TimeStampedModel provides timestamps
  """

  email = models.EmailField(
    _('email_address'),
    unique=True,
    error_messages={
      'unique': _("A user with that email already exists."),
    },
    help_text=('Required. Used for login and notifications.')
  )

  is_instructor = models.BooleanField(
    _('instructor status'),
    default=False,
    help_text=('Designates whether the user can create and manage courses.')
  )

  phone = models.CharField(
    _('phone_number'),
    max_length=20,
    blank=True,
    null=True,
    help_text=('Optional contact phone number.')
  )

  USERNAME_FIELD = 'email'
  REQUIRED_FIELDS = ['username']


  class Meta:
      verbose_name = _('user')
      verbose_name_plural = _('users')
      ordering = ['-date_joined']  # Newest users first
  
  def __str__(self):
      """String representation of the user."""
      return self.email or self.username
  
  def get_full_name(self):
      """
      Return the user's full name (first_name + last_name).
      Falls back to username if names are not set.
      """
      full_name = f"{self.first_name} {self.last_name}".strip()
      return full_name or self.username
  
  def get_short_name(self):
      """Return the user's first name or username."""
      return self.first_name or self.username
  
  @property
  def bio(self):
    """Shortcut to profile bio."""
    return getattr(self.profile, 'bio', '')
    
  @property
  def avatar(self):
      """Shortcut to profile avatar."""
      return getattr(self.profile, 'avatar', None)
  
class Profile(TimeStampedModel):
    """
    Extended profile information for users.
    
    This model stores additional information about users that is not
    directly related to authentication. It has a one-to-one relationship
    with the User model, meaning each user has exactly one profile.
    
    Attributes:
        - user (OneToOneField): Reference to the User model. When a user is
        deleted, their profile is also deleted (CASCADE).
        - bio (TextField): User's biography or description. Optional.
        - avatar (ImageField): Profile picture. Optional. Uploaded to 'avatars/' folder.
        - birth_date (DateField): User's date of birth. Optional.
        - website (URLField): User's personal website or portfolio. Optional.
        - linkedin (URLField): LinkedIn profile URL. Optional.
        - github (URLField): GitHub profile URL. Optional.

    Notes:
        - Use Django signals (post_save) to auto-create profiles when users are created
        - Avatar uploads require Pillow library (already in requirements.txt)
        - Consider using django-storages for cloud storage (S3) in production    
    """

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE, 
        related_name='profile', # allows access to profile through user
        verbose_name=_('user'),
        help_text=_('User associated with this profile')
    )

    bio = models.TextField(
        _('biography'),
        max_length=500,
        blank=True,
        help_text=_('Brief description about yourself.')
    )

    avatar = models.ImageField(
        _('avatar'),
        upload_to='avatars/',
        blank=True,
        null=True,
        help_text=_('Profile picture (recommended: 400x400px).')
    )

    birth_date = models.DateField(
        _('birth date'),
        blank=True,
        null=True,
        help_text=_('Your date of birth.')
    )

    # Social media links
    website = models.URLField(
        _('website'),
        max_length= 200,
        blank=True,
        help_text=_('Your personal website or portfolio.')
    )

    linkedin = models.URLField(
        _('Linkedin'),
        max_length= 200,
        blank=True,
        help_text=_('Linkedin profile URL.')
    )

    instagram = models.URLField(
        _('instagram'),
        max_length= 200,
        blank=True,
        help_text=_('Instagram profile URL.')
    )

    class Meta:
        verbose_name = _('profile')
        verbose_name_plural = _('profiles')
    
    def __str__(self):
        return f"Profile of {self.user.get_full_name()}"