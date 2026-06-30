"""Deny-path tests for the users IsOwnerOrReadOnly permission (#50).

The view querysets already filter to the requesting user, so the object-level
branches of ``IsOwnerOrReadOnly`` are rarely reached end-to-end and were
under-covered (``permissions.py`` 79%, lines 57/70-73). These unit tests lock
in the allow **and** deny decisions directly on the permission class.
"""

from types import SimpleNamespace

from django.contrib.auth.models import AnonymousUser

from rest_framework.test import APIRequestFactory

import pytest

from apps.courses.factories import CourseFactory
from apps.users.factories import UserFactory
from apps.users.permissions import IsOwnerOrReadOnly

factory = APIRequestFactory()


def _request(method, user):
    """Build a DRF request of ``method`` authenticated as ``user``."""
    builder = getattr(factory, method.lower())
    request = builder("/")
    request.user = user
    return request


@pytest.mark.django_db
class TestIsOwnerOrReadOnlyHasPermission:
    """View-level gate: only authenticated requests pass."""

    def test_anonymous_is_denied(self):
        """An anonymous request is rejected (no public PII enumeration)."""
        permission = IsOwnerOrReadOnly()
        request = _request("GET", AnonymousUser())
        assert permission.has_permission(request, view=None) is False

    def test_authenticated_is_allowed(self):
        """An authenticated request passes the view-level gate."""
        permission = IsOwnerOrReadOnly()
        request = _request("GET", UserFactory())
        assert permission.has_permission(request, view=None) is True


@pytest.mark.django_db
class TestIsOwnerOrReadOnlyHasObjectPermission:
    """Object-level allow/deny across SAFE, DELETE and write methods."""

    def setup_method(self):
        self.permission = IsOwnerOrReadOnly()

    # -- SAFE methods (GET/HEAD/OPTIONS) ---------------------------------

    def test_safe_read_by_owner_allowed(self):
        """Owner may read their own object."""
        user = UserFactory()
        request = _request("GET", user)
        assert self.permission.has_object_permission(request, None, user) is True

    def test_safe_read_by_staff_allowed(self):
        """Staff may read any object (oversight)."""
        owner, staff = UserFactory(), UserFactory(is_staff=True)
        request = _request("GET", staff)
        assert self.permission.has_object_permission(request, None, owner) is True

    def test_safe_read_by_other_denied(self):
        """A non-owner, non-staff user cannot read another user's object."""
        owner, other = UserFactory(), UserFactory()
        request = _request("GET", other)
        assert self.permission.has_object_permission(request, None, owner) is False

    # -- DELETE (staff only) --------------------------------------------

    def test_delete_by_staff_allowed(self):
        """DELETE is permitted for staff."""
        owner, staff = UserFactory(), UserFactory(is_staff=True)
        request = _request("DELETE", staff)
        assert self.permission.has_object_permission(request, None, owner) is True

    def test_delete_by_owner_denied(self):
        """A non-staff owner cannot delete (delete is staff-only)."""
        owner = UserFactory()
        request = _request("DELETE", owner)
        assert self.permission.has_object_permission(request, None, owner) is False

    # -- Writes (PATCH/PUT/POST): owner only ----------------------------

    def test_write_by_owner_allowed(self):
        """Owner may update their own object."""
        user = UserFactory()
        request = _request("PATCH", user)
        assert self.permission.has_object_permission(request, None, user) is True

    def test_write_by_other_denied(self):
        """A non-owner cannot update another user's object."""
        owner, other = UserFactory(), UserFactory()
        request = _request("PATCH", other)
        assert self.permission.has_object_permission(request, None, owner) is False


@pytest.mark.django_db
class TestIsOwnerResolution:
    """``_is_owner`` resolves ownership for each supported object shape."""

    def setup_method(self):
        self.permission = IsOwnerOrReadOnly()

    def test_user_object_owner(self):
        """The User object itself is owned by the same user."""
        user = UserFactory()
        request = _request("PATCH", user)
        assert self.permission.has_object_permission(request, None, user) is True

    def test_owner_bearing_object(self):
        """A Profile (has .user) is owned by its user."""
        user = UserFactory()
        request = _request("PATCH", user)
        assert (
            self.permission.has_object_permission(request, None, user.profile) is True
        )

    def test_instructor_bearing_object_owner(self):
        """A Course (has .instructor) is owned by its instructor."""
        course = CourseFactory()
        request = _request("PATCH", course.instructor)
        assert self.permission.has_object_permission(request, None, course) is True

    def test_instructor_bearing_object_non_owner_denied(self):
        """A Course is not owned by an unrelated user."""
        course = CourseFactory()
        request = _request("PATCH", UserFactory())
        assert self.permission.has_object_permission(request, None, course) is False

    def test_unknown_object_shape_denied(self):
        """An object with no ownership attribute is denied (safe default)."""
        request = _request("PATCH", UserFactory())
        unknown = SimpleNamespace(foo="bar")
        assert self.permission.has_object_permission(request, None, unknown) is False
