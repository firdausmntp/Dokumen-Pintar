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


# ── v1.1.0 6.3: workspace_diagnose ──


def _setup_with_diagnose(cfg: AppConfig) -> tuple[FastMCP, AppContext]:
    ctx = build_context(cfg)
    mcp = FastMCP(name="diagnose")
    workspace.register(mcp, ctx)
    workspace.register_diagnose(mcp, ctx)
    return mcp, ctx


def _diag(mcp: FastMCP):
    return mcp._tool_manager._tools["workspace_diagnose"].fn


def test_workspace_diagnose_basic_shape(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    mcp, _ctx = _setup_with_diagnose(make_config())
    result = _diag(mcp)()
    # Top-level keys.
    assert {
        "config",
        "roots",
        "snapshot_store",
        "audit_log",
        "extract_cache",
        "semantic_search",
        "warnings",
    } <= result.keys()
    # Both roots reported, both exist (created by tmp_roots fixture).
    assert len(result["roots"]) == 2
    assert all(r["exists"] for r in result["roots"])


def test_workspace_diagnose_warns_on_missing_root(
    make_config: Callable[..., AppConfig],
    tmp_roots: tuple[Path, Path],
    tmp_path: Path,
) -> None:
    """A configured root that doesn't exist on disk produces a warning."""
    cfg = make_config()
    # Add a root pointing nowhere.
    from dokumen_pintar.config import RootConfig

    cfg.roots.append(
        RootConfig(name="ghost", path=str(tmp_path / "does_not_exist"), writable=False)
    )
    mcp, _ctx = _setup_with_diagnose(cfg)
    result = _diag(mcp)()
    assert any("ghost" in w for w in result["warnings"])
    ghost = next(r for r in result["roots"] if r["name"] == "ghost")
    assert ghost["exists"] is False


def test_workspace_diagnose_audit_entries_count(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    """Audit log entry count is reported when log is non-empty."""
    mcp, ctx = _setup_with_diagnose(make_config())
    ctx.audit.log("test_event", note="hello")
    ctx.audit.log("test_event", note="world")
    ctx.audit.close()  # Force flush before reading.
    result = _diag(mcp)()
    assert result["audit_log"]["entries"] >= 2


def test_workspace_diagnose_warns_on_oversized_snapshot_db(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    """Stub the index_db_size to trigger the >100MB warning path."""
    from unittest.mock import patch

    mcp, _ctx = _setup_with_diagnose(make_config())

    real_stat = Path.stat

    def fake_stat(self, *a, **kw):  # type: ignore[no-untyped-def]
        result = real_stat(self, *a, **kw)
        # Fake 200 MB for the snapshot index db only.
        if "index.sqlite" in self.name:

            class _StatProxy:
                st_size = 200 * 1024 * 1024
                st_mtime = result.st_mtime
                st_mtime_ns = result.st_mtime_ns

            return _StatProxy()
        return result

    with patch.object(Path, "stat", fake_stat):
        result = _diag(mcp)()
    assert any("snapshot index db" in w for w in result["warnings"])


def test_workspace_diagnose_count_via_sql_fallback(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    """When VersionStore lacks count_all, the SQL fallback runs."""
    mcp, ctx = _setup_with_diagnose(make_config())
    # Take one snapshot so the count is observable.
    docs_dir, _ = tmp_roots
    f = docs_dir / "diag.txt"
    f.write_text("v1", encoding="utf-8")
    ctx.versions.snapshot(root_name="documents", rel_path="diag.txt", source=f, action="diag")
    # VersionStore does not implement count_all in v1.1.0, so the
    # diagnose tool falls back to a direct SQL count.
    assert not hasattr(ctx.versions, "count_all")
    result = _diag(mcp)()
    assert result["snapshot_store"]["snapshot_count"] >= 1


# ── workspace_diagnose coverage gap fillers ──


def test_dir_size_handles_outer_oserror(tmp_path: Path) -> None:
    """Outer ``rglob`` failure returns 0."""
    from unittest.mock import patch

    from dokumen_pintar.tools.workspace import _dir_size

    target = tmp_path / "rg"
    target.mkdir()
    with patch.object(Path, "rglob", side_effect=OSError("boom")):
        assert _dir_size(target) == 0


def test_workspace_diagnose_audit_io_error(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    """OSError on audit log read produces None for size/entries."""
    from unittest.mock import patch

    mcp, ctx = _setup_with_diagnose(make_config())
    ctx.audit.log("event", x=1)
    ctx.audit.close()

    real_open = Path.open

    def patched(self, *a, **kw):  # type: ignore[no-untyped-def]
        if "audit.jsonl" in self.name:
            raise OSError("io fail")
        return real_open(self, *a, **kw)

    with patch.object(Path, "open", patched):
        result = _diag(mcp)()
    assert result["audit_log"]["size_bytes"] is None
    assert result["audit_log"]["entries"] is None


def test_workspace_diagnose_warns_on_oversized_audit(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    """Audit log > 50 MB triggers a rotate-or-archive warning."""
    from unittest.mock import patch

    mcp, _ctx = _setup_with_diagnose(make_config())

    real_stat = Path.stat

    def fake_stat(self, *a, **kw):  # type: ignore[no-untyped-def]
        result = real_stat(self, *a, **kw)
        if "audit.jsonl" in self.name:

            class _S:
                st_size = 60 * 1024 * 1024
                st_mtime = result.st_mtime
                st_mtime_ns = result.st_mtime_ns

            return _S()
        return result

    # Touch the audit log so the path exists.
    _ctx.audit.log("e", x=1)
    _ctx.audit.close()

    with patch.object(Path, "stat", fake_stat):
        result = _diag(mcp)()
    assert any("audit log is" in w for w in result["warnings"])


def test_workspace_diagnose_warns_on_oversized_cache(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    """Extract cache > 200 MB triggers a clear-cache warning."""
    from unittest.mock import patch

    mcp, _ctx = _setup_with_diagnose(make_config())
    real_stat = Path.stat

    def fake_stat(self, *a, **kw):  # type: ignore[no-untyped-def]
        result = real_stat(self, *a, **kw)
        if "extract_cache.sqlite" in self.name:

            class _S:
                st_size = 250 * 1024 * 1024
                st_mtime = result.st_mtime
                st_mtime_ns = result.st_mtime_ns

            return _S()
        return result

    with patch.object(Path, "stat", fake_stat):
        result = _diag(mcp)()
    assert any("extract cache is" in w for w in result["warnings"])


def test_workspace_diagnose_with_semantic_index(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    """When ctx has a _semantic_index attribute, its stats are surfaced."""
    from unittest.mock import MagicMock

    mcp, ctx = _setup_with_diagnose(make_config())
    fake_idx = MagicMock()
    fake_idx.stats.return_value = {
        "chunks": 42,
        "documents": 7,
        "model": "fake-model",
    }
    ctx._semantic_index = fake_idx
    result = _diag(mcp)()
    assert result["semantic_search"]["chunks"] == 42
    assert result["semantic_search"]["documents"] == 7
    assert result["semantic_search"]["model"] == "fake-model"


def test_workspace_diagnose_semantic_index_stats_raises(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    """Best-effort: if _semantic_index.stats() raises, the call still succeeds."""
    from unittest.mock import MagicMock

    mcp, ctx = _setup_with_diagnose(make_config())
    fake_idx = MagicMock()
    fake_idx.stats.side_effect = RuntimeError("nope")
    ctx._semantic_index = fake_idx
    result = _diag(mcp)()
    # Stats keys absent (only `enabled` present from the default branch).
    assert "chunks" not in result["semantic_search"]


def test_count_snapshots_via_sql_returns_zero_for_missing_db(tmp_path: Path) -> None:
    """The SQL fallback returns 0 when the index db file does not yet exist."""
    from unittest.mock import MagicMock

    from dokumen_pintar.tools.workspace import _count_snapshots_via_sql

    fake_ctx = MagicMock()
    fake_ctx.versions._db_path = tmp_path / "absent.sqlite"
    assert _count_snapshots_via_sql(fake_ctx) == 0
