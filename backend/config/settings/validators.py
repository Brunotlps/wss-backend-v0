"""Settings validation helpers (fail-fast on misconfiguration).

Used by ``settings/production.py`` to refuse to start when required
third-party credentials are missing, instead of failing opaquely at
request time (#23).
"""

from typing import Dict, Optional

from django.core.exceptions import ImproperlyConfigured


def require_non_empty(values: Dict[str, Optional[str]]) -> None:
    """Validate that every mapped setting has a non-empty value.

    Args:
        values: Mapping of setting name -> value. ``None``, an empty string, or
            a whitespace-only string is treated as missing (the env-var
            defaults in ``base.py``).

    Raises:
        ImproperlyConfigured: If any value is missing, listing all of them so
            the operator can fix the environment in one pass.
    """
    missing = sorted(
        name for name, value in values.items() if not (value and value.strip())
    )
    if missing:
        raise ImproperlyConfigured(
            "Missing required production settings (set the corresponding "
            "environment variables): " + ", ".join(missing)
        )
