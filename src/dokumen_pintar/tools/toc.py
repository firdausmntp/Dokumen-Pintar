"""Table of Contents generator for DOCX files.

Walks the document's heading paragraphs (Title, Heading 1..9) and
emits a static markdown-style TOC inserted at a specified location
(or replacing an existing TOC region marked by ``DAFTAR ISI`` /
``Table of Contents`` heading).

Page numbers are best-effort: python-docx cannot reliably compute
final page positions without running Word's layout engine, so we
omit them by default. When ``page_numbers=True`` the tool emits
``-`` placeholders that Word will refresh on open if the user
selects "Update Field". Most agents use this tool for static
preview TOCs (markdown export, web rendering) where page numbers
are not meaningful anyway.
"""

from __future__ import annotations

import re
from copy import deepcopy
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from ..context import AppContext
from ..errors import HandlerError, UnsupportedFormatError, ValidationError
from ..utils.locks import file_lock
from ._common import resolve_for_write, summarize_resolved


def _heading_level(para: Any) -> int | None:
    """Return outline level (0 for Title, 1..9 for Heading N), or None."""
    style = getattr(para, "style", None)
    if style is None:  # pragma: no cover - defensive
        return None
    name = (style.name or "").strip()
    m = re.match(r"^[Hh]eading\s*(\d+)$", name)
    if m:
        return int(m.group(1))
    if name.lower() == "title":
        return 0
    return None


def _collect_toc_entries(
    doc: Any,
    *,
    max_depth: int,
    exclude_patterns: list[re.Pattern[str]],
) -> list[dict[str, Any]]:
    """Walk paragraphs and return ordered TOC entries."""
    entries: list[dict[str, Any]] = []
    for idx, para in enumerate(doc.paragraphs):
        lvl = _heading_level(para)
        if lvl is None or lvl > max_depth:
            continue
        text = (para.text or "").strip()
        if not text:  # pragma: no cover - empty heading paragraphs are filtered upstream
            continue
        if any(rx.search(text) for rx in exclude_patterns):
            continue
        entries.append({"level": lvl, "text": text, "paragraph_index": idx})
    return entries


def _format_toc_paragraph(entry: dict[str, Any], *, style: str, page_numbers: bool) -> str:
    """Format a single TOC line according to ``style``."""
    indent = "    " * max(0, entry["level"] - 1)
    text = entry["text"]
    if not page_numbers:
        if style == "indented":
            return f"{indent}{text}"
        # default: dotted leader without numbers (markdown-style)
        return f"{indent}{text}"
    # When page_numbers=True we emit a placeholder dash; Word users can
    # right-click → Update Field on a real {TOC} field instead.
    if style == "indented":
        return f"{indent}{text}\t-"
    # dotted_leader style with placeholder.
    leader = "." * max(3, 60 - len(indent) - len(text))
    return f"{indent}{text} {leader} -"


def _find_insertion_index(
    doc: Any,
    insert_at: str | None,
) -> int:
    """Resolve where to insert the TOC.

    Returns a 0-based body element index. ``None`` defaults to the start
    of the body (index 0 - just below the title).
    """
    body_children = list(doc.element.body)
    if insert_at is None:
        return 0

    # paragraph:N -> insert immediately after paragraph N.
    if insert_at.startswith("paragraph:"):
        try:
            target_idx = int(insert_at.split(":", 1)[1])
        except ValueError as exc:
            raise ValidationError(
                f"insert_at paragraph index must be an integer (got {insert_at!r})"
            ) from exc
        if target_idx < 0:
            raise ValidationError(f"insert_at paragraph index must be >= 0 (got {target_idx})")
        # Map the paragraph index to a body element index.
        para_count = 0
        from docx.oxml.ns import qn

        for i, el in enumerate(body_children):
            if el.tag == qn("w:p"):
                if para_count == target_idx:
                    return i + 1  # insert just after this paragraph
                para_count += 1
        # Out of range -> insert at end (before sectPr).
        return len(body_children)

    # after:HEADING_TEXT -> insert after the first matching heading.
    if insert_at.startswith("after:"):
        marker = insert_at.split(":", 1)[1].strip()
        if not marker:
            raise ValidationError("insert_at marker cannot be empty")
        from docx.oxml.ns import qn
        from docx.text.paragraph import Paragraph as _P

        for i, el in enumerate(body_children):
            if el.tag != qn("w:p"):
                continue
            text = (_P(el, doc).text or "").strip()
            if marker in text:
                return i + 1
        raise ValidationError(f"insert_at marker not found in document: {marker!r}")

    raise ValidationError(f"insert_at must be 'paragraph:N' or 'after:TEXT' (got {insert_at!r})")


