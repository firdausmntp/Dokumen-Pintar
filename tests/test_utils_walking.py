"""Unit tests for :mod:`dokumen_pintar.utils.walking`."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from dokumen_pintar.config import AppConfig
from dokumen_pintar.context import build_context
from dokumen_pintar.utils.walking import _expand_doublestar, iter_files


def test_expand_doublestar_no_prefix() -> None:
    """Patterns without ``**/`` are returned unchanged."""
    assert _expand_doublestar("*.txt") == ("*.txt",)
    assert _expand_doublestar("foo/bar.md") == ("foo/bar.md",)


def test_expand_doublestar_with_rest() -> None:
    """``**/x`` expands to ``(x, **/x)`` so top-level + nested both match."""
    assert _expand_doublestar("**/*.txt") == ("*.txt", "**/*.txt")
    assert _expand_doublestar("**/sub/*.md") == ("sub/*.md", "**/sub/*.md")


def test_expand_doublestar_bare() -> None:
    """``**/`` alone (no rest) is returned as-is - it has no useful expansion."""
    assert _expand_doublestar("**/") == ("**/",)


def test_iter_files_doublestar_matches_top_level_and_nested(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    docs_dir, _ = tmp_roots
    (docs_dir / "top.txt").write_text("top", encoding="utf-8")
    (docs_dir / "nested").mkdir()
    (docs_dir / "nested" / "deep.txt").write_text("deep", encoding="utf-8")

    ctx = build_context(make_config())

    rels = sorted(
        p.relative_to(root_abs).as_posix()
        for _, p, root_abs in iter_files(ctx, glob="documents:/**/*.txt")
    )
    assert rels == ["nested/deep.txt", "top.txt"]


def test_iter_files_empty_glob_yields_nothing(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    docs_dir, _ = tmp_roots
    (docs_dir / "any.txt").write_text("x", encoding="utf-8")
    ctx = build_context(make_config())
    assert list(iter_files(ctx, glob="")) == []


def test_iter_files_root_filter_conflict_yields_nothing(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    docs_dir, _ = tmp_roots
    (docs_dir / "x.txt").write_text("x", encoding="utf-8")
    ctx = build_context(make_config())
    # glob targets 'documents' but root_filter forces 'reference' - conflict.
    assert list(iter_files(ctx, glob="documents:/*.txt", root_filter="reference")) == []


def test_iter_files_writable_only_skips_readonly(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    docs_dir, ref_dir = tmp_roots
    (docs_dir / "a.txt").write_text("a", encoding="utf-8")
    (ref_dir / "b.txt").write_text("b", encoding="utf-8")
    ctx = build_context(make_config())
    # 'reference' root is read-only by fixture; ensure it's skipped.
    rels = [r for r, _, _ in iter_files(ctx, glob="*.txt", writable_only=True)]
    assert "documents" in rels
    assert "reference" not in rels
