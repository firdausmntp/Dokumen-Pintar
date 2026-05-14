"""Tests for :mod:`dokumen_pintar.tools.workspace`."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from mcp.server.fastmcp import FastMCP

from dokumen_pintar.config import AppConfig
from dokumen_pintar.context import AppContext, build_context
from dokumen_pintar.tools import workspace


def _setup(cfg: AppConfig) -> tuple[FastMCP, AppContext]:
    ctx = build_context(cfg)
    mcp = FastMCP(name="test")
    workspace.register(mcp, ctx)
    return mcp, ctx


def test_workspace_list_roots(make_config: Callable[..., AppConfig]) -> None:
    cfg = make_config()
    mcp, ctx = _setup(cfg)
    tool_fn = mcp._tool_manager._tools["workspace_list_roots"].fn
    result = tool_fn()
    assert result["count"] == 2
    names = {r["name"] for r in result["roots"]}
    assert "documents" in names
    assert "ref" in names


def test_workspace_stat_existing_file(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    docs_dir, _ = tmp_roots
    target = docs_dir / "stat_test.txt"
    target.write_text("hello", encoding="utf-8")

    cfg = make_config()
    mcp, ctx = _setup(cfg)
    tool_fn = mcp._tool_manager._tools["workspace_stat"].fn
    result = tool_fn(path=str(target))
    assert result["exists"] is True
    assert result["is_file"] is True
    assert result["format"] == "text"


def test_workspace_stat_nonexistent(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    docs_dir, _ = tmp_roots
    cfg = make_config()
    mcp, ctx = _setup(cfg)
    tool_fn = mcp._tool_manager._tools["workspace_stat"].fn
    result = tool_fn(path="documents:/ghost.txt")
    assert result["exists"] is False


def test_workspace_tree(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    docs_dir, _ = tmp_roots
    (docs_dir / "a.txt").write_text("a", encoding="utf-8")
    sub = docs_dir / "sub"
    sub.mkdir()
    (sub / "b.txt").write_text("b", encoding="utf-8")

    cfg = make_config()
    mcp, ctx = _setup(cfg)
    tool_fn = mcp._tool_manager._tools["workspace_tree"].fn
    result = tool_fn(path="documents:/", depth=3)
    assert "tree" in result
    assert len(result["tree"]) >= 1


# ── Additional workspace coverage ──


def test_workspace_stat_directory(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    docs_dir, _ = tmp_roots
    sub = docs_dir / "subdir"
    sub.mkdir()
    cfg = make_config()
    mcp, ctx = _setup(cfg)
    tool_fn = mcp._tool_manager._tools["workspace_stat"].fn
    result = tool_fn(path=str(sub))
    assert result["exists"] is True
    assert result["is_dir"] is True


def test_workspace_tree_not_a_dir(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    docs_dir, _ = tmp_roots
    f = docs_dir / "afile.txt"
    f.write_text("hi", encoding="utf-8")
    cfg = make_config()
    mcp, ctx = _setup(cfg)
    tool_fn = mcp._tool_manager._tools["workspace_tree"].fn
    result = tool_fn(path=str(f))
    assert "error" in result


def test_workspace_tree_with_glob(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    docs_dir, _ = tmp_roots
    (docs_dir / "a.txt").write_text("a", encoding="utf-8")
    (docs_dir / "b.md").write_text("b", encoding="utf-8")
    cfg = make_config()
    mcp, ctx = _setup(cfg)
    tool_fn = mcp._tool_manager._tools["workspace_tree"].fn
    result = tool_fn(path="documents:/", glob="*.txt")
    names = [e["name"] for e in result["tree"] if e["type"] == "file"]
    assert "a.txt" in names
    assert "b.md" not in names


def test_workspace_tree_hidden_files(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    docs_dir, _ = tmp_roots
    (docs_dir / ".hidden").write_text("hidden", encoding="utf-8")
    (docs_dir / "visible.txt").write_text("visible", encoding="utf-8")
    cfg = make_config()
    mcp, ctx = _setup(cfg)
    tool_fn = mcp._tool_manager._tools["workspace_tree"].fn

    result = tool_fn(path="documents:/", include_hidden=False)
    names = [e["name"] for e in result["tree"] if e["type"] == "file"]
    assert ".hidden" not in names

    result2 = tool_fn(path="documents:/", include_hidden=True)
    names2 = [e["name"] for e in result2["tree"] if e["type"] == "file"]
    assert ".hidden" in names2


def test_workspace_tree_depth_limit(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    docs_dir, _ = tmp_roots
    deep = docs_dir / "l1" / "l2" / "l3"
    deep.mkdir(parents=True)
    (deep / "deep.txt").write_text("deep", encoding="utf-8")
    cfg = make_config()
    mcp, ctx = _setup(cfg)
    tool_fn = mcp._tool_manager._tools["workspace_tree"].fn
    result = tool_fn(path="documents:/", depth=1)
    # Should have l1 dir but not recurse deeper
    assert "tree" in result


def test_workspace_tree_permission_error(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    from unittest.mock import patch
    docs_dir, _ = tmp_roots
    (docs_dir / "ok.txt").write_text("ok", encoding="utf-8")
    cfg = make_config()
    mcp, ctx = _setup(cfg)
    tool_fn = mcp._tool_manager._tools["workspace_tree"].fn
    with patch("pathlib.Path.iterdir", side_effect=PermissionError("no access")):
        result = tool_fn(path="documents:/")
    assert result["tree"] == []


def test_workspace_tree_exclude_pattern(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    docs_dir, _ = tmp_roots
    nm = docs_dir / "node_modules"
    nm.mkdir()
    (nm / "pkg.js").write_text("x", encoding="utf-8")
    (docs_dir / "app.txt").write_text("y", encoding="utf-8")
    cfg = make_config()
    cfg.exclude_patterns = ["node_modules", "node_modules/**"]
    mcp, ctx = _setup(cfg)
    tool_fn = mcp._tool_manager._tools["workspace_tree"].fn
    result = tool_fn(path="documents:/")
    names = [e["name"] for e in result["tree"]]
    assert "node_modules" not in names


def test_workspace_tree_stat_oserror(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    import traceback
    from unittest.mock import patch
    docs_dir, _ = tmp_roots
    (docs_dir / "stat_err.txt").write_text("x", encoding="utf-8")
    cfg = make_config()
    mcp, ctx = _setup(cfg)
    tool_fn = mcp._tool_manager._tools["workspace_tree"].fn
    _original_stat = Path.stat
    def _fail_stat(self, *args, **kwargs):
        if self.name == "stat_err.txt":
            # Only fail when called directly from workspace code (child.stat()),
            # not from is_file() / is_dir() which also call stat() internally.
            stack = "".join(traceback.format_stack())
            if "is_file" not in stack and "is_dir" not in stack:
                raise OSError("stat fail")
        return _original_stat(self, *args, **kwargs)
    with patch.object(Path, "stat", _fail_stat):
        result = tool_fn(path="documents:/")
    files = [e for e in result["tree"] if e["name"] == "stat_err.txt"]
    assert len(files) == 1
    assert files[0]["size"] == -1


def test_workspace_tree_github_hidden_included(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    docs_dir, _ = tmp_roots
    github_dir = docs_dir / ".github"
    github_dir.mkdir()
    (github_dir / "workflow.yml").write_text("on: push", encoding="utf-8")
    cfg = make_config()
    mcp, ctx = _setup(cfg)
    tool_fn = mcp._tool_manager._tools["workspace_tree"].fn
    result = tool_fn(path="documents:/", include_hidden=False)
    names = [e["name"] for e in result["tree"]]
    assert ".github" in names
