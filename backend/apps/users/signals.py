"""
Signal handlers for the Users application.

This module contains Django signal handlers that respond to events
in the User model lifecycle, such as creation and updates.

Signals:
    - create_user_profile: Automatically creates a Profile when a User is created
    - save_user_profile: Ensures Profile is saved when User is saved
"""

from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import User, Profile


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """
    Automatically create a Profile when a new User is created.
    
    This signal handler is triggered every time a User object is saved.
    If the User is being created (not updated), a corresponding Profile
    object is automatically created and linked to the User.
    
    Args:
        sender (Model): The model class that sent the signal (User).
        instance (User): The actual User instance being saved.
        created (bool): True if a new record was created, False if updated.
        **kwargs: Additional keyword arguments from the signal.
    
    Example:
        When: user = User.objects.create_user(email='test@example.com', ...)
        Result: A Profile object is automatically created with profile.user = user
    
    Notes:
        - This ensures every User always has a Profile
        - No need to manually create Profile in views or serializers
        - Profile fields default to empty/null as defined in the model
    """
    if created:
        Profile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """
    Ensure the User's Profile is saved when the User is saved.
    
    This signal handler ensures that if a Profile exists for a User,
    it is saved whenever the User is saved. This helps maintain data
    consistency and can trigger any additional Profile-level logic.
    
    Args:
        sender (Model): The model class that sent the signal (User).
        instance (User): The actual User instance being saved.
        **kwargs: Additional keyword arguments from the signal.
    
    Notes:
        - This only saves existing profiles, doesn't create new ones
        - Uses hasattr() check to avoid errors if Profile doesn't exist
        - Profile creation is handled by create_user_profile signal
    """
    if hasattr(instance, 'profile'):
        instance.profile.save()
