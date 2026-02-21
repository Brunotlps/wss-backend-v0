"""
Permissions for the courses module.

This module defines custom permission classes to control access to
course-related resources in the system. Permissions ensure that only
authorized users can perform certain operations on courses and categories.

Available permissions:
    - IsInstructorOrReadOnly: Only authenticated instructors can create/modify courses
    - IsCourseOwnerOrReadOnly: Only course owners can update/delete their courses

When to use:
    - Import these permission classes in views or viewsets
    - Apply to CourseViewSet to enforce business rules
    - Combine with IsAuthenticatedOrReadOnly for comprehensive access control
"""

from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsInstructorOrReadOnly(BasePermission):
    """
    Custom permission to only allow instructors to create courses.
    
    This permission grants read-only access to any request (GET, HEAD, OPTIONS),
    but only allows write permissions (POST, PUT, PATCH, DELETE) to users
    with is_instructor=True.
    
    Business Rule:
        - Anyone can view courses (public listing)
        - Only instructors can create new courses
        - Only instructors can modify/delete courses (combined with IsCourseOwnerOrReadOnly)
    
    Usage:
        class CourseViewSet(viewsets.ModelViewSet):
            permission_classes = [IsAuthenticatedOrReadOnly, IsInstructorOrReadOnly]
    
    Attributes:
        Inherits from BasePermission
        
    Methods:
        has_permission: Determines if user can perform the action at view level
    """
    
    def has_permission(self, request, view):
        """        
        This is VIEW-LEVEL permission (checked BEFORE accessing specific object).
        Called for list/create actions where no specific object exists yet.
        
        Args:
            request: The HTTP request being made (contains user, method, data)
            view: The view that is being accessed (CourseViewSet, etc.)
            
        Returns:
            bool: True if user has permission, False otherwise
        """

        if request.method in SAFE_METHODS:
            return True
        
        return request.user and request.user.is_authenticated and request.user.is_instructor


class IsCourseOwnerOrReadOnly(BasePermission):
    """
    Custom permission to only allow course owners to edit/delete their courses.
    
    This permission grants read-only access to any request,
    but only allows write permissions to the instructor who created the course.
    
    Business Rule:
        - Anyone can view course details (public access)
        - Only the course.instructor can update the course
        - Only the course.instructor can delete the course
    
    Usage:
        class CourseViewSet(viewsets.ModelViewSet):
            permission_classes = [IsAuthenticatedOrReadOnly, IsCourseOwnerOrReadOnly]
    
    Attributes:
        Inherits from BasePermission
        
    Methods:
        has_object_permission: Determines if user can perform action on specific course
    """
    
    def has_object_permission(self, request, view, obj):
        """
        Check if user has permission to perform action on this specific course.
        
        This is OBJECT-LEVEL permission (checked AFTER retrieving the course).
        Called for retrieve/update/delete actions on specific course instance.
        
        Args:
            request: The HTTP request being made
            view: The view that is being accessed
            obj: The Course object being accessed (has instructor, title, etc.)
            
        Returns:
            bool: True if user has permission, False otherwise
        """

        if request.method in SAFE_METHODS:
            return True
        
        return obj.instructor == request.user
