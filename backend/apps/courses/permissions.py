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

    On ``update``/``partial_update`` there IS an object, but
    ``has_object_permission`` only sees the module's *current* course by
    default — a ``course`` key in the write payload would reassign the
    module to a different course, and ``ModuleSerializer.course`` has no
    queryset restriction of its own. So ``has_object_permission`` applies
    the same ownership rule to a ``course`` value present in the request
    body as ``has_permission`` does on create (#237): denies with 403
    whether that target course is nonexistent, hidden, or owned by someone
    else, and — critically — never lets the write reach the serializer in
    any of those cases, so there's no second path for the reassignment to
    slip through. One difference from create: ``Module.course`` isn't
    nullable, so there's no missing-course-id case to let through as a 400
    here — an explicit ``course: null`` resolves like any other id that
    doesn't exist (403), not the required-field 400 a missing key would
    give on create.
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
        if obj.course.instructor != request.user:
            return False

        # Same rule as create (#223): a write reassigning `course` to one
        # the requester doesn't own denies with 403 whether that course
        # exists, is hidden, or is publicly visible — never falls through
        # to the serializer, which would otherwise apply its unfiltered
        # queryset and let the reassignment actually happen (#237).
        if "course" in request.data:
            try:
                new_course = Course.objects.get(pk=request.data["course"])
            except (ValueError, TypeError):
                return True
            except Course.DoesNotExist:
                return False
            if new_course.instructor != request.user:
                return False

        return True
