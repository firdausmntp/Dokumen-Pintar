"""Tests for :mod:`dokumen_pintar.utils.mime`."""

from __future__ import annotations

from pathlib import Path

from dokumen_pintar.utils.mime import EXTENSION_MAP, detect_format


def test_extension_map_has_common_formats() -> None:
    assert EXTENSION_MAP[".txt"] == "text"
    assert EXTENSION_MAP[".json"] == "json"
    assert EXTENSION_MAP[".csv"] == "csv"
    assert EXTENSION_MAP[".pdf"] == "pdf"
    assert EXTENSION_MAP[".docx"] == "docx"
    assert EXTENSION_MAP[".xlsx"] == "xlsx"
    assert EXTENSION_MAP[".pptx"] == "pptx"


def test_detect_format_by_extension() -> None:
    assert detect_format(Path("test.json")) == "json"
    assert detect_format(Path("test.yaml")) == "yaml"
    assert detect_format(Path("test.yml")) == "yaml"
    assert detect_format(Path("test.xml")) == "xml"
    assert detect_format(Path("test.py")) == "text"
    assert detect_format(Path("test.csv")) == "csv"


def test_detect_format_unknown_extension() -> None:
    assert detect_format(Path("test.xyz")) == "binary"


def test_detect_format_pdf_magic_bytes(tmp_path: Path) -> None:
    target = tmp_path / "no_ext"
    target.write_bytes(b"%PDF-1.4 fake content")
    fmt = detect_format(target, sniff_bytes=True)
    assert fmt == "pdf"


def test_detect_format_sniff_unknown_magic(tmp_path: Path) -> None:
    target = tmp_path / "mystery"
    target.write_bytes(b"\x00\x01\x02\x03random bytes")
    fmt = detect_format(target, sniff_bytes=True)
    assert fmt == "binary"


def test_detect_format_zip_office_magic_returns_binary(tmp_path: Path) -> None:
    target = tmp_path / "no_ext"
    target.write_bytes(b"PK\x03\x04fake zip")
    fmt = detect_format(target, sniff_bytes=True)
    assert fmt == "binary"


def test_detect_format_case_insensitive() -> None:
    assert detect_format(Path("TEST.JSON")) == "json"
    assert detect_format(Path("TEST.PDF")) == "pdf"


def test_detect_format_nonexistent_sniff(tmp_path: Path) -> None:
    target = tmp_path / "nonexistent"
    fmt = detect_format(target, sniff_bytes=True)
    assert fmt == "binary"


def test_detect_format_sniff_oserror(tmp_path: Path) -> None:
    from unittest.mock import patch
    target = tmp_path / "oserr"
    target.write_bytes(b"data")
    with patch("pathlib.Path.read_bytes", side_effect=OSError("no read")):
        fmt = detect_format(target, sniff_bytes=True)
    assert fmt == "binary"
