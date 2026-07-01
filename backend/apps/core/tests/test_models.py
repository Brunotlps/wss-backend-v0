"""Behavioral tests for the project-wide TimeStampedModel base (#86).

``TimeStampedModel`` is abstract and inherited by every model in the project,
but nothing exercised its contract — models.py showed "100%" only because the
field declarations run at import time. A regression flipping ``auto_now_add`` /
``auto_now`` would silently corrupt timestamps everywhere while CI stayed green.

The contract is verified through a concrete subclass (Course) since the base
cannot be instantiated on its own.
"""

from datetime import timedelta
from unittest.mock import patch

from django.utils import timezone

import pytest

from apps.courses.factories import CourseFactory


@pytest.mark.django_db
class TestTimeStampedModel:
    """created_at is write-once; updated_at advances on every save."""

    def test_timestamps_populated_on_create(self):
        """Both timestamps are set when the row is first created."""
        course = CourseFactory()
        assert course.created_at is not None
        assert course.updated_at is not None

    def test_created_at_is_immutable_and_updated_at_advances_on_save(self):
        """A later save() bumps updated_at but never rewrites created_at.

        ``timezone.now`` is pinned to two distinct instants (create, then
        update) so the advance is asserted deterministically rather than
        relying on wall-clock resolution between two rapid saves.
        """
        created_instant = timezone.now()
        updated_instant = created_instant + timedelta(minutes=1)

        with patch("django.utils.timezone.now", return_value=created_instant):
            course = CourseFactory()
        original_created_at = course.created_at
        first_updated_at = course.updated_at

        with patch("django.utils.timezone.now", return_value=updated_instant):
            course.title = "A changed title"
            course.save()
        course.refresh_from_db()

        assert course.created_at == original_created_at
        assert course.updated_at > first_updated_at
