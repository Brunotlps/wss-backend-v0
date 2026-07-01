"""Unit tests for enrollment serializer validators (#34).

These lock the defense-in-depth business rules that the API path shadows:
``watched_duration`` and ``rating`` are guarded a second time inside the
serializer even though the model fields (PositiveIntegerField / MaxValueValidator)
reject bad input first at the DRF field level, and the "owner only" update rule
sits behind the view's owner-filtered queryset (a non-owner gets 404 before
``validate`` runs). Exercised directly so the guards themselves are verified.
"""

from types import SimpleNamespace

from rest_framework import serializers

import pytest

from apps.enrollments.factories import EnrollmentFactory
from apps.enrollments.serializers import (
    EnrollmentUpdateSerializer,
    LessonProgressSerializer,
)
from apps.users.factories import UserFactory


class TestLessonProgressValidators:
    """Field-level guards on LessonProgressSerializer."""

    def test_validate_watched_duration_rejects_negative(self):
        """A negative watched_duration raises ValidationError (guard behind
        the model's PositiveIntegerField)."""
        with pytest.raises(serializers.ValidationError):
            LessonProgressSerializer().validate_watched_duration(-1)

    def test_validate_watched_duration_allows_non_negative(self):
        """A non-negative value passes through unchanged."""
        assert LessonProgressSerializer().validate_watched_duration(5) == 5


class TestEnrollmentUpdateValidators:
    """Guards on EnrollmentUpdateSerializer."""

    def test_validate_rating_rejects_out_of_range(self):
        """A rating above 5 raises (guard behind the model's MaxValueValidator)."""
        with pytest.raises(serializers.ValidationError):
            EnrollmentUpdateSerializer().validate_rating(6)

    @pytest.mark.django_db
    def test_validate_rejects_update_by_non_owner(self):
        """Only the enrollment owner may update it — a non-owner is rejected
        (defense in depth behind the view's owner-filtered queryset)."""
        enrollment = EnrollmentFactory(user=UserFactory())
        serializer = EnrollmentUpdateSerializer(
            instance=enrollment,
            data={"is_active": False},
            partial=True,
            context={"request": SimpleNamespace(user=UserFactory())},
        )
        assert not serializer.is_valid()
        assert "enrollment" in serializer.errors
