"""Tests for :mod:`dokumen_pintar.tools.batch`."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from mcp.server.fastmcp import FastMCP

from dokumen_pintar.config import AppConfig
from dokumen_pintar.context import build_context
from dokumen_pintar.tools import batch


def _setup(cfg: AppConfig) -> tuple[FastMCP, ...]:
    ctx = build_context(cfg)
    mcp = FastMCP(name="test")
    batch.register(mcp, ctx)
    return mcp, ctx


def _tool(mcp: FastMCP, name: str):
    return mcp._tool_manager._tools[name].fn


def test_batch_rename_dry_run(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    docs_dir, _ = tmp_roots
    (docs_dir / "report_2024.txt").write_text("data", encoding="utf-8")
    (docs_dir / "report_2023.txt").write_text("data", encoding="utf-8")
    mcp, _ = _setup(make_config())
    result = _tool(mcp, "batch_rename")(
        glob="report_*.txt", pattern=r"report_", replacement="doc_", dry_run=True
    )
    assert result["dry_run"] is True
    assert result["count"] >= 1


def test_batch_rename_apply(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    docs_dir, _ = tmp_roots
    (docs_dir / "old_a.txt").write_text("a", encoding="utf-8")
    mcp, _ = _setup(make_config())
    result = _tool(mcp, "batch_rename")(
        glob="old_*.txt", pattern=r"old_", replacement="new_", dry_run=False
    )
    assert result["dry_run"] is False
    assert (docs_dir / "new_a.txt").exists()
    assert not (docs_dir / "old_a.txt").exists()


def test_batch_replace_content_dry_run(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    docs_dir, _ = tmp_roots
    (docs_dir / "fix.txt").write_text("TODO fix this", encoding="utf-8")
    mcp, _ = _setup(make_config())
    result = _tool(mcp, "batch_replace_content")(
        glob="*.txt", old="TODO", new="DONE", dry_run=True
    )
    assert result["dry_run"] is True
    assert result["count"] >= 1
    # Original unchanged
    assert "TODO" in (docs_dir / "fix.txt").read_text(encoding="utf-8")


def test_batch_replace_content_apply(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    docs_dir, _ = tmp_roots
    (docs_dir / "fix2.txt").write_text("TODO replace", encoding="utf-8")
    mcp, _ = _setup(make_config())
    result = _tool(mcp, "batch_replace_content")(
        glob="*.txt", old="TODO", new="DONE", dry_run=False
    )
    assert result["dry_run"] is False
    assert "DONE" in (docs_dir / "fix2.txt").read_text(encoding="utf-8")


def test_batch_delete_dry_run(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    docs_dir, _ = tmp_roots
    (docs_dir / "temp.log").write_text("log data", encoding="utf-8")
    mcp, _ = _setup(make_config())
    result = _tool(mcp, "batch_delete")(glob="*.log", dry_run=True)
    assert result["dry_run"] is True
    assert result["count"] >= 1
    assert (docs_dir / "temp.log").exists()


def test_batch_delete_apply(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    docs_dir, _ = tmp_roots
    (docs_dir / "kill.log").write_text("bye", encoding="utf-8")
    mcp, _ = _setup(make_config())
    result = _tool(mcp, "batch_delete")(glob="*.log", dry_run=False)
    assert result["dry_run"] is False
    assert not (docs_dir / "kill.log").exists()


# ── Additional batch coverage ──

import pytest
from dokumen_pintar.errors import ValidationError


def test_batch_rename_no_match(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    docs_dir, _ = tmp_roots
    (docs_dir / "keep.txt").write_text("k", encoding="utf-8")
    mcp, _ = _setup(make_config())
    result = _tool(mcp, "batch_rename")(
        glob="*.txt", pattern=r"ZZZNOMATCH", replacement="X", dry_run=False
    )
    assert result["count"] == 0


def test_batch_rename_target_exists_raises(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    docs_dir, _ = tmp_roots
    (docs_dir / "conflict_a.txt").write_text("a", encoding="utf-8")
    (docs_dir / "conflict_b.txt").write_text("b", encoding="utf-8")
    mcp, _ = _setup(make_config())
    with pytest.raises(ValidationError, match="Target exists"):
        _tool(mcp, "batch_rename")(
            glob="conflict_a.txt", pattern=r"_a", replacement="_b", dry_run=False
        )


def test_batch_replace_content_regex(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    docs_dir, _ = tmp_roots
    (docs_dir / "rg.txt").write_text("item123 item456", encoding="utf-8")
    mcp, _ = _setup(make_config())
    result = _tool(mcp, "batch_replace_content")(
        glob="rg.txt", old=r"item\d+", new="REPLACED", regex=True, dry_run=False
    )
    assert result["count"] >= 1
    assert "REPLACED" in (docs_dir / "rg.txt").read_text(encoding="utf-8")


def test_batch_replace_content_case_insensitive(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    docs_dir, _ = tmp_roots
    (docs_dir / "ci.txt").write_text("Hello HELLO hello", encoding="utf-8")
    mcp, _ = _setup(make_config())
    result = _tool(mcp, "batch_replace_content")(
        glob="ci.txt", old="hello", new="HI", case_sensitive=False, dry_run=False
    )
    content = (docs_dir / "ci.txt").read_text(encoding="utf-8")
    assert "Hello" not in content
    assert "HI" in content


def test_batch_replace_content_no_match(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    docs_dir, _ = tmp_roots
    (docs_dir / "nm.txt").write_text("nothing", encoding="utf-8")
    mcp, _ = _setup(make_config())
    result = _tool(mcp, "batch_replace_content")(
        glob="nm.txt", old="ZZZNOPE", new="X", dry_run=False
    )
    assert result["count"] == 0


def test_batch_delete_no_match(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    docs_dir, _ = tmp_roots
    mcp, _ = _setup(make_config())
    result = _tool(mcp, "batch_delete")(glob="*.nonexistent_ext", dry_run=False)
    assert result["count"] == 0


def test_batch_replace_skips_directories(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    docs_dir, _ = tmp_roots
    subdir = docs_dir / "subdir"
    subdir.mkdir()
    (docs_dir / "real.txt").write_text("hello", encoding="utf-8")
    mcp, _ = _setup(make_config())
    result = _tool(mcp, "batch_replace_content")(
        glob="*", old="hello", new="bye", dry_run=False
    )
    assert result["count"] >= 1


def test_batch_replace_skips_unrecognized_format(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    docs_dir, _ = tmp_roots
    (docs_dir / "data.zzz123").write_text("content", encoding="utf-8")
    mcp, _ = _setup(make_config())
    result = _tool(mcp, "batch_replace_content")(
        glob="*.zzz123", old="content", new="new", dry_run=False
    )
    # Unknown extension should be skipped (handler is None)
    assert result["count"] == 0


def test_batch_replace_skips_unreadable_file(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    from unittest.mock import patch
    docs_dir, _ = tmp_roots
    (docs_dir / "bad.txt").write_text("hello", encoding="utf-8")
    mcp, ctx = _setup(make_config())
    with patch("dokumen_pintar.tools.batch.read_text", side_effect=OSError("nope")):
        result = _tool(mcp, "batch_replace_content")(
            glob="bad.txt", old="hello", new="bye", dry_run=False
        )
    assert result["count"] == 0


def test_batch_exclude_pattern(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    docs_dir, _ = tmp_roots
    nm = docs_dir / "node_modules"
    nm.mkdir()
    (nm / "pkg.txt").write_text("old", encoding="utf-8")
    (docs_dir / "app.txt").write_text("old", encoding="utf-8")
    cfg = make_config()
    cfg.exclude_patterns = ["node_modules/**"]
    mcp, ctx = _setup(cfg)
    result = _tool(mcp, "batch_replace_content")(
        glob="*.txt", old="old", new="new", dry_run=True
    )
    paths = [f["absolute"] for f in result["files"]]
    assert not any("node_modules" in p for p in paths)


def test_batch_relative_to_valueerror(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    from unittest.mock import patch as _patch
    docs_dir, _ = tmp_roots
    (docs_dir / "ok.txt").write_text("testval", encoding="utf-8")
    cfg = make_config()
    mcp, ctx = _setup(cfg)
    _original_rglob = Path.rglob
    def _rglob_with_outside(self, pat):
        yield from _original_rglob(self, pat)
        yield Path("Z:/outside/fake.txt")
    _original_is_file = Path.is_file
    def _is_file_patched(self):
        if str(self).startswith("Z:"):
            return True
        return _original_is_file(self)
    with _patch.object(Path, "rglob", _rglob_with_outside):
        with _patch.object(Path, "is_file", _is_file_patched):
            result = _tool(mcp, "batch_replace_content")(
                glob="*.txt", old="testval", new="newval", dry_run=True
            )
    assert isinstance(result["files"], list)


# ── B1 regression: batch_replace_content must not corrupt binary files ──


def test_batch_replace_content_skips_binary_content(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    docs_dir, _ = tmp_roots
    # File with .txt extension but binary content (NUL byte) — must be skipped.
    (docs_dir / "fake.txt").write_bytes(b"hello\x00world")
    (docs_dir / "real.txt").write_text("hello world", encoding="utf-8")
    mcp, _ = _setup(make_config())
    result = _tool(mcp, "batch_replace_content")(
        glob="*.txt", old="hello", new="HI", dry_run=False
    )
    # Only real.txt should be in plan; fake.txt skipped as binary_content.
    assert all("real.txt" in f["uri"] for f in result["files"])
    assert any(s["reason"] == "binary_content" for s in result.get("skipped", []))
    # Binary file must remain byte-identical.
    assert (docs_dir / "fake.txt").read_bytes() == b"hello\x00world"


def test_batch_replace_content_skips_binary_format_docx(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    from docx import Document

    docs_dir, _ = tmp_roots
    docx_path = docs_dir / "doc.docx"
    doc = Document()
    doc.add_paragraph("hello world")
    doc.save(str(docx_path))
    original_bytes = docx_path.read_bytes()
    mcp, _ = _setup(make_config())
    result = _tool(mcp, "batch_replace_content")(
        glob="*.docx", old="hello", new="HI", dry_run=False
    )
    # docx must never be touched by raw text replace.
    assert result["count"] == 0
    assert any(s["reason"] == "binary_format" for s in result.get("skipped", []))
    assert docx_path.read_bytes() == original_bytes


def test_batch_replace_content_skips_oversized_files(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    docs_dir, _ = tmp_roots
    big_path = docs_dir / "big.txt"
    cfg = make_config()
    cfg.max_file_size_mb = 1  # 1MB limit
    # Write 1.5MB of text — should exceed the limit.
    big_path.write_text("X" * (int(1.5 * 1024 * 1024)), encoding="utf-8")
    (docs_dir / "small.txt").write_text("X here", encoding="utf-8")
    mcp, _ = _setup(cfg)
    result = _tool(mcp, "batch_replace_content")(
        glob="*.txt", old="X", new="Y", dry_run=True
    )
    # Big file must be skipped, small file should be planned.
    skipped_uris = {s["uri"] for s in result.get("skipped", []) if s["reason"] == "exceeds_max_file_size"}
    assert any("big.txt" in u for u in skipped_uris)


def test_looks_binary_returns_true_on_oserror(tmp_path: Path) -> None:
    from dokumen_pintar.tools.batch import _looks_binary

    # Path to a non-existent file should produce OSError on open and return True.
    assert _looks_binary(tmp_path / "does_not_exist.bin") is True


def test_batch_replace_content_handles_stat_oserror(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path], monkeypatch
) -> None:
    """Cover the stat() OSError skip branch in batch_replace_content."""
    docs_dir, _ = tmp_roots
    target = docs_dir / "stat_fail.txt"
    target.write_text("hello", encoding="utf-8")
    mcp, _ = _setup(make_config())

    real_stat = Path.stat

    def _stat_raises(self, *args, **kwargs):
        # Only fail the size-check stat() call (no kwargs); leave is_file()'s
        # follow_symlinks call alone so iteration can reach the size check.
        if self.name == "stat_fail.txt" and not args and not kwargs:
            raise OSError("simulated stat failure")
        return real_stat(self, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", _stat_raises)
    result = _tool(mcp, "batch_replace_content")(
        glob="stat_fail.txt", old="hello", new="HI", dry_run=True
    )
    assert any(s["reason"] == "stat_failed" for s in result.get("skipped", []))
