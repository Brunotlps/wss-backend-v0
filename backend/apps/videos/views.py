"""
Video Management Views Module

This module provides API viewsets for managing video and lesson resources within the
educational platform. It serves as the primary interface layer between the video/lesson
models and the REST API, implementing role-based access control, advanced filtering,
and comprehensive CRUD operations for course content management.

Module Overview:
    This module contains two main viewsets:

    1. VideoViewSet: A comprehensive CRUD viewset for managing video files and metadata.
       Provides endpoints for uploading, retrieving, updating, and deleting video resources,
       with instructor-only creation and modification rights.

    2. LessonViewSet: A comprehensive CRUD viewset for managing lesson resources with full
       lifecycle support. Implements role-based access control for staff, instructors, and
       regular users, supporting lesson creation within courses, content organization, and
       curriculum sequencing.

Key Features:
    - Role-based access control through permission classes and queryset filtering
    - Dynamic serializer selection based on action (list, retrieve, create, update)
    - Advanced filtering by course, order, duration, processing status, and more
    - Optimized database queries using select_related and prefetch_related
    - Support for published and draft course visibility through lesson filtering
    - Two-level ownership validation (lesson → course → instructor)
    - Permission enforcement at both viewset and action levels

Integration Points:
    - Complements the video and lesson models by providing API access
    - Works with custom permission classes (IsCourseInstructorOrReadOnly, IsInstructorOrReadOnly)
    - Integrates with LessonFilter and VideoFilter for advanced filtering capabilities
    - Uses multiple serializer classes for different operations (list, detail, create, update)
    - Supports DjangoFilterBackend, SearchFilter, and OrderingFilter for flexible queries

Security & Access Control:
    - Implements role-based visibility: staff see all lessons, instructors see their own and
      published course lessons, regular users and anonymous users see only published course lessons
    - Uses permission classes to enforce authentication requirements and two-level ownership checks
    - Validates user authorization before allowing modifications

Database Optimization:
    - Uses select_related for course, video, and nested instructor foreign keys
    - Queryset filtering is applied at the database level for efficiency
    - Prevents N+1 query problems through strategic relationship loading
"""

from django.db.models import Q

from rest_framework import viewsets
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticatedOrReadOnly

from django_filters.rest_framework import DjangoFilterBackend

from .filters import LessonFilter, VideoFilter
from .models import Lesson, Video
from .permissions import (
    IsCourseInstructorOrReadOnly,
    IsEnrolled,
    IsInstructorOrReadOnly,
)
from .serializers import (
    LessonCreateSerializer,
    LessonDetailSerializer,
    LessonListSerializer,
    LessonUpdateSerializer,
    VideoListSerializer,
    VideoSerializer,
)


class VideoViewSet(viewsets.ModelViewSet):
    """
    Comprehensive CRUD viewset for managing video resources and metadata.

    This viewset provides a complete REST API interface for video file uploads, retrieval,
    updates, and deletion within the educational platform. It implements role-based access
    control ensuring that only authenticated instructors can create or modify video resources,
    while maintaining read-only access for all users.

    Business Rules:
        - Anyone can view video listings and details (public access)
        - Only instructors can upload/create new video resources
        - Only instructors can modify or delete their own video resources
        - Video metadata includes title, duration, file size, processing status, and more

    Access Control:
        - IsAuthenticatedOrReadOnly: Enforces authentication for write operations (POST, PUT, PATCH, DELETE)
        - IsInstructorOrReadOnly: Restricts video creation and modification to instructors only

    Features:
        - Advanced filtering by course, processing status, duration, and file size
        - Search capabilities across video titles
        - Ordering by creation date, file size, and duration
        - Dynamic serializer selection (list vs detail views)
        - Optimized database queries through efficient queryset management
        - Supports video processing status tracking for asynchronous uploads

    Integration Points:
        - Works with Video model for data persistence
        - Uses VideoSerializer and VideoListSerializer for different operations
        - Integrates with VideoFilter for advanced filtering capabilities
        - Complements LessonViewSet by providing video resources for lessons
        - Uses DjangoFilterBackend, SearchFilter, and OrderingFilter for flexible queries

    Usage:
        GET /api/videos/                    # List all public videos
        GET /api/videos/{id}/               # Retrieve video details
        POST /api/videos/                   # Create new video (instructor only)
        PUT /api/videos/{id}/               # Update video (instructor only)
        PATCH /api/videos/{id}/             # Partial update video (instructor only)
        DELETE /api/videos/{id}/            # Delete video (instructor only)

    Attributes:
        queryset: All Video objects from database
        permission_classes: Requires authentication for write operations; write access restricted to instructors
        filter_backends: DjangoFilterBackend, SearchFilter, OrderingFilter
        filterset_class: VideoFilter for advanced filtering
        search_fields: ['title'] for keyword search
        ordering_fields: ['created_at', 'file_size', 'duration']
        ordering: Default ordering by creation date (newest first)

    Methods:
        get_serializer_class: Returns appropriate serializer based on action (list vs detail)
    """

    queryset = Video.objects.all()
    permission_classes = [IsAuthenticatedOrReadOnly, IsInstructorOrReadOnly]

    # Filtering & Search
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = VideoFilter
    search_fields = ["title"]
    ordering_fields = ["created_at", "file_size", "duration"]
    ordering = ["-created_at"]

    def get_serializer_class(self):

        if self.action == "list":
            return VideoListSerializer
        return VideoSerializer


