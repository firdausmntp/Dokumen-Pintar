"""Tests for :mod:`dokumen_pintar.utils.encoding`."""

from __future__ import annotations

from pathlib import Path

from dokumen_pintar.utils.encoding import (
    _is_ascii,
    _slow_detect,
    detect_encoding,
    read_text,
    write_text,
)


def test_is_ascii_pure_ascii() -> None:
    assert _is_ascii(b"Hello World 123!") is True


def test_is_ascii_with_high_byte() -> None:
    assert _is_ascii(b"\xc3\xa9") is False  # é in UTF-8


def test_is_ascii_empty() -> None:
    assert _is_ascii(b"") is True


def test_detect_encoding_empty_returns_default() -> None:
    assert detect_encoding(b"") == "utf-8"
    assert detect_encoding(b"", default="latin-1") == "latin-1"


def test_detect_encoding_utf8_bom() -> None:
    assert detect_encoding(b"\xef\xbb\xbfhello") == "utf-8-sig"


def test_detect_encoding_utf16_le_bom() -> None:
    assert detect_encoding(b"\xff\xfeh\x00i\x00") == "utf-16"


def test_detect_encoding_utf16_be_bom() -> None:
    assert detect_encoding(b"\xfe\xffh\x00i\x00") == "utf-16"


def test_detect_encoding_plain_ascii_returns_utf8() -> None:
    assert detect_encoding(b"just ascii text") == "utf-8"


def test_detect_encoding_non_ascii_triggers_slow_detect() -> None:
    enc = detect_encoding("café".encode("latin-1"))
    assert isinstance(enc, str)
    assert len(enc) > 0


def test_slow_detect_returns_default_on_empty() -> None:
    result = _slow_detect(b"", "fallback")
    assert isinstance(result, str)


def test_read_text_roundtrip(tmp_path: Path) -> None:
    target = tmp_path / "rt.txt"
    target.write_bytes(b"hello\nworld\n")
    content, enc = read_text(target)
    assert content == "hello\nworld\n"
    assert enc == "utf-8"


def test_read_text_with_explicit_encoding(tmp_path: Path) -> None:
    target = tmp_path / "enc.txt"
    target.write_bytes("héllo".encode("latin-1"))
    content, enc = read_text(target, encoding="latin-1")
    assert "héllo" in content
    assert enc == "latin-1"


def test_write_text_default_newline(tmp_path: Path) -> None:
    target = tmp_path / "out.txt"
    write_text(target, "a\r\nb\rc\n")
    raw = target.read_bytes()
    assert b"\r\n" not in raw
    assert b"\r" not in raw


def test_write_text_crlf_newline(tmp_path: Path) -> None:
    target = tmp_path / "crlf.txt"
    write_text(target, "a\nb\n", newline="\r\n")
    raw = target.read_bytes()
    assert raw == b"a\r\nb\r\n"


def test_write_text_empty_newline_verbatim(tmp_path: Path) -> None:
    target = tmp_path / "verbatim.txt"
    content = "a\r\nb\n"
    write_text(target, content, newline="")
    raw = target.read_bytes()
    assert raw == content.encode("utf-8")


def test_slow_detect_best_none() -> None:
    from unittest.mock import patch, MagicMock
    mock_result = MagicMock()
    mock_result.best.return_value = None
    with patch("charset_normalizer.from_bytes", return_value=mock_result):
        result = _slow_detect(b"\x80\x81\x82", "fallback-enc")
    assert result == "fallback-enc"
