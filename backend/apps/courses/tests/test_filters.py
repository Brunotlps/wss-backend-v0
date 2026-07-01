"""Unit tests for CourseFilter methods (#72)."""

import pytest

from apps.courses.factories import CourseFactory
from apps.courses.filters import CourseFilter
from apps.courses.models import Course


@pytest.mark.django_db
class TestFilterIsFree:
    """Direct coverage of the filter_is_free branches.

    ``?is_free=true|false`` is exercised end-to-end in test_views.py; this locks
    the defensive passthrough for a non-boolean value, which the DRF filter
    backend never reaches (it skips the method entirely on an empty value).
    """

    def test_none_value_is_a_passthrough(self):
        """A None value returns the queryset unchanged (no price filtering)."""
        CourseFactory(price=0)
        CourseFactory(price=99)
        queryset = Course.objects.all()

        result = CourseFilter().filter_is_free(queryset, "is_free", None)

        assert result.count() == queryset.count() == 2
