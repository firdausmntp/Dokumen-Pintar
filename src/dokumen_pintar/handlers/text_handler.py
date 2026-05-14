"""Plain-text format handler."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from dokumen_pintar.errors import UnsupportedFormatError
from dokumen_pintar.handlers.base import (
    FormatHandler,
    HandlerCapability,
    default_registry,
)
from dokumen_pintar.utils.encoding import (
    read_text as _read_text,
    write_text as _write_text,
)


class TextHandler:
    """Handler for plain-text and source-code-like files."""

    name: str = "text"
    extensions: tuple[str, ...] = (
        ".txt",
        ".md",
        ".markdown",
        ".log",
        ".rst",
        ".ini",
        ".cfg",
        ".conf",
        ".py",
        ".ts",
        ".tsx",
        ".js",
        ".jsx",
        ".rs",
        ".go",
        ".java",
        ".cs",
        ".cpp",
        ".c",
        ".h",
        ".hpp",
        ".html",
        ".htm",
        ".css",
        ".scss",
        ".sass",
        ".sh",
        ".ps1",
        ".sql",
        ".toml",
    )
    capabilities: HandlerCapability = (
        HandlerCapability.READ_TEXT
        | HandlerCapability.WRITE_TEXT
        | HandlerCapability.SEARCH_EXTRACTED
    )

    def detect(self, path: Path) -> bool:
        return path.suffix.lower() in self.extensions

    def read_meta(self, path: Path) -> dict[str, Any]:
        stat = path.stat()
        raw = path.read_bytes()
        from dokumen_pintar.utils.encoding import detect_encoding

        encoding = detect_encoding(raw)
        try:
            text = raw.decode(encoding, errors="replace")
            line_count = text.count("\n") + (1 if text and not text.endswith("\n") else 0)
        except Exception:
            line_count = 0
        return {
            "format": self.name,
            "size": stat.st_size,
            "mtime": stat.st_mtime,
            "encoding": encoding,
            "line_count": line_count,
            "suffix": path.suffix.lower(),
        }

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

    def extract_for_search(self, path: Path) -> str:
        try:
            return self.read_text(path)
        except (OSError, UnicodeDecodeError, LookupError, ValueError):
            return ""

    def structured_get(self, path: Path, expr: str) -> Any:
        raise UnsupportedFormatError("structured ops not supported for text")

    def structured_set(self, path: Path, expr: str, value: Any) -> None:
        raise UnsupportedFormatError("structured ops not supported for text")

    def structured_delete(self, path: Path, expr: str) -> None:
        raise UnsupportedFormatError("structured ops not supported for text")


# Runtime-checkable protocol sanity assertion (no cost if Protocol is satisfied).
_handler: FormatHandler = TextHandler()
default_registry.register(_handler)