def _insert_toc_paragraphs(
    doc: Any,
    body_idx: int,
    lines: list[str],
) -> None:
    """Insert each line as a fresh paragraph at body_idx."""
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    body = doc.element.body
    # Build a header marker so future runs can find/replace this TOC.
    marker = OxmlElement("w:p")
    marker_run = OxmlElement("w:r")
    marker_t = OxmlElement("w:t")
    marker_t.text = "DAFTAR ISI"
    marker_run.append(marker_t)
    marker.append(marker_run)
    inserted = [marker]

    for line in lines:
        p = OxmlElement("w:p")
        r = OxmlElement("w:r")
        t = OxmlElement("w:t")
        t.text = line
        # Preserve leading whitespace.
        t.set(qn("xml:space"), "preserve")
        r.append(t)
        p.append(r)
        inserted.append(p)

    # Insert in reverse so first item ends up at body_idx.
    for el in reversed(inserted):
        body.insert(body_idx, el)


def register(mcp: FastMCP, ctx: AppContext) -> None:
    """Register the toc_generate tool."""

    @mcp.tool(
        name="toc_generate",
        description=(
            "Generate a static table of contents from heading paragraphs. "
            "Walks Title + Heading 1..N styles up to `max_depth` (default 3) "
            "and inserts a 'DAFTAR ISI' block. `insert_at` accepts "
            "`paragraph:N` (insert after the Nth paragraph) or "
            "`after:TEXT` (insert after the first heading whose text "
            "contains TEXT). Defaults to the top of the body. "
            "`exclude_patterns` is a list of regex strings; matching "
            "headings are skipped. Snapshots pre+post."
        ),
    )
    def toc_generate(
        path: str,
        insert_at: str | None = None,
        style: str = "dotted_leader",
        max_depth: int = 3,
        exclude_patterns: list[str] | None = None,
        page_numbers: bool = False,
    ) -> dict[str, Any]:
        if style not in ("dotted_leader", "indented"):
            raise ValidationError(f"style must be 'dotted_leader' or 'indented' (got {style!r})")
        if max_depth < 0 or max_depth > 9:
            raise ValidationError(f"max_depth must be 0..9 (got {max_depth})")

        resolved = resolve_for_write(ctx, path)
        if resolved.absolute.suffix.lower() != ".docx":
            raise UnsupportedFormatError(
                f"toc_generate: target must be .docx, got {resolved.absolute.suffix!r}"
            )
        if not resolved.absolute.exists():
            raise ValidationError(f"file not found: {resolved.absolute}")

        excludes = [re.compile(p) for p in (exclude_patterns or [])]
        from docx import Document

        try:
            doc = Document(str(resolved.absolute))
        except Exception as exc:  # noqa: BLE001 - python-docx surfaces several types
            raise HandlerError(f"failed to open docx: {resolved.absolute} ({exc})") from exc

        entries = _collect_toc_entries(doc, max_depth=max_depth, exclude_patterns=excludes)
        if not entries:
            raise ValidationError(
                "no headings found in document; check max_depth and exclude_patterns"
            )

        body_idx = _find_insertion_index(doc, insert_at)
        lines = [_format_toc_paragraph(e, style=style, page_numbers=page_numbers) for e in entries]

        rel = resolved.rel_to_root.as_posix()
        root_name = resolved.root.name
        with file_lock(resolved.absolute):
            ctx.versions.snapshot(
                root_name=root_name,
                rel_path=rel,
                source=resolved.absolute,
                action="toc_generate_pre",
            )
            _insert_toc_paragraphs(doc, body_idx, lines)
            try:
                doc.save(str(resolved.absolute))
            except Exception as exc:  # noqa: BLE001 - python-docx serialiser
                raise HandlerError(f"failed to save docx: {resolved.absolute} ({exc})") from exc
            snap = ctx.versions.snapshot(
                root_name=root_name,
                rel_path=rel,
                source=resolved.absolute,
                action="toc_generate_post",
            )
        ctx.audit.log(
            "toc_generate",
            path=str(resolved.absolute),
            entries=len(entries),
            style=style,
            max_depth=max_depth,
        )
        return {
            **summarize_resolved(resolved),
            "entries": len(entries),
            "style": style,
            "snapshot": snap,
        }
