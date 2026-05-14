"""Tests for :mod:`dokumen_pintar.handlers.base`."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from dokumen_pintar.handlers.base import (
    FormatHandler,
    HandlerCapability,
    HandlerRegistry,
)


class _DummyHandler:
    """Minimal handler for testing the registry."""

    name = "dummy"
    extensions = (".dum", ".dummy")
    capabilities = HandlerCapability.READ_TEXT

    def detect(self, path: Path) -> bool:
        return path.suffix.lower() in self.extensions

    def read_meta(self, path: Path) -> dict[str, Any]:
        return {}

    def read_text(self, path: Path, **kwargs: Any) -> str:
        return ""

    def write_text(self, path: Path, content: str, **kwargs: Any) -> None:
        pass

    def extract_for_search(self, path: Path) -> str:
        return ""

    def structured_get(self, path: Path, expr: str) -> Any:
        return None

    def structured_set(self, path: Path, expr: str, value: Any) -> None:
        pass

    def structured_delete(self, path: Path, expr: str) -> None:
        pass


def test_dummy_satisfies_format_handler_protocol() -> None:
    handler = _DummyHandler()
    assert isinstance(handler, FormatHandler)


def test_registry_register_and_by_format() -> None:
    reg = HandlerRegistry()
    handler = _DummyHandler()
    reg.register(handler)
    assert reg.by_format("dummy") is handler


def test_registry_for_path_by_extension() -> None:
    reg = HandlerRegistry()
    handler = _DummyHandler()
    reg.register(handler)
    assert reg.for_path(Path("test.dum")) is handler
    assert reg.for_path(Path("test.dummy")) is handler


def test_registry_for_path_case_insensitive() -> None:
    reg = HandlerRegistry()
    handler = _DummyHandler()
    reg.register(handler)
    assert reg.for_path(Path("test.DUM")) is handler


def test_registry_for_path_unknown() -> None:
    reg = HandlerRegistry()
    assert reg.for_path(Path("test.xyz")) is None


def test_registry_by_format_unknown() -> None:
    reg = HandlerRegistry()
    assert reg.by_format("nonexistent") is None


def test_registry_all_lists_all() -> None:
    reg = HandlerRegistry()
    h1 = _DummyHandler()
    h1.name = "handler_a"
    h1.extensions = (".a",)

    h2 = _DummyHandler()
    h2.name = "handler_b"
    h2.extensions = (".b",)

    reg.register(h1)
    reg.register(h2)
    all_handlers = reg.all()
    assert len(all_handlers) == 2
    names = {h.name for h in all_handlers}
    assert names == {"handler_a", "handler_b"}


def test_capability_flags() -> None:
    combo = HandlerCapability.READ_TEXT | HandlerCapability.WRITE_TEXT
    assert HandlerCapability.READ_TEXT in combo
    assert HandlerCapability.WRITE_TEXT in combo
    assert HandlerCapability.STRUCTURED_GET not in combo
