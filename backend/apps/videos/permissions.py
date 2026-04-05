"""
Permissions for the videos module.

This module defines custom permission classes to control access to
video and lesson resources in the system. Permissions ensure that only
authorized users can perform certain operations on lessons and videos,
with special consideration for the two-level ownership relationship
through courses.

Available permissions:
    - IsCourseInstructorOrReadOnly: Only course instructors can create/modify lessons
    - IsInstructorOrReadOnly: Only authenticated instructors can create videos

Key Concepts:
    - Two-level ownership: lesson → course → instructor
    - Lessons belong to courses, and only the course instructor can manage them
    - Videos are initially created by instructors, then associated with lessons

When to use:
    - Import these permission classes in views or viewsets
    - Apply to LessonViewSet and VideoViewSet to enforce business rules
    - Combine with IsAuthenticatedOrReadOnly for comprehensive access control
"""

from rest_framework.permissions import BasePermission, SAFE_METHODS
from django.core.cache import cache
from apps.enrollments.models import Enrollment


class IsCourseInstructorOrReadOnly(BasePermission):
    """
    Custom permission to only allow course instructors to create/modify lessons.
    
    This permission grants read-only access to any request (GET, HEAD, OPTIONS),
    but only allows write permissions (POST, PUT, PATCH, DELETE) to the instructor
    who owns the course that the lesson belongs to.
    
    Business Rule:
        - Anyone can view lessons (public listing, subject to enrollment checks in views)
        - Only the course instructor can create new lessons in their course
        - Only the course instructor can modify/delete lessons in their course
    
    Important Note - Two-Level Ownership:
        Unlike courses (where obj.instructor == user), lessons have two-level lookup:
        lesson.course.instructor == user
        
        This means we need to navigate through the course relationship to check ownership.
        The serializer validates this during creation, but the permission enforces it
        at the API level.
    
    Usage:
        class LessonViewSet(viewsets.ModelViewSet):
            permission_classes = [IsAuthenticatedOrReadOnly, IsCourseInstructorOrReadOnly]
    
    Attributes:
        Inherits from BasePermission
        
    Methods:
        has_permission: VIEW-LEVEL permission check (before object access)
        has_object_permission: OBJECT-LEVEL permission check (after object retrieval)
    """
    
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return request.user and request.user.is_authenticated and request.user.is_instructor
    
    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        return obj.course.instructor == request.user


class IsInstructorOrReadOnly(BasePermission):
    """
    Custom permission to only allow instructors to create videos.
    
    This permission grants read-only access to any request (GET, HEAD, OPTIONS),
    but only allows write permissions (POST, PUT, PATCH, DELETE) to users
    with is_instructor=True.
    
    Business Rule:
        - Anyone can view videos (subject to enrollment checks in views)
        - Only instructors can create new videos
        - Only instructors can modify/delete videos (ownership checked separately)
    
    Note:
        This is identical to apps.courses.permissions.IsInstructorOrReadOnly.
        We redefine it here to avoid cross-app imports and maintain module independence.
        Alternatively, you could import from courses if preferred:
        
        from apps.courses.permissions import IsInstructorOrReadOnly
    
    Usage:
        class VideoViewSet(viewsets.ModelViewSet):
            permission_classes = [IsAuthenticatedOrReadOnly, IsInstructorOrReadOnly]
    
    Attributes:
        Inherits from BasePermission
        
    Methods:
        has_permission: Determines if user can perform the action at view level
    """
    
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return request.user and request.user.is_authenticated and request.user.is_instructor


class IsEnrolled(BasePermission):
    """
    Permission class to restrict lesson/video access to enrolled users.
    
    Access is granted if:
    1. User is the course instructor (bypass enrollment check)
    2. User is admin/staff (full access for moderation)
    3. Lesson is first in course (order=1) - free preview
    4. User has active enrollment in the course
    
    Cache Strategy:
    - Key: f"enrollment:{user_id}:{course_id}"
    - TTL: 15 minutes
    - Invalidated on enrollment save/delete
    
    Usage:
        class LessonViewSet(viewsets.ModelViewSet):
            permission_classes = [IsAuthenticated, IsEnrolled]
    
    Security:
        - Only applies to SAFE_METHODS (GET, HEAD, OPTIONS)
        - Write operations handled by IsCourseInstructorOrReadOnly
        - Provides specific error messages with course name
    """
    
    message = "Você precisa estar matriculado neste curso para acessar este conteúdo."
    
    def has_object_permission(self, request, view, obj):
        """
        Check if user has permission to access this lesson/video.
        
        Args:
            request: HTTP request object
            view: ViewSet handling the request
            obj: Lesson or Video object being accessed
            
        Returns:
            bool: True if access granted, False otherwise
        """
        
        if request.method not in SAFE_METHODS:
            return True
        
        # First lesson is always free (preview/marketing)
        # Check this BEFORE authentication to allow anonymous access
        if hasattr(obj, 'order') and obj.order == 1:
            return True
        
        # Now require authentication for non-free lessons
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Admin/staff bypass enrollment check (for moderation/support)
        if request.user.is_staff or request.user.is_superuser:
            return True
        
        # Determine the course from the object
        # obj can be Lesson (has course FK) or Video (has lesson.course)
        course = self._get_course_from_object(obj)
        if not course:
            # If we can't determine course, deny access (safety)
            return False
        
        # Course instructor can access their own content
        if course.instructor == request.user:
            return True
        
        # Check enrollment (with caching)
        is_enrolled = self._check_enrollment_cached(request.user.id, course.id)
        
        if not is_enrolled:
            # Customize error message with course name
            self.message = f"Você precisa estar matriculado no curso '{course.title}' para acessar este conteúdo."
        
        return is_enrolled
    
    def _get_course_from_object(self, obj):
        """
        Extract course from Lesson or Video object.
        
        Args:
            obj: Lesson or Video instance
            
        Returns:
            Course instance or None
        """
        # Lesson has direct FK to Course
        if hasattr(obj, 'course'):
            return obj.course
        
        # Video has lesson.course
        if hasattr(obj, 'lesson') and obj.lesson:
            return obj.lesson.course
        
        return None
    
    def _check_enrollment_cached(self, user_id, course_id):
        """
        Check if user is enrolled in course (with Redis cache).
        
        Cache key format: enrollment:{user_id}:{course_id}
        TTL: 15 minutes (900 seconds)
        
        Args:
            user_id: User ID
            course_id: Course ID
            
        Returns:
            bool: True if enrolled and active, False otherwise
        """
        cache_key = f"enrollment:{user_id}:{course_id}"
        
        # Try to get from cache first
        cached_result = cache.get(cache_key)
        if cached_result is not None:
            return cached_result
        
        # Cache miss - query database
        is_enrolled = Enrollment.objects.filter(
            user_id=user_id,
            course_id=course_id,
            is_active=True
        ).exists()
        
        # Store in cache for 15 minutes
        cache.set(cache_key, is_enrolled, timeout=900)  # 900 seconds = 15 minutes
        
        return is_enrolled


def invalidate_enrollment_cache(user_id, course_id):
    """
    Invalidate enrollment cache when enrollment changes.
    
    Call this function when:
    - Enrollment is created
    - Enrollment is updated (is_active changed)
    - Enrollment is deleted
    
    Args:
        user_id: User ID
        course_id: Course ID
        
    Usage:
        # In Enrollment model or signal:
        from apps.videos.permissions import invalidate_enrollment_cache
        invalidate_enrollment_cache(enrollment.user_id, enrollment.course_id)
    """
    cache_key = f"enrollment:{user_id}:{course_id}"
    cache.delete(cache_key)
    
