"""Tests for production settings fail-fast validation (#23)."""

from django.core.exceptions import ImproperlyConfigured

import pytest

from config.settings.validators import require_non_empty


class TestRequireNonEmpty:
    """Tests for require_non_empty (fail-fast on missing config)."""

    def test_passes_when_all_values_present(self):
        """No exception when every mapped value is non-empty."""
        require_non_empty({"A": "x", "B": "y"})  # must not raise

    def test_raises_listing_only_missing_names(self):
        """Empty string and None are missing; present keys are not listed."""
        with pytest.raises(ImproperlyConfigured) as exc_info:
            require_non_empty({"A": "x", "B": "", "C": None})

        message = str(exc_info.value)
        assert "B" in message
        assert "C" in message
        assert "A" not in message

    def test_message_points_to_environment_variables(self):
        """The error guides the operator to set the env vars."""
        with pytest.raises(ImproperlyConfigured, match="environment"):
            require_non_empty({"STRIPE_SECRET_KEY": ""})

    def test_empty_mapping_does_not_raise(self):
        """An empty mapping has nothing to validate and must not raise."""
        require_non_empty({})  # must not raise

    def test_whitespace_only_value_is_missing(self):
        """A whitespace-only value is treated as missing."""
        with pytest.raises(ImproperlyConfigured, match="A"):
            require_non_empty({"A": "   "})

    def test_missing_names_are_listed_sorted(self):
        """Missing names are reported in deterministic (sorted) order."""
        with pytest.raises(ImproperlyConfigured) as exc_info:
            require_non_empty({"Z": "", "A": "", "M": ""})

        listed = str(exc_info.value).split(": ", 1)[1]
        assert listed == "A, M, Z"
