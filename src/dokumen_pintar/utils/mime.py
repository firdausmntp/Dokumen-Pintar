"""MIME / format detection helpers."""

from __future__ import annotations

from pathlib import Path


# Lower-cased suffix -> logical format name.
EXTENSION_MAP: dict[str, str] = {
    # text-like
    ".txt": "text",
    ".md": "text",
    ".markdown": "text",
    ".log": "text",
    ".rst": "text",
    ".ini": "text",
    ".cfg": "text",
    ".conf": "text",
    ".py": "text",
    ".ts": "text",
    ".tsx": "text",
    ".js": "text",
    ".jsx": "text",
    ".rs": "text",
    ".go": "text",
    ".java": "text",
    ".cs": "text",
    ".cpp": "text",
    ".c": "text",
    ".h": "text",
    ".hpp": "text",
    ".html": "text",
    ".htm": "text",
    ".css": "text",
    ".scss": "text",
    ".sass": "text",
    ".sh": "text",
    ".ps1": "text",
    ".sql": "text",
    ".env": "text",
    # structured
    ".json": "json",
    ".jsonc": "json",
    ".json5": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".xml": "xml",
    ".svg": "xml",
    ".csv": "csv",
    ".tsv": "csv",
    # office
    ".docx": "docx",
    ".xlsx": "xlsx",
    ".pptx": "pptx",
    ".pdf": "pdf",
}


BINARY_MAGIC: tuple[tuple[bytes, str], ...] = (
    (b"%PDF-", "pdf"),
    (b"PK\x03\x04", "zip_office"),  # docx/xlsx/pptx are zip
)


def detect_format(path: Path, *, sniff_bytes: bool = False) -> str:
    """Return the logical format for *path*.

    Falls back to ``"binary"`` when nothing matches. Set ``sniff_bytes=True``
    only when you really need magic-byte fallback — it triggers a file read
    and is too slow for directory listings.
    """
    ext = path.suffix.lower()
    if ext in EXTENSION_MAP:
        return EXTENSION_MAP[ext]
    if not sniff_bytes:
        return "binary"
    if path.exists() and path.is_file():
        try:
            head = path.read_bytes()[:16]
        except OSError:
            return "binary"
        for magic, name in BINARY_MAGIC:
            if head.startswith(magic):
                if name == "zip_office":
                    # Disambiguate by extension we already tried; give up
                    return "binary"
                return name
    return "binary"
