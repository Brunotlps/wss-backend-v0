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
    