class LessonViewSet(viewsets.ModelViewSet):
    """
    Comprehensive CRUD viewset for managing lesson resources within course curricula.

    This viewset provides a complete REST API interface for lesson creation, retrieval,
    updates, and deletion within the educational platform. It implements role-based access
    control with two-level ownership validation (lesson → course → instructor) and supports
    filtering for course-aware content organization and visibility management.

    Business Rules:
        - Staff members can view and manage all lessons across all courses (admin mode)
        - Instructors can view their own course lessons and lessons from published courses
        - Instructors can only create/modify/delete lessons in their own courses
        - Regular users and anonymous users can only view lessons from published courses
        - Lessons support ordering within a course for curriculum sequencing
        - Lessons can be filtered by course, status, duration, and other metadata

    Access Control:
        - IsAuthenticatedOrReadOnly: Enforces authentication for write operations (POST, PUT, PATCH, DELETE)
        - IsCourseInstructorOrReadOnly: Restricts lesson creation and modification to course instructors only
        - Two-level ownership check: validates lesson.course.instructor == user before modifications

    Features:
        - Role-based visibility: Staff see all lessons, instructors see their own and published course lessons,
          regular users see only published course lessons
        - Advanced filtering by course, order, duration, processing status, and more
        - Search capabilities across lesson titles and descriptions
        - Ordering by lesson sequence, duration, and creation date
        - Dynamic serializer selection based on action (list, retrieve, create, update)
        - Optimized database queries using select_related for course, video, and instructor relationships
        - Support for published and draft course visibility through queryset filtering

    Integration Points:
        - Works with Lesson model for data persistence
        - Complements VideoViewSet by providing video assignment to lessons
        - Uses multiple serializer classes: LessonListSerializer, LessonDetailSerializer,
          LessonCreateSerializer, and LessonUpdateSerializer for different operations
        - Integrates with LessonFilter for advanced filtering capabilities
        - Uses DjangoFilterBackend, SearchFilter, and OrderingFilter for flexible queries
        - Enforces course-level permissions through IsCourseInstructorOrReadOnly class

    Database Optimization:
        - Uses select_related for course, video, and course_instructor foreign keys to prevent N+1 queries
        - Queryset filtering is applied at the database level through get_queryset() for efficiency
        - Strategic relationship loading optimizes complex multi-level permission checks

    Usage:
        GET /api/lessons/                    # List lessons (filtered by user role and published status)
        GET /api/lessons/{id}/               # Retrieve lesson details
        POST /api/lessons/                   # Create new lesson in course (instructor only)
        PUT /api/lessons/{id}/               # Update lesson (instructor only)
        PATCH /api/lessons/{id}/             # Partial update lesson (instructor only)
        DELETE /api/lessons/{id}/            # Delete lesson (instructor only)

    Attributes:
        queryset: Lesson objects with select_related optimization for course, video, and instructor
        permission_classes: Requires authentication for write operations; enforces two-level ownership
        filter_backends: DjangoFilterBackend, SearchFilter, OrderingFilter
        filterset_class: LessonFilter for advanced filtering by course and other criteria
        search_fields: ['title', 'description'] for keyword search
        ordering_fields: ['order', 'duration', 'created_at']
        ordering: Default ordering by course and lesson order (curriculum sequence)

    Methods:
        get_serializer_class: Returns appropriate serializer based on action (list, retrieve, create, update)
        get_queryset: Applies role-based filtering to ensure users only see lessons they have access to
    """

    # Query optimization : Load related course, video, and nested instructor in single query
    queryset = Lesson.objects.select_related("course", "video", "course__instructor")
    permission_classes = [
        IsAuthenticatedOrReadOnly,
        IsEnrolled,
        IsCourseInstructorOrReadOnly,
    ]

    # Filtering & Search
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = LessonFilter
    search_fields = ["title", "description"]
    ordering_fields = ["order", "duration", "created_at"]
    ordering = ["course", "order"]

    def get_serializer_class(self):

        if self.action == "list":
            return LessonListSerializer
        elif self.action == "retrieve":
            return LessonDetailSerializer
        elif self.action == "create":
            return LessonCreateSerializer
        elif self.action in ["update", "partial_update"]:
            return LessonUpdateSerializer
        return LessonDetailSerializer

    def get_queryset(self):

        queryset = super().get_queryset()
        user = self.request.user

        # Staff can see all lessons from all courses (admin mode)
        if user.is_authenticated and user.is_staff:
            return queryset

        # Instructors see lessons from own courses + lessons from published courses
        # Uses Q objects for OR logic: (course.instructor=user OR course.is_published=True)
        if user.is_authenticated and user.is_instructor:
            return queryset.filter(
                Q(course__instructor=user) | Q(course__is_published=True)
            ).distinct()

        # Anonymous and regular users see only lessons from published courses
        return queryset.filter(course__is_published=True)
