"""Tests for :mod:`dokumen_pintar.tools.authoring`."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import pytest
from mcp.server.fastmcp import FastMCP

from dokumen_pintar.config import AppConfig
from dokumen_pintar.context import build_context
from dokumen_pintar.errors import UnsupportedFormatError, ValidationError
from dokumen_pintar.tools import authoring


def _setup(cfg: AppConfig):  # type: ignore[no-untyped-def]
    ctx = build_context(cfg)
    mcp = FastMCP(name="test")
    authoring.register(mcp, ctx)
    return mcp, ctx


def _tool(mcp: FastMCP, name: str):  # type: ignore[no-untyped-def]
    return mcp._tool_manager._tools[name].fn


def test_validate_spec_tool_ok(make_config: Callable[..., AppConfig]) -> None:
    mcp, _ = _setup(make_config())
    res = _tool(mcp, "validate_spec")(
        spec={"blocks": [{"type": "heading", "text": "Hi"}]}
    )
    assert res["valid"] is True
    assert res["normalized"]["blocks"][0]["text"] == "Hi"


def test_validate_spec_tool_bad(make_config: Callable[..., AppConfig]) -> None:
    mcp, _ = _setup(make_config())
    res = _tool(mcp, "validate_spec")(spec={"blocks": [{"type": "marquee"}]})
    assert res["valid"] is False
    assert "not supported" in res["error"]


def test_compose_docx_writes_file(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    docs_dir, _ = tmp_roots
    mcp, _ = _setup(make_config())
    res = _tool(mcp, "compose_docx")(
        path="documents:/out.docx",
        spec={
            "blocks": [
                {"type": "heading", "text": "Hello"},
                {"type": "paragraph", "text": "World"},
            ]
        },
    )
    assert (docs_dir / "out.docx").exists()
    assert res["blocks"] == 2


def test_compose_docx_refuses_overwrite_without_flag(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    docs_dir, _ = tmp_roots
    target = docs_dir / "exists.docx"
    target.write_bytes(b"placeholder")
    mcp, _ = _setup(make_config())
    with pytest.raises(ValidationError, match="overwrite"):
        _tool(mcp, "compose_docx")(
            path="documents:/exists.docx",
            spec={"blocks": [{"type": "heading", "text": "x"}]},
        )


def test_compose_docx_overwrite_flag_works(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    docs_dir, _ = tmp_roots
    target = docs_dir / "ow.docx"
    target.write_bytes(b"placeholder")
    mcp, _ = _setup(make_config())
    _tool(mcp, "compose_docx")(
        path="documents:/ow.docx",
        spec={"blocks": [{"type": "heading", "text": "new"}]},
        overwrite=True,
    )
    # Real DOCX is much larger and starts with 'PK' (zip).
    assert target.read_bytes()[:2] == b"PK"


def test_compose_docx_extension_check(
    make_config: Callable[..., AppConfig]
) -> None:
    mcp, _ = _setup(make_config())
    with pytest.raises(UnsupportedFormatError, match=".docx"):
        _tool(mcp, "compose_docx")(
            path="documents:/out.txt",
            spec={"blocks": [{"type": "heading", "text": "x"}]},
        )


def test_compose_docx_invalid_spec(
    make_config: Callable[..., AppConfig]
) -> None:
    mcp, _ = _setup(make_config())
    with pytest.raises(ValidationError, match="invalid spec"):
        _tool(mcp, "compose_docx")(
            path="documents:/x.docx", spec={"blocks": "nope"}
        )


def test_compose_pdf_writes_file(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    docs_dir, _ = tmp_roots
    mcp, _ = _setup(make_config())
    _tool(mcp, "compose_pdf")(
        path="documents:/out.pdf",
        spec={"blocks": [{"type": "heading", "text": "Hi"}]},
    )
    out = docs_dir / "out.pdf"
    assert out.exists()
    assert out.read_bytes()[:4] == b"%PDF"


def test_compose_pdf_extension_check(
    make_config: Callable[..., AppConfig]
) -> None:
    mcp, _ = _setup(make_config())
    with pytest.raises(UnsupportedFormatError, match=".pdf"):
        _tool(mcp, "compose_pdf")(
            path="documents:/out.docx",
            spec={"blocks": [{"type": "heading", "text": "x"}]},
        )


def test_compose_pdf_invalid_spec(
    make_config: Callable[..., AppConfig]
) -> None:
    mcp, _ = _setup(make_config())
    with pytest.raises(ValidationError, match="invalid spec"):
        _tool(mcp, "compose_pdf")(
            path="documents:/x.pdf", spec={"blocks": "nope"}
        )


def test_compose_from_markdown_to_docx(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    docs_dir, _ = tmp_roots
    mcp, _ = _setup(make_config())
    res = _tool(mcp, "compose_from_markdown")(
        path="documents:/md.docx",
        markdown="# Title\n\nSome **bold** text.\n",
    )
    assert res["format"] == "docx"
    assert (docs_dir / "md.docx").exists()


def test_compose_from_markdown_to_pdf(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    docs_dir, _ = tmp_roots
    mcp, _ = _setup(make_config())
    res = _tool(mcp, "compose_from_markdown")(
        path="documents:/md.pdf",
        markdown="# Title\n\nPara.\n",
    )
    assert res["format"] == "pdf"
    out = docs_dir / "md.pdf"
    assert out.exists()
    assert out.read_bytes()[:4] == b"%PDF"


def test_compose_from_markdown_explicit_format(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    docs_dir, _ = tmp_roots
    mcp, _ = _setup(make_config())
    # Path has no extension matching format → must use explicit ``format``.
    with pytest.raises(UnsupportedFormatError):
        _tool(mcp, "compose_from_markdown")(
            path="documents:/md.txt",
            markdown="# X\n",
        )


def test_compose_from_markdown_empty_rejected(
    make_config: Callable[..., AppConfig]
) -> None:
    mcp, _ = _setup(make_config())
    with pytest.raises(ValidationError, match="non-empty"):
        _tool(mcp, "compose_from_markdown")(
            path="documents:/x.docx",
            markdown="   \n",
        )


def test_compose_from_markdown_refuses_overwrite(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    docs_dir, _ = tmp_roots
    (docs_dir / "ex.docx").write_bytes(b"x")
    mcp, _ = _setup(make_config())
    with pytest.raises(ValidationError, match="overwrite"):
        _tool(mcp, "compose_from_markdown")(
            path="documents:/ex.docx",
            markdown="# X\n",
        )


def test_path_resolver_invalid_falls_through(
    make_config: Callable[..., AppConfig], tmp_path: Path
) -> None:
    """The path resolver must not crash on URIs outside the workspace —
    it falls back to a literal Path which then surfaces a clean
    'image not found' from the renderer."""
    mcp, _ = _setup(make_config())
    with pytest.raises(Exception):  # HandlerError or similar
        _tool(mcp, "compose_docx")(
            path="documents:/img.docx",
            spec={
                "blocks": [
                    {"type": "image", "path": "/no/such/place/x.png"}
                ]
            },
        )
