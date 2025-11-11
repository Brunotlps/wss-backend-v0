"""
Serializers for Course and Category management.

This module contains serializers for:
- Category CRUD operations
- Course management with different levels of detail
- Nested relationships with User (instructor) and Category
- Business logic validation for course creation

All serializers include proper validation and optimization.
"""

from rest_framework import serializers
from django.utils.text import slugify
from django.db import transaction

from .models import Category, Course
from apps.users.serializers import UserListSerializer


class CategorySerializer(serializers.ModelSerializer):
    """
    Serializer for Category CRUD operations.
    
    Handles automatic slug generation from name if not provided.
    """
    
    class Meta:
        model = Category
        fields = [
            'id', 'name', 'slug', 'description', 'is_active', 
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
        extra_kwargs = {
            'slug': {'required': False},  # Optional, auto-generated if empty
        }
    
    def create(self, validated_data):
        """Auto-generate slug from name if not provided."""
        if not validated_data.get('slug'):
            validated_data['slug'] = slugify(validated_data['name'])
        return super().create(validated_data)
    
    def update(self, instance, validated_data):
        """Update slug if name changed and slug not provided."""
        if 'name' in validated_data and not validated_data.get('slug'):
            validated_data['slug'] = slugify(validated_data['name'])
        return super().update(instance, validated_data)


class CategoryListSerializer(serializers.ModelSerializer):
    """
    Minimal category serializer for list views and nested relationships.
    """
    
    class Meta:
        model = Category
        fields = ['id', 'name', 'slug']


class CourseListSerializer(serializers.ModelSerializer):
    """
    Minimal course serializer for list views.
    
    Includes basic information and computed fields for performance.
    """
    instructor_name = serializers.CharField(source='instructor.get_full_name', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)
    enrolled_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Course
        fields = [
            'id', 'title', 'slug', 'thumbnail', 'price', 'difficulty',
            'duration_hours', 'is_published', 'instructor_name', 
            'category_name', 'enrolled_count', 'created_at'
        ]
    
    def get_enrolled_count(self, obj):
        """Return number of active enrollments."""
        return obj.enrollments.filter(is_active=True).count()


class CourseDetailSerializer(serializers.ModelSerializer):
    """
    Detailed course serializer for single course views.
    
    Includes nested relationships and computed fields.
    """
    instructor = UserListSerializer(read_only=True)
    category = CategoryListSerializer(read_only=True)
    enrolled_count = serializers.SerializerMethodField()
    is_enrolled = serializers.SerializerMethodField()
    lessons_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Course
        fields = [
            'id', 'title', 'slug', 'description', 'instructor', 'category',
            'thumbnail', 'price', 'difficulty', 'is_published',
            'duration_hours', 'what_you_will_learn', 'requirements',
            'enrolled_count', 'is_enrolled', 'lessons_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_enrolled_count(self, obj):
        """Return number of active enrollments."""
        return obj.enrollments.filter(is_active=True).count()
    
    def get_is_enrolled(self, obj):
        """Check if current user is enrolled in this course."""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.enrollments.filter(
                user=request.user, 
                is_active=True
            ).exists()
        return False
    
    def get_lessons_count(self, obj):
        """Return total number of lessons in this course."""
        return obj.lessons.count()


class CourseCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating new courses.
    
    Includes business logic validation and automatic field population.
    """
    
    class Meta:
        model = Course
        fields = [
            'title', 'slug', 'description', 'category', 'thumbnail',
            'price', 'difficulty', 'duration_hours', 'what_you_will_learn',
            'requirements'
        ]
        extra_kwargs = {
            'slug': {'required': False},
        }
    
    def validate_category(self, value):
        """Ensure category is active."""
        if not value.is_active:
            raise serializers.ValidationError(
                "Cannot create course in inactive category."
            )
        return value
    
    def create(self, validated_data):
        """Create course with automatic instructor assignment."""
        request = self.context['request']
        
        if not request.user.is_instructor:
            raise serializers.ValidationError(
                "Only instructors can create courses. Please upgrade your account."
            )
        
        validated_data['instructor'] = request.user
        
        if not validated_data.get('slug'):
            validated_data['slug'] = slugify(validated_data['title'])
        
        return super().create(validated_data)


class CourseUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating existing courses.
    
    Only course owners (instructors) can update their courses.
    """
    
    class Meta:
        model = Course
        fields = [
            'title', 'slug', 'description', 'category', 'thumbnail',
            'price', 'difficulty', 'duration_hours', 'what_you_will_learn',
            'requirements', 'is_published'
        ]
        extra_kwargs = {
            'slug': {'required': False},
        }
    
    def validate_category(self, value):
        """Ensure category is active."""
        if not value.is_active:
            raise serializers.ValidationError(
                "Cannot assign course to inactive category."
            )
        return value
    
    def validate(self, data):
        """Business logic validation."""
        request = self.context['request']
        
        # Only course instructor can update
        if self.instance.instructor != request.user:
            raise serializers.ValidationError(
                "Only the course instructor can update this course."
            )
        
        return data
    
    def update(self, instance, validated_data):
        """Update slug if title changed and slug not provided."""
        if 'title' in validated_data and not validated_data.get('slug'):
            validated_data['slug'] = slugify(validated_data['title'])
        
        return super().update(instance, validated_data)