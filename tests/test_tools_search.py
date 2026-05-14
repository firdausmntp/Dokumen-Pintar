"""Tests for :mod:`dokumen_pintar.tools.search`."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import pytest
from mcp.server.fastmcp import FastMCP

from dokumen_pintar.config import AppConfig
from dokumen_pintar.context import build_context
from dokumen_pintar.errors import DokumenPintarError
from dokumen_pintar.tools import search


def _setup(cfg: AppConfig) -> tuple[FastMCP, ...]:
    ctx = build_context(cfg)
    mcp = FastMCP(name="test")
    search.register(mcp, ctx)
    return mcp, ctx


def _tool(mcp: FastMCP, name: str):
    return mcp._tool_manager._tools[name].fn


def test_search_filename(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    docs_dir, _ = tmp_roots
    (docs_dir / "hello.txt").write_text("hi", encoding="utf-8")
    (docs_dir / "world.md").write_text("md", encoding="utf-8")
    mcp, _ = _setup(make_config())
    result = _tool(mcp, "search_filename")(glob_pattern="*.txt")
    assert result["count"] >= 1
    assert any("hello.txt" in m["uri"] for m in result["matches"])


def test_search_filename_with_root(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    docs_dir, ref_dir = tmp_roots
    (docs_dir / "a.txt").write_text("a", encoding="utf-8")
    (ref_dir / "b.txt").write_text("b", encoding="utf-8")
    mcp, _ = _setup(make_config())
    result = _tool(mcp, "search_filename")(glob_pattern="*.txt", root="documents")
    uris = [m["uri"] for m in result["matches"]]
    assert all("documents:" in u for u in uris)


def test_search_content(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    docs_dir, _ = tmp_roots
    (docs_dir / "needle.txt").write_text("The quick brown fox jumps", encoding="utf-8")
    (docs_dir / "other.txt").write_text("nothing here", encoding="utf-8")
    mcp, _ = _setup(make_config())
    result = _tool(mcp, "search_content")(query="quick brown")
    assert result["truncated"] is False
    assert len(result["matches"]) >= 1
    assert any("needle.txt" in m["uri"] for m in result["matches"])


def test_search_content_regex(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    docs_dir, _ = tmp_roots
    (docs_dir / "regex.txt").write_text("item123 item456", encoding="utf-8")
    mcp, _ = _setup(make_config())
    result = _tool(mcp, "search_content")(query=r"item\d+", regex=True)
    assert len(result["matches"]) >= 1


def test_search_content_no_match(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    docs_dir, _ = tmp_roots
    (docs_dir / "miss.txt").write_text("nothing special", encoding="utf-8")
    mcp, _ = _setup(make_config())
    result = _tool(mcp, "search_content")(query="ZZZZNOTFOUND")
    assert result["matches"] == []


def test_search_in_format(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    docs_dir, _ = tmp_roots
    (docs_dir / "search.txt").write_text("findme here", encoding="utf-8")
    (docs_dir / "data.json").write_text('{"key": "findme"}', encoding="utf-8")
    mcp, _ = _setup(make_config())
    result = _tool(mcp, "search_in_format")(query="findme", format="text")
    assert len(result["matches"]) >= 1
    # Should only find .txt, not .json
    for m in result["matches"]:
        assert m["format"] == "text"


def test_search_in_format_unknown(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    mcp, _ = _setup(make_config())
    with pytest.raises(DokumenPintarError, match="Unknown format"):
        _tool(mcp, "search_in_format")(query="x", format="nonexistent")


# ── Additional search coverage ──


def test_search_filename_limit(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    docs_dir, _ = tmp_roots
    for i in range(10):
        (docs_dir / f"file{i}.txt").write_text(f"content {i}", encoding="utf-8")
    mcp, _ = _setup(make_config())
    result = _tool(mcp, "search_filename")(glob_pattern="*.txt", limit=3)
    assert result["count"] == 3


def test_search_content_case_sensitive(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    docs_dir, _ = tmp_roots
    (docs_dir / "case.txt").write_text("FindMe here", encoding="utf-8")
    mcp, _ = _setup(make_config())
    result = _tool(mcp, "search_content")(query="findme", case_sensitive=True)
    assert len(result["matches"]) == 0
    result2 = _tool(mcp, "search_content")(query="FindMe", case_sensitive=True)
    assert len(result2["matches"]) >= 1


def test_search_content_max_files(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    docs_dir, _ = tmp_roots
    for i in range(5):
        (docs_dir / f"m{i}.txt").write_text(f"needle {i}", encoding="utf-8")
    mcp, _ = _setup(make_config())
    result = _tool(mcp, "search_content")(query="needle", max_files=2)
    # Should have scanned at most 2 files
    assert result["truncated"] is False


def test_search_content_max_results_truncation(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    docs_dir, _ = tmp_roots
    (docs_dir / "many.txt").write_text("hit\nhit\nhit\nhit\nhit", encoding="utf-8")
    mcp, _ = _setup(make_config())
    result = _tool(mcp, "search_content")(query="hit", max_results=2)
    assert result["truncated"] is True
    assert len(result["matches"]) == 2


def test_search_content_with_glob(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    docs_dir, _ = tmp_roots
    (docs_dir / "yes.txt").write_text("target", encoding="utf-8")
    (docs_dir / "no.md").write_text("target", encoding="utf-8")
    mcp, _ = _setup(make_config())
    result = _tool(mcp, "search_content")(query="target", glob="*.txt")
    for m in result["matches"]:
        assert ".txt" in m["uri"]


def test_search_in_format_regex(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    docs_dir, _ = tmp_roots
    (docs_dir / "regex.txt").write_text("item123 item456", encoding="utf-8")
    mcp, _ = _setup(make_config())
    result = _tool(mcp, "search_in_format")(
        query=r"item\d+", format="text", regex=True
    )
    assert len(result["matches"]) >= 1


def test_search_in_format_max_results(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    docs_dir, _ = tmp_roots
    (docs_dir / "trunc.txt").write_text("x\nx\nx\nx\nx", encoding="utf-8")
    mcp, _ = _setup(make_config())
    result = _tool(mcp, "search_in_format")(
        query="x", format="text", max_results=2
    )
    assert result["truncated"] is True


def test_search_filename_with_root_filter(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    docs_dir, _ = tmp_roots
    (docs_dir / "rootf.txt").write_text("x", encoding="utf-8")
    mcp, _ = _setup(make_config())
    result = _tool(mcp, "search_filename")(glob_pattern="*.txt", root="documents")
    assert result["count"] >= 1


def test_search_filename_wrong_root(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    docs_dir, _ = tmp_roots
    (docs_dir / "rootf2.txt").write_text("x", encoding="utf-8")
    mcp, _ = _setup(make_config())
    result = _tool(mcp, "search_filename")(glob_pattern="rootf2.txt", root="nonexistent_root")
    assert result["count"] == 0


def test_search_content_with_root_filter(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    docs_dir, _ = tmp_roots
    (docs_dir / "rf.txt").write_text("findmeroot", encoding="utf-8")
    mcp, _ = _setup(make_config())
    result = _tool(mcp, "search_content")(query="findmeroot", root="documents")
    assert len(result["matches"]) >= 1


def test_search_content_binary_file_skipped(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    docs_dir, _ = tmp_roots
    (docs_dir / "binary.bin").write_bytes(b"\x00\x01\x02\x03")
    mcp, _ = _setup(make_config())
    result = _tool(mcp, "search_content")(query="anything")
    # binary.bin should not cause errors, just be skipped (no handler)
    for m in result["matches"]:
        assert "binary.bin" not in m["uri"]


def test_search_content_excludes_hidden(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    docs_dir, _ = tmp_roots
    (docs_dir / "visible_search.txt").write_text("searchterm", encoding="utf-8")
    sub = docs_dir / ".hidden_dir"
    sub.mkdir()
    (sub / "hidden.txt").write_text("searchterm", encoding="utf-8")
    cfg = make_config()
    cfg.exclude_patterns = [".*"]
    mcp, _ = _setup(cfg)
    result = _tool(mcp, "search_content")(query="searchterm")
    for m in result["matches"]:
        assert ".hidden_dir" not in m["uri"]


def test_search_in_format_case_sensitive(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    docs_dir, _ = tmp_roots
    (docs_dir / "cs.txt").write_text("HelloWorld", encoding="utf-8")
    mcp, _ = _setup(make_config())
    result = _tool(mcp, "search_in_format")(
        query="helloworld", format="text", case_sensitive=True
    )
    assert len(result["matches"]) == 0
    result2 = _tool(mcp, "search_in_format")(
        query="HelloWorld", format="text", case_sensitive=True
    )
    assert len(result2["matches"]) >= 1


def test_search_content_with_nonexistent_root(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    import shutil
    docs_dir, _ = tmp_roots
    (docs_dir / "find_me.txt").write_text("findable", encoding="utf-8")
    cfg = make_config()
    mcp, _ = _setup(cfg)
    # Search with root filter that doesn't exist
    result = _tool(mcp, "search_content")(query="findable", root="nonexistent_root")
    assert result["matches"] == []


def test_search_content_extract_error_continues(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    from unittest.mock import patch
    docs_dir, _ = tmp_roots
    (docs_dir / "err_search.txt").write_text("findme", encoding="utf-8")
    cfg = make_config()
    mcp, ctx = _setup(cfg)
    # Patch extract_for_search on the text handler to raise
    from dokumen_pintar.handlers.text_handler import TextHandler
    with patch.object(TextHandler, "extract_for_search", side_effect=DokumenPintarError("fail")):
        result = _tool(mcp, "search_content")(query="findme")
    assert result["matches"] == []


def test_search_content_generic_exception_continues(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    from unittest.mock import patch
    docs_dir, _ = tmp_roots
    (docs_dir / "exc_search.txt").write_text("findme2", encoding="utf-8")
    cfg = make_config()
    mcp, ctx = _setup(cfg)
    from dokumen_pintar.handlers.text_handler import TextHandler
    with patch.object(TextHandler, "extract_for_search", side_effect=RuntimeError("oops")):
        result = _tool(mcp, "search_content")(query="findme2")
    assert result["matches"] == []


def test_search_in_format_extract_error(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    from unittest.mock import patch
    docs_dir, _ = tmp_roots
    (docs_dir / "fmt_err.txt").write_text("x", encoding="utf-8")
    cfg = make_config()
    mcp, ctx = _setup(cfg)
    from dokumen_pintar.handlers.text_handler import TextHandler
    with patch.object(TextHandler, "extract_for_search", side_effect=DokumenPintarError("fail")):
        result = _tool(mcp, "search_in_format")(query="x", format="text")
    assert result["matches"] == []


def test_walk_files_root_not_exists(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    import shutil
    docs_dir, _ = tmp_roots
    (docs_dir / "file.txt").write_text("hello", encoding="utf-8")
    cfg = make_config()
    mcp, ctx = _setup(cfg)
    # Remove root dir so it doesn't exist
    shutil.rmtree(docs_dir)
    result = _tool(mcp, "search_content")(query="hello")
    assert result["matches"] == []


def test_walk_files_relative_to_valueerror(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    from unittest.mock import patch
    docs_dir, _ = tmp_roots
    (docs_dir / "ok.txt").write_text("test", encoding="utf-8")
    cfg = make_config()
    mcp, ctx = _setup(cfg)
    _original_rglob = Path.rglob
    def _rglob_with_outside(self, pat):
        yield from _original_rglob(self, pat)
        fake = Path("Z:/outside/fake.txt")
        yield fake
    _original_is_file = Path.is_file
    def _is_file_override(self):
        if str(self).startswith("Z:"):
            return True
        return _original_is_file(self)
    with patch.object(Path, "rglob", _rglob_with_outside):
        with patch.object(Path, "is_file", _is_file_override):
            result = _tool(mcp, "search_content")(query="test")
    assert isinstance(result["matches"], list)
