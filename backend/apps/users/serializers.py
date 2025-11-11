"""
Serializers for User authentication and profile management.

This module contains serializers for:
- User registration and authentication
- Profile management
- User data serialization for API responses

All serializers include proper validation and follow DRF best practices.
"""


from rest_framework import serializers
from django.contrib.auth import authenticate 
from django.contrib.auth.password_validation import validate_password

from .models import User, Profile

class UserRegistrationSerializer(serializers.ModelSerializer):
  """
  Serializer for user registration.
  
  Handles new user creation with password validation and automatic
  profile creation via signals. 
  """

  password = serializers.CharField(
    write_only=True,
    validators=[validate_password],
    help_text="Password must meet Django's validation requirements"
  )

  password_confirm = serializers.CharField(
    write_only=True,
    help_text="Must match password field"
  )

  class Meta:
    model=User
    fields=[
      'email', 'username', 'password', 'password_confirm',
      'first_name', 'last_name', 'phone', 'is_instructor'      
    ]
    extra_kwargs={
      'email': {'required': True},
      'username': {'required': True},    
    }

  def validate(self, data):

    if data['password'] != data['password_confirm']:
      raise serializers.ValidationError("Password does not match.")
    return data
  
  def create(self, validated_data):
    validated_data.pop('password_confirm')
    password=validated_data.pop('password')

    user=User(**validated_data)
    user.set_password(password) # Hash password
    user.save()

    return user

class ProfileSerializer(serializers.ModelSerializer):
  """Serializer for user profile information"""

  class Meta:
    model=Profile
    fields=[
      'bio', 'avatar', 'birth_date', 'website', 
      'linkedin', 'instagram', 'created_at', 'updated_at'
    ]
    read_only_fields=['created_at', 'updated_at']

class UserDetailSerializer(serializers.ModelSerializer):
  """
  Detailed user serializer for authenticated requests.
  
  Includes nested profile information and computed fields.
  """

  profile=ProfileSerializer(read_only=True)
  full_name=serializers.CharField(source='get_full_name', read_only=True)
  
  class Meta:
    model=User
    fields=[
      'id', 'email', 'username', 'first_name', 'last_name',
      'phone', 'is_instructor', 'full_name', 'profile',
      'date_joined', 'last_login'      
    ]
    read_only_fields=['id', 'date_joined', 'last_login', 'created_at', 'updated_at']

class UserUpdateSerializer(serializers.ModelSerializer):
  """Serializer for updating user informations."""

  class Meta:
    model=User
    fields=[
      'first_name', 'last_name', 'phone', 'is_instructor'
    ]

  def validate_is_instructor(self,  value):
    
    if not value and self.instance.is_instructor:
      raise serializers.ValidationError(
        "Cannot demote from instructor status. Contact admin."
      )
    return value

class UserListSerializer(serializers.ModelSerializer):
  """Minimal user serializer for list views."""
  
  full_name = serializers.CharField(source='get_full_name', read_only=True)
  
  class Meta:
      model = User
      fields = ['id', 'email', 'username', 'full_name', 'is_instructor']