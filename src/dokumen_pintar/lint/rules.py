"""Built-in lint rules for the v1.1.0 ``default`` preset.

Each rule emits Issue objects; the auto-fixable ones override
``apply_fix`` to mutate the python-docx Document in place.
"""

from __future__ import annotations

import re
from typing import Any, Iterator

from .base import Issue, LintRule, add_preset, register_rule


def _heading_level(para: Any) -> int | None:
    style = getattr(para, "style", None)
    if style is None:  # pragma: no cover - python-docx always sets a style
        return None
    name = (style.name or "").strip()
    m = re.match(r"^[Hh]eading\s*(\d+)$", name)
    if m:
        return int(m.group(1))
    if name.lower() == "title":
        return 0
    return None


@register_rule
class TrailingWhitespaceRule(LintRule):
    """Paragraphs ending in whitespace produce trailing-whitespace issues."""

    id = "trailing_whitespace"
    severity = "warn"
    auto_fixable = True

    def check(self, doc: Any) -> Iterator[Issue]:
        for idx, para in enumerate(doc.paragraphs):
            text = para.text or ""
            if text and text != text.rstrip():
                yield Issue(
                    rule=self.id,
                    severity=self.severity,
                    location={"paragraph": idx},
                    current=text,
                    suggested=text.rstrip(),
                    message="Paragraph has trailing whitespace",
                    auto_fixable=True,
                )

    def apply_fix(self, doc: Any, issue: Issue) -> bool:
        idx = issue.location.get("paragraph")
        if idx is None or idx >= len(doc.paragraphs):
            return False
        para = doc.paragraphs[idx]
        para.text = (para.text or "").rstrip()
        return True


@register_rule
class EmptyHeadingRule(LintRule):
    """Headings with no text content."""

    id = "empty_heading"
    severity = "warn"
    auto_fixable = True

    def check(self, doc: Any) -> Iterator[Issue]:
        for idx, para in enumerate(doc.paragraphs):
            level = _heading_level(para)
            if level is None:
                continue
            text = (para.text or "").strip()
            if not text:
                yield Issue(
                    rule=self.id,
                    severity=self.severity,
                    location={"paragraph": idx, "level": level},
                    current="",
                    suggested="",
                    message=f"Empty heading at level {level}",
                    auto_fixable=True,
                )

    def apply_fix(self, doc: Any, issue: Issue) -> bool:
        idx = issue.location.get("paragraph")
        if idx is None or idx >= len(doc.paragraphs):
            return False
        para = doc.paragraphs[idx]
        parent = para._element.getparent()
        if parent is None:  # pragma: no cover - paragraph always has parent
            return False
        parent.remove(para._element)
        return True


@register_rule
class DuplicateHeadingRule(LintRule):
    """Two heading paragraphs with identical text + level."""

    id = "duplicate_heading"
    severity = "warn"
    auto_fixable = False

    def check(self, doc: Any) -> Iterator[Issue]:
        seen: dict[tuple[int, str], int] = {}
        for idx, para in enumerate(doc.paragraphs):
            level = _heading_level(para)
            if level is None:
                continue
            text = (para.text or "").strip()
            if not text:
                continue
            key = (level, text.lower())
            if key in seen:
                yield Issue(
                    rule=self.id,
                    severity=self.severity,
                    location={
                        "paragraph": idx,
                        "first_paragraph": seen[key],
                        "level": level,
                    },
                    current=text,
                    message=(
                        f"Heading {text!r} (level {level}) is duplicated; "
                        f"first appearance at paragraph {seen[key]}"
                    ),
                    auto_fixable=False,
                )
            else:
                seen[key] = idx


@register_rule
class HeadingHierarchySkipRule(LintRule):
    """Detect heading-level jumps (e.g. H1 → H3 skips H2)."""

    id = "heading_hierarchy_skip"
    severity = "warn"
    auto_fixable = False

    def check(self, doc: Any) -> Iterator[Issue]:
        prev_level = 0
        for idx, para in enumerate(doc.paragraphs):
            level = _heading_level(para)
            if level is None:
                continue
            if level == 0:
                # Title resets the hierarchy floor.
                prev_level = 0
                continue
            if prev_level > 0 and level > prev_level + 1:
                yield Issue(
                    rule=self.id,
                    severity=self.severity,
                    location={"paragraph": idx, "level": level, "previous_level": prev_level},
                    current=(para.text or "").strip(),
                    message=(
                        f"Heading skipped from level {prev_level} to {level} "
                        f"(expected {prev_level + 1})"
                    ),
                    auto_fixable=False,
                )
            prev_level = level


@register_rule
class TitleCaseIndonesianRule(LintRule):
    """Indonesian title-case: every major word capitalised, conjunctions lowercase.

    Heuristic check: heading text where all-words-uppercase or first letter
    lowercased. Useful for catching ``DAFTAR isi`` or ``Bab i Pendahuluan``
    style mistakes.
    """

    id = "title_case_id"
    severity = "info"
    auto_fixable = False

    # Indonesian conjunctions / prepositions kept lowercase.
    _LOWERCASE_WORDS = frozenset(
        {
            "dan",
            "atau",
            "yang",
            "di",
            "ke",
            "dari",
            "untuk",
            "dengan",
            "pada",
            "sebagai",
            "oleh",
            "dalam",
            "tetapi",
            "atau",
            "the",
            "a",
            "of",
        }
    )

    def check(self, doc: Any) -> Iterator[Issue]:
        for idx, para in enumerate(doc.paragraphs):
            level = _heading_level(para)
            if level is None:
                continue
            text = (para.text or "").strip()
            if not text:  # pragma: no cover - empty headings caught by EmptyHeadingRule
                continue
            # All-lowercase or sentence-case heading is suspicious for
            # Indonesian titles where Title Case Each Major Word is the norm.
            words = text.split()
            if not words:  # pragma: no cover - non-empty text always splits to >=1 word
                continue
            problems: list[str] = []
            for i, w in enumerate(words):
                lw = w.lower()
                if lw in self._LOWERCASE_WORDS and i != 0:
                    continue
                if not w[0].isupper():
                    problems.append(w)
            if problems:
                yield Issue(
                    rule=self.id,
                    severity=self.severity,
                    location={"paragraph": idx, "level": level},
                    current=text,
                    message=(
                        f"Heading words not title-cased: {problems}. "
                        f"Indonesian academic style expects Title Case "
                        f"For Each Major Word."
                    ),
                    auto_fixable=False,
                )


@register_rule
class RequiredSectionRule(LintRule):
    """Generic required-section rule. Subclasses set ``required_section_pattern``."""

    id = "required_section"
    severity = "error"
    auto_fixable = False
    required_section_pattern: str = ""
    section_label: str = ""

    def check(self, doc: Any) -> Iterator[Issue]:
        if not self.required_section_pattern:
            return
        rx = re.compile(self.required_section_pattern, re.IGNORECASE)
        for para in doc.paragraphs:
            level = _heading_level(para)
            if level is None:
                continue
            text = (para.text or "").strip()
            if rx.search(text):
                return  # Found - rule satisfied.
        yield Issue(
            rule=self.id,
            severity=self.severity,
            location={"section": self.section_label or self.required_section_pattern},
            message=(
                f"Required section not found: {self.section_label or self.required_section_pattern!r}"
            ),
            auto_fixable=False,
        )


# ── presets ──

add_preset(
    "default",
    description="Basic structure & whitespace checks",
    rules=[
        "trailing_whitespace",
        "empty_heading",
        "duplicate_heading",
        "heading_hierarchy_skip",
    ],
)
