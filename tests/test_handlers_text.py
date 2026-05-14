"""Tests for :class:`dokumen_pintar.handlers.text_handler.TextHandler`."""

from __future__ import annotations

from pathlib import Path

import pytest

from dokumen_pintar.errors import UnsupportedFormatError
from dokumen_pintar.handlers.text_handler import TextHandler


@pytest.fixture
def handler() -> TextHandler:
    return TextHandler()


def test_detect_txt_and_py(handler: TextHandler, tmp_path: Path) -> None:
    assert handler.detect(tmp_path / "a.txt") is True
    assert handler.detect(tmp_path / "b.py") is True
    assert handler.detect(tmp_path / "c.pdf") is False


def test_read_write_unicode_roundtrip(handler: TextHandler, tmp_path: Path) -> None:
    target = tmp_path / "u.txt"
    content = "Halo 🌏 — αβγ — 你好\n"
    handler.write_text(target, content)
    read_back = handler.read_text(target)
    assert read_back == content


def test_read_meta_returns_expected_keys(handler: TextHandler, tmp_path: Path) -> None:
    target = tmp_path / "meta.txt"
    target.write_text("line1\nline2\nline3\n", encoding="utf-8")
    meta = handler.read_meta(target)

    for key in ("format", "size", "mtime", "encoding", "line_count", "suffix"):
        assert key in meta
    assert meta["format"] == "text"
    assert meta["suffix"] == ".txt"
    assert meta["size"] > 0
    assert meta["line_count"] >= 3


def test_structured_get_raises_unsupported(handler: TextHandler, tmp_path: Path) -> None:
    target = tmp_path / "unsupported.txt"
    target.write_text("content", encoding="utf-8")
    with pytest.raises(UnsupportedFormatError):
        handler.structured_get(target, "$.anything")


def test_structured_set_raises_unsupported(handler: TextHandler, tmp_path: Path) -> None:
    target = tmp_path / "unsupported.txt"
    target.write_text("content", encoding="utf-8")
    with pytest.raises(UnsupportedFormatError):
        handler.structured_set(target, "$.anything", "v")


def test_structured_delete_raises_unsupported(handler: TextHandler, tmp_path: Path) -> None:
    target = tmp_path / "unsupported.txt"
    target.write_text("content", encoding="utf-8")
    with pytest.raises(UnsupportedFormatError):
        handler.structured_delete(target, "$.anything")


def test_extract_for_search(handler: TextHandler, tmp_path: Path) -> None:
    target = tmp_path / "search.txt"
    target.write_text("findme content", encoding="utf-8")
    assert "findme" in handler.extract_for_search(target)


def test_extract_for_search_missing_file(handler: TextHandler, tmp_path: Path) -> None:
    target = tmp_path / "gone.txt"
    assert handler.extract_for_search(target) == ""


def test_read_meta_no_trailing_newline(handler: TextHandler, tmp_path: Path) -> None:
    target = tmp_path / "notl.txt"
    target.write_text("single line no newline", encoding="utf-8")
    meta = handler.read_meta(target)
    assert meta["line_count"] == 1


def test_read_meta_decode_exception(handler: TextHandler, tmp_path: Path) -> None:
    from unittest.mock import patch
    target = tmp_path / "decfail.txt"
    target.write_bytes(b"hello\nworld\n")
    # Patch detect_encoding at the source module so the lazy import finds it
    with patch("dokumen_pintar.utils.encoding.detect_encoding", return_value="not-a-real-encoding-999"):
        meta = handler.read_meta(target)
        assert meta["line_count"] == 0
