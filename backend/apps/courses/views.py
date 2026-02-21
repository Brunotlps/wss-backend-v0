"""
Course Management Views Module

This module provides API viewsets for managing course resources and category data within the 
educational platform. It serves as the primary interface layer between the course models and 
the REST API, implementing role-based access control, advanced filtering, and comprehensive 
CRUD operations for course lifecycle management.

Module Overview:
    This module contains two main viewsets:
    
    1. CategoryViewSet: A read-only viewset for managing and retrieving active course categories.
       Provides endpoints for listing and retrieving category details, supporting course 
       organization and discovery features throughout the platform.
    
    2. CourseViewSet: A comprehensive CRUD viewset for managing course resources with full 
       lifecycle support. Implements role-based access control for staff, instructors, and 
       regular users, supporting course creation, publishing, updating, and deletion operations.

Key Features:
    - Role-based access control through permission classes and queryset filtering
    - Dynamic serializer selection based on action (list, retrieve, create, update)
    - Advanced filtering by category, level, price range, and search terms
    - Optimized database queries using select_related and prefetch_related
    - Dedicated lessons endpoint for accessing course curriculum
    - Support for published and draft course states with visibility rules
    - Permission enforcement at both viewset and action levels

Integration Points:
    - Complements the course models (Category, Course) by providing API access
    - Works with custom permission classes (IsInstructorOrReadOnly, IsCourseOwnerOrReadOnly)
    - Integrates with CourseFilter for advanced filtering capabilities
    - Uses multiple serializer classes for different operations (list, detail, create, update)
    - Leverages LessonListSerializer from the videos app for curriculum management
    - Supports DjangoFilterBackend, SearchFilter, and OrderingFilter for flexible queries

Security & Access Control:
    - Implements role-based visibility: staff see all courses, instructors see their own and 
      published courses, regular users and anonymous users see only published courses
    - Uses permission classes to enforce authentication requirements and ownership checks
    - Validates user authorization before allowing modifications

Database Optimization:
    - Uses select_related for instructor and category foreign keys
    - Uses prefetch_related for lessons to avoid N+1 query problems
    - Queryset filtering is applied at the database level for efficiency
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticatedOrReadOnly
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from .models import Category, Course
from .serializers import (
    CategorySerializer,
    CourseListSerializer,
    CourseDetailSerializer,
    CourseCreateSerializer,
    CourseUpdateSerializer,
)
from .permissions import IsInstructorOrReadOnly, IsCourseOwnerOrReadOnly
from .filters import CourseFilter
from apps.videos.serializers import LessonListSerializer


class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    A read-only viewset for managing course categories.
    
    This viewset provides API endpoints for retrieving active course categories
    throughout the platform. It allows authenticated and unauthenticated users
    to access category listings and details, supporting course organization,
    filtering, and discovery features. Categories are essential for structuring
    the course catalog and enhancing user navigation experiences.
    
    Attributes:
        queryset: Filters only active categories from the database.
        serializer_class: Serializes category data for API responses.
        permission_classes: Allows public access to category endpoints.
        ordering: Orders categories by name in ascending order.
    Endpoints:
        GET /api/categories/        - List all active categories
        GET /api/categories/{id}/   - Retrieve specific category details
    
    Response Format:
        {
            "id": 1,
            "name": "Web Development",
            "slug": "web-development",
            "description": "Learn web development from basics to advanced",
            "is_active": true,
            "created_at": "2026-01-15T10:30:00Z",
            "updated_at": "2026-01-15T10:30:00Z"
        }
    """

    queryset = Category.objects.filter(is_active=True)
    serializer_class = CategorySerializer
    permission_classes = [AllowAny]

    ordering = ['name']

