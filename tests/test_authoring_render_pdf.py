"""Tests for :mod:`dokumen_pintar.authoring.render_pdf`."""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

import pytest

from dokumen_pintar.authoring.render_pdf import render_pdf
from dokumen_pintar.authoring.spec import validate_spec
from dokumen_pintar.errors import HandlerError


def _png_bytes(width: int = 4, height: int = 4) -> bytes:
    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = chunk(
        b"IHDR",
        struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0),
    )
    raw = b""
    for _ in range(height):
        raw += b"\x00" + b"\xff\xff\xff" * width
    idat = chunk(b"IDAT", zlib.compress(raw))
    iend = chunk(b"IEND", b"")
    return sig + ihdr + idat + iend


def test_render_full_doc_pdf(tmp_path: Path) -> None:
    img = tmp_path / "tiny.png"
    img.write_bytes(_png_bytes())
    spec = validate_spec(
        {
            "meta": {"title": "T", "author": "A", "subject": "S", "keywords": "k"},
            "blocks": [
                {"type": "heading", "level": 1, "text": "Title"},
                {
                    "type": "paragraph",
                    "runs": [
                        {"text": "Hello "},
                        {"text": "bold", "bold": True},
                        {"text": " "},
                        {"text": "italic", "italic": True},
                        {"text": " "},
                        {"text": "code", "code": True},
                        {"text": " "},
                        {"text": "big", "font_size": 14},
                        {"text": " "},
                        {"text": "red", "color": "#ff0000"},
                    ],
                },
                {"type": "list", "items": ["a", "b"]},
                {"type": "list", "ordered": True, "items": ["one", "two"]},
                {"type": "table", "header": ["A", "B"], "rows": [["1", "2"]]},
                {
                    "type": "image",
                    "path": str(img),
                    "width_cm": 2,
                    "caption": "cap",
                },
                {"type": "page_break"},
                {"type": "code", "text": "print('x')\n"},
                {"type": "math", "latex": "E=mc^2"},
                {"type": "hr"},
                {"type": "blockquote", "text": "wisdom"},
            ],
        }
    )
    out = tmp_path / "out.pdf"
    render_pdf(spec, out)
    assert out.exists()
    # PDF magic bytes.
    assert out.read_bytes()[:4] == b"%PDF"


def test_pdf_image_not_found(tmp_path: Path) -> None:
    spec = validate_spec(
        {"blocks": [{"type": "image", "path": str(tmp_path / "nope.png")}]}
    )
    with pytest.raises(HandlerError, match="image not found"):
        render_pdf(spec, tmp_path / "x.pdf")


def test_pdf_path_resolver(tmp_path: Path) -> None:
    img = tmp_path / "real.png"
    img.write_bytes(_png_bytes())

    def resolver(uri: str) -> Path:
        return img if uri == "uri:/img.png" else Path(uri)

    spec = validate_spec(
        {"blocks": [{"type": "image", "path": "uri:/img.png", "width_cm": 2}]}
    )
    out = tmp_path / "x.pdf"
    render_pdf(spec, out, path_resolver=resolver)
    assert out.exists()


def test_pdf_table_without_header(tmp_path: Path) -> None:
    spec = validate_spec(
        {"blocks": [{"type": "table", "rows": [["1", "2"], ["3", "4"]]}]}
    )
    out = tmp_path / "no-header.pdf"
    render_pdf(spec, out)
    assert out.exists()


def test_pdf_empty_table(tmp_path: Path) -> None:
    spec = validate_spec({"blocks": [{"type": "table", "rows": []}]})
    out = tmp_path / "empty.pdf"
    render_pdf(spec, out)
    assert out.exists()


def test_pdf_unsupported_block_unreachable(tmp_path: Path) -> None:
    from dokumen_pintar.authoring.render_pdf import _render_block, _styles

    out: list = []
    with pytest.raises(HandlerError, match="unsupported block type"):
        _render_block(
            {"type": "marquee"},
            styles=_styles(),
            path_resolver=None,
            out=out,
        )


def test_pdf_build_failure_wrapped(tmp_path: Path, monkeypatch) -> None:
    spec = validate_spec({"blocks": [{"type": "heading", "text": "x"}]})
    from reportlab.platypus import SimpleDocTemplate

    def boom(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("layout boom")

    monkeypatch.setattr(SimpleDocTemplate, "build", boom)
    with pytest.raises(HandlerError, match="failed to write pdf"):
        render_pdf(spec, tmp_path / "x.pdf")
