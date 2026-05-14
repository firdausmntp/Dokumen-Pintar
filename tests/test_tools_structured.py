"""Tests for :mod:`dokumen_pintar.tools.structured`."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from mcp.server.fastmcp import FastMCP

from dokumen_pintar.config import AppConfig
from dokumen_pintar.context import build_context
from dokumen_pintar.tools import structured


def _setup(cfg: AppConfig) -> tuple[FastMCP, ...]:
    ctx = build_context(cfg)
    mcp = FastMCP(name="test")
    structured.register(mcp, ctx)
    return mcp, ctx


def _tool(mcp: FastMCP, name: str):
    return mcp._tool_manager._tools[name].fn


def test_struct_get(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    docs_dir, _ = tmp_roots
    (docs_dir / "data.json").write_text('{"key": "value"}', encoding="utf-8")
    mcp, _ = _setup(make_config())
    result = _tool(mcp, "struct_get")(path="documents:/data.json", expr="$.key")
    assert result["result"] == "value"
    assert result["handler"] == "json"


def test_struct_set(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    docs_dir, _ = tmp_roots
    (docs_dir / "data.json").write_text('{"key": "old"}', encoding="utf-8")
    mcp, _ = _setup(make_config())
    _tool(mcp, "struct_set")(path="documents:/data.json", expr="$.key", value="new")
    result = _tool(mcp, "struct_get")(path="documents:/data.json", expr="$.key")
    assert result["result"] == "new"


def test_struct_delete(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    docs_dir, _ = tmp_roots
    (docs_dir / "data.json").write_text('{"a": 1, "b": 2}', encoding="utf-8")
    mcp, _ = _setup(make_config())
    _tool(mcp, "struct_delete")(path="documents:/data.json", expr="$.b")
    result = _tool(mcp, "struct_get")(path="documents:/data.json", expr="$.b")
    # After deletion, jsonpath returns [] for missing keys
    assert result["result"] == [] or result["result"] is None


def test_struct_meta(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    docs_dir, _ = tmp_roots
    (docs_dir / "info.txt").write_text("hello world\n", encoding="utf-8")
    mcp, _ = _setup(make_config())
    result = _tool(mcp, "struct_meta")(path="documents:/info.txt")
    assert result["handler"] == "text"
    assert "meta" in result