class CourseViewSet(viewsets.ModelViewSet):
    """
    A comprehensive viewset for managing course resources and operations.
    
    This viewset provides full CRUD functionality for course management, enabling instructors to create,
    retrieve, update, and delete courses while allowing students and anonymous users to browse published
    courses. It implements role-based access control through permission classes and queryset filtering,
    ensuring users only access courses appropriate to their authorization level. The viewset complements
    the project's educational platform by orchestrating course lifecycle management, content organization,
    and curriculum delivery.
    
    Key Features:
        - Role-based access control for staff, instructors, and regular users
        - Dynamic serializer selection based on requested action (list, retrieve, create, update)
        - Advanced filtering by category, level, price range, and search terms
        - Optimized database queries using select_related and prefetch_related
        - Dedicated lessons endpoint for accessing course curriculum
        - Support for published and draft course states with visibility rules
    
    Attributes:
        queryset: All course objects with optimized related object loading.
        permission_classes: Implements authentication and authorization checks.
        filter_backends: Enables filtering, searching, and ordering capabilities.
        filterset_class: Defines custom filtering logic via CourseFilter.
        search_fields: Fields searchable by keyword: title, description, learning outcomes.
        ordering_fields: Fields that support result ordering.
        ordering: Default ordering by creation date (newest first).
    
    Endpoints:
        GET /api/courses/                      - List courses (filtered by user role and visibility)
        POST /api/courses/                     - Create a new course (instructors only)
        GET /api/courses/{id}/                 - Retrieve course details
        PUT /api/courses/{id}/                 - Update entire course (owner only)
        PATCH /api/courses/{id}/               - Partially update course (owner only)
        DELETE /api/courses/{id}/              - Delete course (owner only)
        GET /api/courses/{id}/lessons/         - List all lessons in a course
    
    Response Format (Example):
        {
            "id": 1,
            "title": "Advanced Python Development",
            "slug": "advanced-python-development",
            "description": "Master advanced Python concepts",
            "what_you_will_learn": "Learn decorators, async programming, and design patterns",
            "instructor": {
                "id": 1,
                "username": "instructor_name",
                "email": "instructor@example.com"
            },
            "category": {
                "id": 2,
                "name": "Programming",
                "slug": "programming"
            },
            "price": 99.99,
            "level": "advanced",
            "is_published": true,
            "created_at": "2026-01-15T10:30:00Z",
            "updated_at": "2026-01-15T10:30:00Z"
        }
    
    Permissions:
        - IsAuthenticatedOrReadOnly: Requires authentication for modifications.
        - IsInstructorOrReadOnly: Only instructors can create courses.
        - IsCourseOwnerOrReadOnly: Only course owners can modify their courses.
    
    Filtering & Search:
        - Filter by category, level, price range using CourseFilter
        - Search across title, description, and learning outcomes
        - Order by creation date, price, or title
    """

    queryset = Course.objects.select_related('instructor', 'category').prefetch_related('lessons')
    permission_classes = [IsAuthenticatedOrReadOnly, IsInstructorOrReadOnly, IsCourseOwnerOrReadOnly]

    # Filtering & Search 
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = CourseFilter
    search_fields = ['title', 'description', 'what_you_will_learn']
    ordering_fields = ['created_at', 'price', 'title']
    ordering = ['-created_at']

    def get_serializer_class(self):
        if self.action == 'list':
            return CourseListSerializer
        elif self.action == 'retrieve':
            return CourseDetailSerializer
        elif self.action == 'create':
            return CourseCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return CourseUpdateSerializer
        return CourseDetailSerializer
    
    def get_queryset(self):
        """
        Filter courses based on user authentication status and role permissions.
        
        This method implements role-based course visibility logic to ensure users only
        access courses appropriate to their authorization level. It complements the project's
        permission system by providing queryset-level filtering that works in conjunction with
        IsAuthenticatedOrReadOnly, IsInstructorOrReadOnly, and IsCourseOwnerOrReadOnly permission
        classes. This approach enables efficient database queries and consistent access control
        across all course endpoints.
        
        The filtering hierarchy is:
        - Staff users: Access all courses (admin mode)
        - Instructors: Access their own courses and all published courses
        - Authenticated regular users: Access only published courses
        - Anonymous users: Access only published courses
        
        Args:
            self: The viewset instance containing request and user context.
        
        Returns:
            QuerySet: A filtered Course queryset containing only courses the user is authorized to access,
                      with optimized queries using select_related and prefetch_related.
        
        Response Format:
            Courses are returned with the following structure based on the active serializer:
            {
                "id": 1,
                "title": "Advanced Python Development",
                "slug": "advanced-python-development",
                "description": "Master advanced Python concepts",
                "instructor": {
                    "id": 1,
                    "username": "instructor_name",
                    "email": "instructor@example.com"
                },
                "category": {
                    "id": 2,
                    "name": "Programming",
                    "slug": "programming"
                },
                "price": 99.99,
                "is_published": true,
                "created_at": "2026-01-15T10:30:00Z",
                "updated_at": "2026-01-15T10:30:00Z"
            }
        """
        
        queryset = super().get_queryset()
        user = self.request.user

        # Staff can see all courses (admin mode)
        if user.is_authenticated and user.is_staff:
            return queryset
        
        # Instructors see own courses + published courses
        if user.is_authenticated and user.is_instructor:
            from django.db.models import Q

            return queryset.filter(Q(instructor=user) | Q(is_published=True)).distinct()
        
        # Anonymous and regular users see only published courses
        return queryset.filter(is_published=True)
    
    @action(detail=True, methods=['get'], permission_classes=[AllowAny])
    def lessons(self, request, pk=None):
        """
        Retrieve all lessons associated with a specific course.
        
        Endpoint: GET /api/courses/{id}/lessons/
        
        This action provides a dedicated endpoint for fetching lessons from a course,
        allowing users to access course curriculum structure and lesson organization.
        It complements the CourseViewSet by enabling granular lesson retrieval without
        requiring full course details, supporting client-side lesson navigation and
        course content display functionality.
        
        Args:
            request (HttpRequest): The HTTP request object containing user context.
            pk (int, optional): The primary key of the course. Defaults to None.
        
        Returns:
            Response: A Response object containing serialized lesson data with HTTP 200 status.
        
        Response Format:
            [
                {
                    "id": 1,
                    "title": "Introduction to Web Development",
                    "description": "Learn the basics of web development",
                    "order": 1,
                    "duration": 3600,
                    "video_url": "https://example.com/video1.mp4",
                    "created_at": "2026-01-15T10:30:00Z",
                    "updated_at": "2026-01-15T10:30:00Z"
                },
                {
                    "id": 2,
                    "title": "HTML Fundamentals",
                    "description": "Master HTML structure and semantics",
                    "order": 2,
                    "duration": 5400,
                    "video_url": "https://example.com/video2.mp4",
                    "created_at": "2026-01-15T10:35:00Z",
                    "updated_at": "2026-01-15T10:35:00Z"
                }
            ]
        
        Raises:
            Http404: If the course with the given pk does not exist.
        """

        course = self.get_object() # Retrieves course, raises 404 if not found
        lessons = course.lessons.all().order_by('order')
        serializer = LessonListSerializer(lessons, many=True)

        return Response(serializer.data, status=status.HTTP_200_OK)
    

    
    