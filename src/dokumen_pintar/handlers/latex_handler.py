"""LaTeX (.tex) format handler.

Provides metadata, plain-text extraction (for search indexing), and
section-level structured access. Does NOT compile to PDF — Dokumen-Pintar
stays pure-Python; users wanting PDF should drive an external toolchain
themselves or use :func:`compose_pdf` for fresh documents.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from pylatexenc.latex2text import LatexNodes2Text
from pylatexenc.latexwalker import LatexWalker, LatexEnvironmentNode, LatexMacroNode

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


_DOCUMENTCLASS_RX = re.compile(r"\\documentclass\s*(?:\[[^\]]*\])?\s*\{([^}]+)\}")
_USEPACKAGE_RX = re.compile(r"\\usepackage\s*(?:\[[^\]]*\])?\s*\{([^}]+)\}")
_SECTION_LEVELS = {
    "part": 0,
    "chapter": 1,
    "section": 2,
    "subsection": 3,
    "subsubsection": 4,
    "paragraph": 5,
    "subparagraph": 6,
}


def _section_macro_name(node: Any) -> str | None:
    """Return the section-like macro name (without leading backslash) if
    `node` is a sectioning command, else None."""
    if not isinstance(node, LatexMacroNode):
        return None
    name = getattr(node, "macroname", None)
    if name in _SECTION_LEVELS:
        return name
    return None


def _macro_argument_text(node: LatexMacroNode) -> str:
    """Extract the first mandatory argument of a macro as plain text."""
    args = getattr(getattr(node, "nodeargd", None), "argnlist", None)
    if not args:
        return ""
    for arg in args:
        if arg is None:
            continue
        # Mandatory args are typically LatexGroupNode with delimiters '{','}'
        delim = getattr(arg, "delimiters", None)
        if delim and delim[0] == "{":
            return "".join(
                getattr(child, "chars", "") for child in getattr(arg, "nodelist", [])
            ).strip()
    return ""


def _collect_outline(text: str) -> list[dict[str, Any]]:
    walker = LatexWalker(text)
    try:
        nodes, _, _ = walker.get_latex_nodes()
    except Exception as exc:  # noqa: BLE001
        raise HandlerError(f"failed to parse latex: {exc}") from exc

    outline: list[dict[str, Any]] = []

    def _walk(node_list: list[Any]) -> None:
        for node in node_list:
            macro = _section_macro_name(node)
            if macro is not None:
                outline.append(
                    {
                        "index": len(outline),
                        "kind": macro,
                        "level": _SECTION_LEVELS[macro],
                        "title": _macro_argument_text(node),
                        "pos": node.pos,
                    }
                )
            # Recurse into environments (notably document).
            if isinstance(node, LatexEnvironmentNode):
                _walk(node.nodelist)

    _walk(nodes)
    return outline


def _collect_environments(text: str) -> dict[str, int]:
    walker = LatexWalker(text)
    try:
        nodes, _, _ = walker.get_latex_nodes()
    except Exception as exc:  # noqa: BLE001
        raise HandlerError(f"failed to parse latex: {exc}") from exc
    counts: dict[str, int] = {}

    def _walk(node_list: list[Any]) -> None:
        for node in node_list:
            if isinstance(node, LatexEnvironmentNode):
                name = getattr(node, "environmentname", None) or "?"
                counts[name] = counts.get(name, 0) + 1
                _walk(node.nodelist)

    _walk(nodes)
    return counts


def _section_text_at(text: str, idx: int) -> str:
    """Return the raw LaTeX source of the idx-th section (from its macro
    until the next section of equal-or-higher level / end of document)."""
    outline = _collect_outline(text)
    if idx < 0 or idx >= len(outline):
        raise HandlerError(f"section index out of range: {idx}")
    here = outline[idx]
    end = len(text)
    for nxt in outline[idx + 1 :]:
        if nxt["level"] <= here["level"]:
            end = nxt["pos"]
            break
    return text[here["pos"] : end]


class LatexHandler:
    """Handler for LaTeX ``.tex`` source files (read + structured outline)."""

    name: str = "latex"
    extensions: tuple[str, ...] = (".tex",)
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
        dc_match = _DOCUMENTCLASS_RX.search(text)
        packages = sorted({m.group(1).strip() for m in _USEPACKAGE_RX.finditer(text)})
        try:
            outline = _collect_outline(text)
        except HandlerError:
            outline = []
        try:
            envs = _collect_environments(text)
        except HandlerError:
            envs = {}
        return {
            "format": self.name,
            "size": stat.st_size,
            "mtime": stat.st_mtime,
            "documentclass": dc_match.group(1) if dc_match else None,
            "packages": packages,
            "section_count": len(outline),
            "environment_counts": envs,
            "outline": outline,
        }

    def extract_for_search(self, path: Path) -> str:
        try:
            text = self.read_text(path)
        except (OSError, UnicodeDecodeError, LookupError, ValueError):
            return ""
        try:
            return LatexNodes2Text().latex_to_text(text)
        except Exception:  # noqa: BLE001
            # Fall back to raw text — better than nothing for search.
            return text

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
        if key in {"outline", "sections"}:
            return _collect_outline(text)
        if key == "packages":
            return sorted({m.group(1).strip() for m in _USEPACKAGE_RX.finditer(text)})
        if key == "documentclass":
            m = _DOCUMENTCLASS_RX.search(text)
            return m.group(1) if m else None
        if key == "environments":
            return _collect_environments(text)
        if key.startswith("section:"):
            raw = key.split(":", 1)[1].strip()
            if not raw or not raw.lstrip("-").isdigit():
                raise HandlerError(f"invalid section index: {expr!r}")
            return _section_text_at(text, int(raw))
        raise HandlerError(f"unsupported structured expression: {expr!r}")

    def structured_set(self, path: Path, expr: str, value: Any) -> None:
        raise UnsupportedFormatError(
            "latex handler: structured_set not supported; edit the source via "
            "content_replace / content_patch."
        )

    def structured_delete(self, path: Path, expr: str) -> None:
        raise UnsupportedFormatError(
            "latex handler: structured_delete not supported; edit the source via "
            "content_delete_range / content_patch."
        )


# Runtime-checkable protocol sanity assertion.
_handler: FormatHandler = LatexHandler()
default_registry.register(_handler)
