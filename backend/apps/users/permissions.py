"""
Permissions for the users module

This module defines custom permission classes to control access
to user-related resources in the system. Permissions are used
in conjunction with Django REST Framework views to ensure that only
authorized users can perform certain operations.

Available permissions:
    - BasePermission: Base class from Django REST Framework for creating custom permissions
    - SAFE_METHODS: Constant that defines safe HTTP methods (GET, HEAD, OPTIONS)

When to use:
    - Import the necessary permission classes in views or viewsets
    - Use SAFE_METHODS to differentiate read operations from write operations
    - Extend BasePermission to create project-specific custom permissions
"""

from rest_framework.permissions import SAFE_METHODS, BasePermission


class IsOwnerOrReadOnly(BasePermission):
    """Authenticated access only; object access limited to the owner.

    ``has_permission`` rejects anonymous requests outright, so there is no public
    listing or retrieval of user PII. ``has_object_permission`` then limits access
    to the object's owner, with staff allowed to read any object and delete any.

    Ownership is resolved for the User object itself, owner-bearing objects
    (Profile, Enrollment) and instructor-bearing objects (Course).
    """

    def has_permission(self, request, view) -> bool:
        """Allow only authenticated requests (blocks anonymous list/retrieve)."""
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj) -> bool:
        """Authorize the action on ``obj`` based on ownership.

        Args:
            request: The HTTP request being made.
            view: The view being accessed.
            obj: The object being accessed.

        Returns:
            bool: True if the user may perform the requested action.

        Logic:
            - SAFE methods (GET, HEAD, OPTIONS): owner or staff.
            - DELETE: staff only.
            - Other writes (POST, PUT, PATCH): owner only.
        """
        if request.method == "DELETE":
            return request.user.is_staff

        if request.method in SAFE_METHODS:
            return request.user.is_staff or self._is_owner(request.user, obj)

        return self._is_owner(request.user, obj)

    @staticmethod
    def _is_owner(user, obj) -> bool:
        """Return True if ``user`` owns ``obj`` (User/Profile/Enrollment/Course)."""
        if hasattr(obj, "username") and hasattr(obj, "email"):  # the User itself
            return obj == user

        if hasattr(obj, "user"):  # Profile, Enrollment, ...
            return obj.user == user

        if hasattr(obj, "instructor"):  # Course
            return obj.instructor == user

        return False
