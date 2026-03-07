"""
Enrollments Views Module.

This module defines the API views for managing course enrollments and lesson progress tracking.
It provides RESTful endpoints for creating, retrieving, updating, and deleting enrollment records
and tracking student progress through course lessons.

Key Components:
    - EnrollmentViewSet: Handles CRUD operations for user course enrollments with role-based access control.
      Supports filtering, searching, and ordering by course, enrollment date, completion status, and ratings.
    - LessonProgressViewSet: Manages individual lesson progress tracking for enrolled students.
      Allows tracking of watched duration and progress through course lessons with role-based visibility.

Integration:
    - Works with the Course and User models to establish enrollment relationships.
    - Uses DjangoFilterBackend for advanced filtering based on EnrollmentFilter and LessonProgressFilter.
    - Implements custom permission classes (IsEnrollmentOwner, IsEnrolledOrInstructor) to ensure
      data access control based on user roles (student, instructor, staff).
    - Serializes data using EnrollmentListSerializer, EnrollmentDetailSerializer, and LessonProgressSerializer
      for appropriate API responses.
    - Integrates with authentication system to enforce user-based data isolation and role-specific queryset filtering.
"""

from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.db.models import Q

from .models import Enrollment, LessonProgress
from .serializers import (
    EnrollmentListSerializer,
    EnrollmentDetailSerializer,
    LessonProgressListSerializer,
    LessonProgressSerializer,
)
from .permissions import IsEnrollmentOwner, IsEnrolledOrInstructor
from .filters import EnrollmentFilter, LessonProgressFilter

class EnrollmentViewSet(viewsets.ModelViewSet):
    """
    API ViewSet for managing user course enrollments.
    
    Provides RESTful CRUD operations for enrollment records with comprehensive role-based access control.
    Instructors can view their own enrollments and enrollments in their courses, while staff members
    have access to all enrollment data. Supports advanced filtering, searching, and ordering capabilities
    to facilitate enrollment management and analytics.
    
    This class is crucial to the enrollment management system as it:
    - Establishes the relationship between users and courses through enrollment records
    - Enforces role-based data isolation to ensure users only access authorized enrollments
    - Provides filtering and search capabilities for instructors and administrators to manage course enrollments
    - Tracks enrollment lifecycle including enrollment date, completion status, and student ratings
    - Auto-populates the requesting user as the enrollment owner on creation
    
    Integration Points:
    - Serializers: Uses EnrollmentListSerializer for list views and EnrollmentDetailSerializer for detail operations
    - Permissions: Enforces IsAuthenticated and IsEnrollmentOwner to control access
    - Filters: Implements EnrollmentFilter for advanced filtering by course, status, and date ranges
    - Database: Optimizes queries using select_related() for user and course data, and prefetch_related() for lesson progress
    - Authentication: Integrates with Django's authentication system to enforce user-based data isolation
    
    Attributes:
        queryset: Optimized query with related user and course data plus lesson progress tracking
        permission_classes: Requires authentication and ownership/role-based permissions
        filter_backends: Supports filtering, searching, and ordering
        filterset_class: EnrollmentFilter for advanced filtering options
        search_fields: Searchable fields including course title and student reviews
        ordering_fields: Sortable fields for enrollment date, completion date, and ratings
        ordering: Default ordering by most recent enrollments first
    """

    queryset = Enrollment.objects.select_related('user', 'course').prefetch_related('lesson_progress')
    permission_classes = [IsAuthenticated, IsEnrollmentOwner]

    # Filtering & Search
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = EnrollmentFilter
    search_fields = ['course__title', 'review']
    ordering_fields = ['enrolled_at', 'completed_at', 'rating']
    ordering = ['-enrolled_at']

    def get_serializer_class(self):
        if self.action == 'list':
            return EnrollmentListSerializer
        return EnrollmentDetailSerializer
    
    def get_queryset(self):
        
        user = self.request.user
        queryset = self.queryset

        if user.is_staff:
            return queryset

        if user.is_instructor:
            return queryset.filter(Q(user=user) | Q(course__instructor=user))

        return queryset.filter(user=user) 
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class LessonProgressViewSet(viewsets.ModelViewSet):
    """
    API ViewSet for managing individual lesson progress tracking within course enrollments.
    
    Enables students and instructors to track progress through course lessons, including watched duration
    and last access timestamps. Provides role-based visibility where students see only their own progress,
    instructors see progress for their courses, and staff have full access. Supports filtering and ordering
    to facilitate progress monitoring and course analytics.
    
    This class is essential for the learning experience as it:
    - Tracks student progress through individual lessons within enrolled courses
    - Records watched duration to monitor content consumption and time spent
    - Maintains timestamps for last access to determine engagement patterns
    - Enforces role-based visibility ensuring students can only view their own progress
    - Enables instructors to monitor student progress in their courses
    - Provides data for completion tracking and course analytics
    
    Integration Points:
    - Serializer: Uses LessonProgressSerializer for all API responses (list and detail views)
    - Permissions: Enforces IsAuthenticated and IsEnrolledOrInstructor to control progress visibility
    - Filters: Implements LessonProgressFilter for advanced filtering by lesson and enrollment
    - Database: Optimizes queries using select_related() for enrollment, user, course, and lesson data
    - Parent Model: Works in conjunction with Enrollment to track progress within enrollment contexts
    - Authentication: Integrates with user authentication to provide personalized progress tracking
    
    Attributes:
        queryset: Optimized query with related enrollment, user, course, and lesson data
        permission_classes: Requires authentication and enrollment/instructor-based permissions
        filter_backends: Supports filtering and ordering capabilities
        filterset_class: LessonProgressFilter for advanced filtering options
        ordering_fields: Sortable fields for lesson order, watched duration, and last access timestamp
        ordering: Default ordering by lesson sequence
        serializer_class: LessonProgressSerializer for all API responses
    """
    
    queryset = LessonProgress.objects.select_related(
        'enrollment',            
        'enrollment__user',        
        'enrollment__course',      
        'lesson'                 
    )
    
    permission_classes = [IsAuthenticated, IsEnrolledOrInstructor]
    
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = LessonProgressFilter
    ordering_fields = ['lesson__order', 'watched_duration', 'last_watched_at']
    ordering = ['lesson__order']
    
    serializer_class = LessonProgressSerializer
    
    def get_queryset(self):

        user = self.request.user
        queryset = self.queryset
        
        if user.is_staff:
            return queryset
        
        if user.is_instructor:
            return queryset.filter(Q(enrollment__user=user) | Q(enrollment__course__instructor=user))
        
        return queryset.filter(enrollment__user=user)

