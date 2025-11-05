"""
Core models module for WSS Backend.

This module contains abstract base models that provide common functionality
to be inherited by other models throughout the application.

Abstract models don't create database tables themselves, but their fields
and methods are inherited by concrete models that do create tables.
"""

from django.db import models


class TimeStampedModel(models.Model):
  """
    Abstract base model that provides self-updating 'created_at' and 'updated_at' fields.
    
    This model serves as a base class for other models in the application that need
    automatic timestamp tracking. By inheriting from this model, other models
    automatically get creation and modification timestamps without code duplication.
    
    Attributes:
        created_at (DateTimeField): Automatically set when the object is first created.
                                     This field is never updated after creation.
        updated_at (DateTimeField): Automatically updated whenever the object is saved.
                                     This field is updated every time save() is called.
    Notes:
    - This is an abstract model (Meta.abstract = True), so Django won't
      create a database table for it.
    - The fields are automatically managed by Django; you don't need to
      manually set them.
    - auto_now_add: Sets the field to now when the object is first created.
    - auto_now: Sets the field to now every time the object is saved.
  """

  created_at = models.DateTimeField(
    auto_now_add=True,
    verbose_name="Created at",
    help_text="Timestamp when this object was created"
  )

  updated_at = models.DateTimeField(
    auto_now=True,
    verbose_name="Updated at",
    help_text="Timestamp when this object last updated"
  )

  class Meta:
    abstract = True # This makes it an abstract base class
    ordering = ['-created_at']