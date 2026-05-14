"""Tests for :mod:`dokumen_pintar.tools.version`."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import pytest
from mcp.server.fastmcp import FastMCP

from dokumen_pintar.config import AppConfig
from dokumen_pintar.context import build_context
from dokumen_pintar.errors import VersioningError
from dokumen_pintar.tools import version


def _setup(cfg: AppConfig) -> tuple[FastMCP, ...]:
    ctx = build_context(cfg)
    mcp = FastMCP(name="test")
    version.register(mcp, ctx)
    return mcp, ctx


def _tool(mcp: FastMCP, name: str):
    return mcp._tool_manager._tools[name].fn


def test_version_list_empty(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    docs_dir, _ = tmp_roots
    (docs_dir / "v.txt").write_text("x", encoding="utf-8")
    mcp, _ = _setup(make_config())
    result = _tool(mcp, "version_list")(path="documents:/v.txt")
    assert result["count"] == 0
    assert result["versions"] == []


def test_version_list_after_snapshot(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    docs_dir, _ = tmp_roots
    (docs_dir / "v.txt").write_text("content", encoding="utf-8")
    cfg = make_config()
    ctx = build_context(cfg)
    ctx.versions.snapshot(root_name="documents", rel_path="v.txt", source=docs_dir / "v.txt", action="test")

    mcp = FastMCP(name="test")
    version.register(mcp, ctx)
    result = _tool(mcp, "version_list")(path="documents:/v.txt")
    assert result["count"] == 1


def test_version_diff(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    docs_dir, _ = tmp_roots
    (docs_dir / "d.txt").write_bytes(b"original\n")
    cfg = make_config()
    ctx = build_context(cfg)
    rec = ctx.versions.snapshot(root_name="documents", rel_path="d.txt", source=docs_dir / "d.txt", action="test")
    (docs_dir / "d.txt").write_bytes(b"modified\n")

    mcp = FastMCP(name="test")
    version.register(mcp, ctx)
    result = _tool(mcp, "version_diff")(path="documents:/d.txt", version_id=rec["id"])
    assert "diff" in result
    assert result["diff"] is not None


def test_version_diff_not_found(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    docs_dir, _ = tmp_roots
    (docs_dir / "d.txt").write_text("x", encoding="utf-8")
    mcp, _ = _setup(make_config())
    with pytest.raises(VersioningError, match="not found"):
        _tool(mcp, "version_diff")(path="documents:/d.txt", version_id=99999)


def test_version_restore(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    docs_dir, _ = tmp_roots
    (docs_dir / "r.txt").write_bytes(b"original")
    cfg = make_config()
    ctx = build_context(cfg)
    rec = ctx.versions.snapshot(root_name="documents", rel_path="r.txt", source=docs_dir / "r.txt", action="test")
    (docs_dir / "r.txt").write_bytes(b"changed")

    mcp = FastMCP(name="test")
    version.register(mcp, ctx)
    _tool(mcp, "version_restore")(path="documents:/r.txt", version_id=rec["id"])
    assert (docs_dir / "r.txt").read_bytes() == b"original"


def test_version_undo(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    docs_dir, _ = tmp_roots
    (docs_dir / "u.txt").write_bytes(b"v1")
    cfg = make_config()
    ctx = build_context(cfg)
    ctx.versions.snapshot(root_name="documents", rel_path="u.txt", source=docs_dir / "u.txt", action="write")
    (docs_dir / "u.txt").write_bytes(b"v2")
    ctx.versions.snapshot(root_name="documents", rel_path="u.txt", source=docs_dir / "u.txt", action="write")

    mcp = FastMCP(name="test")
    version.register(mcp, ctx)
    _tool(mcp, "version_undo")(path="documents:/u.txt")
    assert (docs_dir / "u.txt").read_bytes() == b"v1"


def test_version_undo_no_history(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    docs_dir, _ = tmp_roots
    (docs_dir / "empty.txt").write_text("x", encoding="utf-8")
    mcp, _ = _setup(make_config())
    with pytest.raises(VersioningError, match="No history"):
        _tool(mcp, "version_undo")(path="documents:/empty.txt")


def test_version_purge(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    mcp, _ = _setup(make_config())
    result = _tool(mcp, "version_purge")(older_than_days=30)
    assert "removed" in result
    assert result["removed"] >= 0


def test_version_diff_binary_file(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    from unittest.mock import patch
    from dokumen_pintar.context import build_context
    docs_dir, _ = tmp_roots
    f = docs_dir / "bin.dat"
    f.write_bytes(b"\x00\x01\x02\x03")
    cfg = make_config()
    ctx = build_context(cfg)
    ctx.versions.snapshot(root_name="documents", rel_path="bin.dat", source=f, action="write")
    f.write_bytes(b"\xff\xfe\xfd")
    ctx.versions.snapshot(root_name="documents", rel_path="bin.dat", source=f, action="write")
    mcp = FastMCP(name="test")
    version.register(mcp, ctx)
    # Force UnicodeDecodeError on read_text to hit the binary fallback
    with patch("dokumen_pintar.tools.version.read_text", side_effect=UnicodeDecodeError("utf-8", b"", 0, 1, "bad")):
        result = _tool(mcp, "version_diff")(path="documents:/bin.dat", version_id=1)
    assert result.get("binary") is True
    assert result.get("diff") is None


def test_version_restore_not_found(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    docs_dir, _ = tmp_roots
    (docs_dir / "rest.txt").write_text("x", encoding="utf-8")
    mcp, _ = _setup(make_config())
    with pytest.raises(VersioningError, match="not found"):
        _tool(mcp, "version_restore")(path="documents:/rest.txt", version_id=99999)
