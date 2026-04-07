"""
Permissions module for the enrollments application.

This module defines permission classes that control access to enrollment-related
resources in the learning management system. It enforces role-based access control
for different user types (students, instructors, and administrators).

Purpose:
    - Restrict enrollment data access to authorized users only
    - Enforce permission rules for enrollment objects and related lesson progress
    - Provide a centralized permission management system for enrollment endpoints

Integration:
    - Used by Django REST Framework views in the enrollments app
    - Enforces object-level permissions on enrollment and lesson progress operations
    - Works in conjunction with the enrollment and course models to validate access rights
    - Supports both list/create and retrieve/update/delete operations with role-based rules

Permission Rules:
    - Administrators and staff members have full access to all enrollments
    - Students can only access their own enrollments and progress
    - Instructors have read-only access to enrollments in their courses
"""

from rest_framework.permissions import SAFE_METHODS, BasePermission


class IsEnrollmentOwner(BasePermission):
    """
    Permission class to control access to enrollment objects.

    Rules:
    - Staff/admin users have full access
    - Enrollment owner (student) can access their own enrollment
    - Course instructor can view (read-only) enrollments in their course
    - Other users are denied access
    """

    def has_object_permission(self, request, view, obj):

        # Admin/staff have full access
        if request.user.is_staff:
            return True

        # Enrollment owner (student) can access their own enrollment
        if obj.user == request.user:
            return True

        # Course instructor can view (read-only) enrollments in their course
        if obj.course.instructor == request.user and request.method in SAFE_METHODS:
            return True

        return False


class IsEnrolledOrInstructor(BasePermission):
    """
    Permission class to control access to lesson progress objects.

    Rules:
    - Staff/admin users have full access
    - Enrolled student can access their own lesson progress
    - Course instructor can view (read-only) lesson progress in their course
    - Other users are denied access
    """

    def has_object_permission(self, request, view, obj):
        # Admin/staff have full access
        if request.user.is_staff:
            return True

        # Enrolled student can access their own lesson progress
        if obj.enrollment.user == request.user:
            return True

        # Course instructor can view (read-only) lesson progress in their course
        if (
            obj.enrollment.course.instructor == request.user
            and request.method in SAFE_METHODS
        ):
            return True

        return False
