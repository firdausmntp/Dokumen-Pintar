"""Tests for :mod:`dokumen_pintar.tools._common`."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import pytest

from dokumen_pintar.config import AppConfig
from dokumen_pintar.context import AppContext, build_context
from dokumen_pintar.errors import (
    FileTooLargeError,
    RootNotWritableError,
    UnsupportedFormatError,
)
from dokumen_pintar.tools._common import (
    handler_for,
    resolve_for_read,
    resolve_for_write,
    summarize_resolved,
)


def test_resolve_for_read_ok(context: AppContext, tmp_roots: tuple[Path, Path]) -> None:
    docs_dir, _ = tmp_roots
    target = docs_dir / "hello.txt"
    target.write_text("hi", encoding="utf-8")
    resolved = resolve_for_read(context, str(target))
    assert resolved.root.name == "documents"


def test_resolve_for_read_size_limit(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    docs_dir, _ = tmp_roots
    cfg = make_config(max_file_size_mb=1)
    ctx = build_context(cfg)

    target = docs_dir / "huge.txt"
    target.write_bytes(b"x" * (2 * 1024 * 1024))

    with pytest.raises(FileTooLargeError):
        resolve_for_read(ctx, str(target))


def test_resolve_for_write_ok(context: AppContext, tmp_roots: tuple[Path, Path]) -> None:
    docs_dir, _ = tmp_roots
    target = docs_dir / "writeable.txt"
    target.write_text("ok", encoding="utf-8")
    resolved = resolve_for_write(context, str(target))
    assert resolved.root.writable is True


def test_resolve_for_write_readonly(context: AppContext, tmp_roots: tuple[Path, Path]) -> None:
    _, ref_dir = tmp_roots
    target = ref_dir / "readonly.txt"
    target.write_text("nope", encoding="utf-8")
    with pytest.raises(RootNotWritableError):
        resolve_for_write(context, str(target))


def test_handler_for_known_extension(context: AppContext, tmp_roots: tuple[Path, Path]) -> None:
    docs_dir, _ = tmp_roots
    target = docs_dir / "data.json"
    h = handler_for(context, target)
    assert h.name == "json"


def test_handler_for_unknown_extension(context: AppContext, tmp_roots: tuple[Path, Path]) -> None:
    docs_dir, _ = tmp_roots
    target = docs_dir / "data.xyz"
    with pytest.raises(UnsupportedFormatError):
        handler_for(context, target)


def test_summarize_resolved(context: AppContext, tmp_roots: tuple[Path, Path]) -> None:
    docs_dir, _ = tmp_roots
    target = docs_dir / "sum.txt"
    target.write_text("x", encoding="utf-8")
    resolved = context.guard.resolve(str(target))
    summary = summarize_resolved(resolved)
    assert "uri" in summary
    assert "absolute" in summary
    assert "root" in summary
    assert "rel" in summary
    assert summary["root"] == "documents"
