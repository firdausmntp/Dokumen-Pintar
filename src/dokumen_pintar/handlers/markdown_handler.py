"""Markdown format handler with structured access (heading-based sections).

This handler claims ``.md`` and ``.markdown`` files and overrides the
catch-all :class:`TextHandler` registration for those extensions. Markdown
is plain text on disk, so :func:`batch_replace_content` and similar
text-mutating tools work normally on these files.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from markdown_it import MarkdownIt

from dokumen_pintar.errors import HandlerError, UnsupportedFormatError
from dokumen_pintar.handlers.base import (
    FormatHandler,
    HandlerCapability,
    default_registry,
)
from dokumen_pintar.utils.encoding import (
    read_text as _read_text,
    write_text as _write_text,
)


def _md() -> MarkdownIt:
    return MarkdownIt("commonmark", {"html": False}).enable("table")


def _collect_outline(text: str) -> list[dict[str, Any]]:
    """Return a list of {index, level, text, line} per ATX/Setext heading."""
    md = _md()
    tokens = md.parse(text)
    headings: list[dict[str, Any]] = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok.type == "heading_open":
            level = int(tok.tag[1:]) if tok.tag and tok.tag[0] == "h" else 1
            inline = tokens[i + 1] if i + 1 < len(tokens) else None
            text_val = inline.content if inline is not None else ""
            line = (tok.map[0] + 1) if tok.map else 0
            headings.append(
                {
                    "index": len(headings),
                    "level": level,
                    "text": text_val,
                    "line": line,
                }
            )
        i += 1
    return headings


def _collect_links(text: str) -> int:
    md = _md()
    tokens = md.parse(text)
    count = 0
    for tok in tokens:
        if tok.type == "inline" and tok.children:
            for child in tok.children:
                if child.type == "link_open":
                    count += 1
    return count


def _section_at(text: str, idx: int) -> str:
    """Return the text of the idx-th heading section (heading line +
    everything until the next heading of the same or higher level)."""
    md = _md()
    tokens = md.parse(text)
    lines = text.splitlines(keepends=True)

    # Build (heading_index, level, start_line_0based, end_line_exclusive)
    spans: list[tuple[int, int, int, int]] = []
    open_stack: list[tuple[int, int]] = []  # (heading_index, level)
    heading_count = 0
    pending: list[tuple[int, int, int]] = []  # (heading_index, level, start_line)

    for tok in tokens:
        if tok.type == "heading_open":
            level = int(tok.tag[1:]) if tok.tag and tok.tag[0] == "h" else 1
            start = tok.map[0] if tok.map else 0
            # Close any pending heading whose level >= this one.
            while pending and pending[-1][1] >= level:
                hidx, hlvl, hstart = pending.pop()
                spans.append((hidx, hlvl, hstart, start))
            pending.append((heading_count, level, start))
            heading_count += 1

    # Close remaining headings at EOF.
    while pending:
        hidx, hlvl, hstart = pending.pop()
        spans.append((hidx, hlvl, hstart, len(lines)))

    spans.sort(key=lambda x: x[0])

    if idx < 0 or idx >= len(spans):
        raise HandlerError(f"heading index out of range: {idx}")
    _h, _l, start, end = spans[idx]
    return "".join(lines[start:end])


class MarkdownHandler:
    """Handler for Markdown ``.md`` / ``.markdown`` files."""

    name: str = "markdown"
    extensions: tuple[str, ...] = (".md", ".markdown")
    capabilities: HandlerCapability = (
        HandlerCapability.READ_TEXT
        | HandlerCapability.WRITE_TEXT
        | HandlerCapability.STRUCTURED_GET
        | HandlerCapability.SEARCH_EXTRACTED
    )

    def detect(self, path: Path) -> bool:
        return path.suffix.lower() in self.extensions

    # ---------- reading ----------

    def read_text(
        self,
        path: Path,
        *,
        encoding: str | None = None,
        auto_detect: bool = True,
        **_: Any,
    ) -> str:
        text, _enc = _read_text(path, encoding=encoding, auto_detect=auto_detect)
        return text

    def read_meta(self, path: Path) -> dict[str, Any]:
        stat = path.stat()
        text = self.read_text(path)
        outline = _collect_outline(text)
        words = len(text.split())
        return {
            "format": self.name,
            "size": stat.st_size,
            "mtime": stat.st_mtime,
            "line_count": text.count("\n") + (1 if text and not text.endswith("\n") else 0),
            "word_count": words,
            "heading_count": len(outline),
            "link_count": _collect_links(text),
            "outline": outline,
        }

    def extract_for_search(self, path: Path) -> str:
        try:
            return self.read_text(path)
        except (OSError, UnicodeDecodeError, LookupError, ValueError):
            return ""

    # ---------- writing ----------

    def write_text(
        self,
        path: Path,
        content: str,
        *,
        encoding: str = "utf-8",
        newline: str = "\n",
        **_: Any,
    ) -> None:
        _write_text(path, content, encoding=encoding, newline=newline)

    # ---------- structured ----------

    def structured_get(self, path: Path, expr: str) -> Any:
        text = self.read_text(path)
        key = expr.strip()
        if key in {"outline", "headings"}:
            return _collect_outline(text)
        if key.startswith("heading:"):
            raw = key.split(":", 1)[1].strip()
            if not raw or not raw.lstrip("-").isdigit():
                raise HandlerError(f"invalid heading index: {expr!r}")
            idx = int(raw)
            return _section_at(text, idx)
        if key == "wordcount":
            return len(text.split())
        raise HandlerError(f"unsupported structured expression: {expr!r}")

    def structured_set(self, path: Path, expr: str, value: Any) -> None:
        raise UnsupportedFormatError(
            "markdown handler: structured_set not supported (use content_replace "
            "or content_patch on the underlying text)"
        )

    def structured_delete(self, path: Path, expr: str) -> None:
        raise UnsupportedFormatError(
            "markdown handler: structured_delete not supported (use "
            "content_delete_range on the underlying text)"
        )


# Runtime-checkable protocol sanity assertion.
_handler: FormatHandler = MarkdownHandler()
default_registry.register(_handler)
