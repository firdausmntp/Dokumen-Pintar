"""Handler registry & protocol."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Flag, auto
from pathlib import Path
from typing import Any, Protocol, runtime_checkable


class HandlerCapability(Flag):
    READ_TEXT = auto()
    WRITE_TEXT = auto()
    STRUCTURED_GET = auto()
    STRUCTURED_SET = auto()
    STRUCTURED_DELETE = auto()
    LIST_ITEMS = auto()
    SEARCH_EXTRACTED = auto()  # can produce plain text for search indexing
    BINARY_ONLY = auto()


@runtime_checkable
class FormatHandler(Protocol):
    """Uniform protocol implemented by every format handler."""

    name: str
    extensions: tuple[str, ...]
    capabilities: HandlerCapability

    def detect(self, path: Path) -> bool: ...  # pragma: no cover

    def read_meta(self, path: Path) -> dict[str, Any]: ...  # pragma: no cover

    def read_text(self, path: Path, **kwargs: Any) -> str: ...  # pragma: no cover

    def write_text(self, path: Path, content: str, **kwargs: Any) -> None: ...  # pragma: no cover

    def extract_for_search(self, path: Path) -> str: ...  # pragma: no cover

    def structured_get(self, path: Path, expr: str) -> Any: ...  # pragma: no cover

    def structured_set(self, path: Path, expr: str, value: Any) -> None: ...  # pragma: no cover

    def structured_delete(self, path: Path, expr: str) -> None: ...  # pragma: no cover


@dataclass
class HandlerRegistry:
    handlers_by_format: dict[str, FormatHandler] = field(default_factory=dict)
    handlers_by_ext: dict[str, FormatHandler] = field(default_factory=dict)

    def register(self, handler: FormatHandler) -> None:
        self.handlers_by_format[handler.name] = handler
        for ext in handler.extensions:
            self.handlers_by_ext[ext.lower()] = handler

    def by_format(self, fmt: str) -> FormatHandler | None:
        return self.handlers_by_format.get(fmt)

    def for_path(self, path: Path) -> FormatHandler | None:
        ext = path.suffix.lower()
        return self.handlers_by_ext.get(ext)

    def all(self) -> list[FormatHandler]:
        return list(self.handlers_by_format.values())


default_registry = HandlerRegistry()
