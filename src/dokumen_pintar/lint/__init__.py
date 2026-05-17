"""Lint subsystem package."""

from .base import (
    Issue,
    LintRule,
    add_preset,
    default_registry,
    register_rule,
)

# Importing rules + presets_id triggers their @register_rule + add_preset
# side effects, populating ``default_registry``.
from . import rules  # noqa: F401  (registration side effect)
from . import presets_id  # noqa: F401  (registration side effect)

__all__ = [
    "Issue",
    "LintRule",
    "add_preset",
    "default_registry",
    "register_rule",
]
