"""Lint rule framework for DOCX documents.

Rules subclass :class:`LintRule` and register themselves via
``register_rule``. Each rule produces zero or more :class:`Issue`
objects when invoked on a document. Rules carry a stable ``id``
(used in presets), a human-readable ``message`` template, a
``severity`` (``error`` / ``warn`` / ``info``), and an
``auto_fixable`` flag.

The :class:`Issue` object's ``location`` is a free-form dict; the
existing rules use ``{"paragraph": idx}``, ``{"table": idx, "row": r,
"col": c}``, or ``{"section": "BAB I"}``. ``apply_fix`` mutates the
provided ``Document`` in place and returns ``True`` if the fix was
applied successfully (False on no-op or unsupported scenarios).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, ClassVar, Iterator


Severity = str  # "error" | "warn" | "info"


@dataclass
class Issue:
    rule: str
    severity: Severity
    location: dict[str, Any]
    current: str = ""
    suggested: str = ""
    message: str = ""
    auto_fixable: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule": self.rule,
            "severity": self.severity,
            "location": self.location,
            "current": self.current,
            "suggested": self.suggested,
            "message": self.message,
            "auto_fixable": self.auto_fixable,
        }


class LintRule:
    """Base class for lint rules.

    Subclasses declare:

    - ``id`` (class var): unique stable identifier used in presets.
    - ``severity`` (class var): default severity for issues this rule emits.
    - ``auto_fixable`` (class var): True when ``apply_fix`` is implemented.

    Override ``check(doc)`` to yield :class:`Issue` instances and
    ``apply_fix(doc, issue)`` to perform the fix if supported.
    """

    id: ClassVar[str] = ""
    severity: ClassVar[Severity] = "warn"
    auto_fixable: ClassVar[bool] = False

    def check(self, doc: Any) -> Iterator[Issue]:
        raise NotImplementedError

    def apply_fix(self, doc: Any, issue: Issue) -> bool:
        # Default no-op for non-auto-fixable rules.
        return False


@dataclass
class _Registry:
    rules: dict[str, type[LintRule]] = field(default_factory=dict)
    presets: dict[str, dict[str, Any]] = field(default_factory=dict)

    def register(self, rule_cls: type[LintRule]) -> None:
        if not rule_cls.id:
            raise ValueError(f"rule class {rule_cls.__name__} has empty id")
        self.rules[rule_cls.id] = rule_cls

    def add_preset(
        self,
        name: str,
        *,
        rules: list[str],
        description: str = "",
        extends: str | None = None,
    ) -> None:
        self.presets[name] = {
            "description": description,
            "rules": list(rules),
            "extends": extends,
        }

    def resolve_preset(self, name: str) -> list[str]:
        """Expand `extends` chains into a flat list of rule IDs."""
        if name not in self.presets:
            raise KeyError(f"unknown preset: {name}")
        seen: set[str] = set()
        order: list[str] = []
        cursor: str | None = name
        while cursor is not None:
            if cursor in seen:
                raise ValueError(f"preset cycle detected at {cursor!r}")
            seen.add(cursor)
            preset = self.presets.get(cursor)
            if preset is None:
                raise KeyError(f"unknown preset (extends chain): {cursor}")
            order.extend(rid for rid in preset["rules"] if rid not in order)
            cursor = preset.get("extends")
        return order

    def rule(self, rule_id: str) -> type[LintRule]:
        if rule_id not in self.rules:
            raise KeyError(f"unknown rule: {rule_id}")
        return self.rules[rule_id]


# Process-wide singleton.
default_registry = _Registry()


def register_rule(rule_cls: type[LintRule]) -> type[LintRule]:
    """Decorator-friendly rule registrar."""
    default_registry.register(rule_cls)
    return rule_cls


def add_preset(
    name: str,
    *,
    rules: list[str],
    description: str = "",
    extends: str | None = None,
) -> None:
    """Add or replace a rule preset."""
    default_registry.add_preset(name, rules=rules, description=description, extends=extends)
