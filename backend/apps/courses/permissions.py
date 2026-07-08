"""
Permissions for the courses module.

This module defines custom permission classes to control access to
course-related resources in the system. Permissions ensure that only
authorized users can perform certain operations on courses and categories.

Available permissions:
    - IsInstructorOrReadOnly: Only authenticated instructors can create/modify courses
    - IsCourseOwnerOrReadOnly: Only course owners can update/delete their courses
    - IsModuleCourseInstructorOrReadOnly: Only the module's course instructor can create/modify modules

When to use:
    - Import these permission classes in views or viewsets
    - Apply to CourseViewSet to enforce business rules
    - Combine with IsAuthenticatedOrReadOnly for comprehensive access control
"""

from rest_framework.permissions import SAFE_METHODS, BasePermission

from .models import Course


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

        return (
            request.user
            and request.user.is_authenticated
            and request.user.is_instructor
        )


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


class IsModuleCourseInstructorOrReadOnly(BasePermission):
    """
    Only the instructor of the module's course may modify the module.

    Read access (GET/HEAD/OPTIONS) is open to anyone; write access (POST,
    PUT, PATCH, DELETE) is restricted to authenticated instructors at the
    view level, and to the specific course instructor at the object level.

    On ``create`` there is no object yet for ``has_object_permission`` to
    check, so ownership of the target course (from the request body) is
    resolved here instead (#122) — keeping the authz failure a 403
    everywhere, instead of the serializer raising a 400 for it. A missing
    ``course`` id is let through (returns True) so the serializer's own
    required-field validation surfaces the 400; a malformed id (wrong type)
    is let through for the same reason (invalid-pk 400).

    A ``course`` id that isn't owned by the requester denies with 403
    regardless of *why* it isn't theirs — nonexistent, existing-but-hidden
    (unpublished, someone else's), and existing-and-visible-but-not-theirs
    are all treated identically (#223). Distinguishing the nonexistent and
    hidden cases (403 vs a 400 fall-through) would let an instructor
    enumerate the existence of other instructors' unpublished courses,
    which they have no other way to discover. The visible-but-not-theirs
    case (a published course owned by someone else) doesn't need that
    protection — its existence isn't secret — but folding it into the same
    403 keeps the rule simple and avoids two different queries to tell the
    cases apart.
    """

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        if not bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_instructor
        ):
            return False

        if view.action == "create":
            course_id = request.data.get("course")
            if course_id is None:
                return True
            try:
                course = Course.objects.get(pk=course_id)
            except (ValueError, TypeError):
                return True
            except Course.DoesNotExist:
                return False
            return course.instructor == request.user

        return True

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        return obj.course.instructor == request.user
