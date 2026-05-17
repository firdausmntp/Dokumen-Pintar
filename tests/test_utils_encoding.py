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



# ── v1.1.0 Bug 1.2: line ending preservation ──


def test_detect_line_ending_crlf() -> None:
    from dokumen_pintar.utils.encoding import detect_line_ending

    assert detect_line_ending(b"line1\r\nline2\r\nline3\r\n") == "\r\n"


def test_detect_line_ending_lf() -> None:
    from dokumen_pintar.utils.encoding import detect_line_ending

    assert detect_line_ending(b"line1\nline2\nline3\n") == "\n"


def test_detect_line_ending_cr_only_classic_mac() -> None:
    from dokumen_pintar.utils.encoding import detect_line_ending

    assert detect_line_ending(b"line1\rline2\rline3\r") == "\r"


def test_detect_line_ending_no_terminators_uses_default() -> None:
    from dokumen_pintar.utils.encoding import detect_line_ending

    assert detect_line_ending(b"single line no terminator") == "\n"
    assert detect_line_ending(b"", default="\r\n") == "\r\n"


def test_detect_line_ending_str_input_encoded() -> None:
    """``str`` is UTF-8-encoded internally before counting bytes."""
    from dokumen_pintar.utils.encoding import detect_line_ending

    assert detect_line_ending("a\r\nb\r\n") == "\r\n"


def test_detect_line_ending_mixed_picks_majority() -> None:
    from dokumen_pintar.utils.encoding import detect_line_ending

    # 3 CRLF, 1 LF: CRLF wins.
    assert detect_line_ending(b"a\r\nb\r\nc\r\nd\ne") == "\r\n"
    # 1 CRLF, 3 LF: LF wins.
    assert detect_line_ending(b"a\r\nb\nc\nd\ne") == "\n"


def test_read_text_with_eol_crlf(tmp_path: Path) -> None:
    """``read_text_with_eol`` returns the file's line ending."""
    from dokumen_pintar.utils.encoding import read_text_with_eol

    target = tmp_path / "win.txt"
    target.write_bytes(b"line1\r\nline2\r\n")
    text, enc, eol = read_text_with_eol(target)
    assert text == "line1\r\nline2\r\n"
    assert enc == "utf-8"
    assert eol == "\r\n"


def test_read_text_with_eol_lf(tmp_path: Path) -> None:
    from dokumen_pintar.utils.encoding import read_text_with_eol

    target = tmp_path / "unix.txt"
    target.write_bytes(b"a\nb\nc\n")
    _text, _enc, eol = read_text_with_eol(target)
    assert eol == "\n"


def test_read_text_with_eol_explicit_encoding(tmp_path: Path) -> None:
    """Caller-supplied encoding bypasses auto-detection."""
    from dokumen_pintar.utils.encoding import read_text_with_eol

    target = tmp_path / "explicit.txt"
    target.write_bytes("héllo\n".encode("latin-1"))
    text, enc, eol = read_text_with_eol(target, encoding="latin-1", auto_detect=False)
    assert text == "héllo\n"
    assert enc == "latin-1"
    assert eol == "\n"
