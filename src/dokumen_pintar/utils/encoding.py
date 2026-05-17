"""Encoding detection + safe text I/O."""

from __future__ import annotations

from pathlib import Path

# charset-normalizer is *not* imported at module load — it costs ~50ms per
# import and we only need it for non-ASCII files.  Lazy via _slow_detect().


def _is_ascii(data: bytes) -> bool:
    """Fast pure-Python ASCII probe; ~10x faster than charset-normalizer."""
    # bytes < 0x80 are ASCII; anything else triggers full detection.
    return not any(b & 0x80 for b in data)


def _slow_detect(data: bytes, default: str) -> str:
    try:
        from charset_normalizer import from_bytes  # local import

        results = from_bytes(data[:65536])
        best = results.best()
        if best is not None:
            return best.encoding or default
    except Exception:  # pragma: no cover
        pass
    return default


def detect_encoding(data: bytes, default: str = "utf-8") -> str:
    if not data:
        return default
    # Fast paths
    if data.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"
    if data.startswith(b"\xff\xfe") or data.startswith(b"\xfe\xff"):
        return "utf-16"
    # Sample first 4KB only — files are overwhelmingly homogeneous.
    sample = data[:4096]
    if _is_ascii(sample):
        return "utf-8"
    return _slow_detect(data, default)


def detect_line_ending(data: bytes | str, default: str = "\n") -> str:
    """Detect the predominant line ending in ``data``.

    Returns one of ``"\\r\\n"``, ``"\\r"``, ``"\\n"``. ``default`` is
    returned when the input has no line terminators at all - we cannot
    sensibly preserve what isn't there. ``str`` input is encoded as
    UTF-8 before counting, which is loss-free for the byte sequences
    we care about (CR, LF).
    """
    if isinstance(data, str):
        data = data.encode("utf-8", errors="replace")
    crlf = data.count(b"\r\n")
    lf = data.count(b"\n") - crlf
    cr = data.count(b"\r") - crlf
    if crlf == 0 and lf == 0 and cr == 0:
        return default
    if crlf >= lf and crlf >= cr:
        return "\r\n"
    if cr > lf:
        return "\r"
    return "\n"


def read_text(
    path: Path, *, encoding: str | None = None, auto_detect: bool = True
) -> tuple[str, str]:
    raw = path.read_bytes()
    enc = encoding or (detect_encoding(raw) if auto_detect else "utf-8")
    return raw.decode(enc, errors="replace"), enc


def read_text_with_eol(
    path: Path, *, encoding: str | None = None, auto_detect: bool = True
) -> tuple[str, str, str]:
    """Like :func:`read_text` but also returns the file's line ending.

    Returns ``(text, encoding, line_ending)`` where ``line_ending`` is
    one of ``"\\r\\n"``, ``"\\r"``, ``"\\n"``. Callers that mutate
    text and write it back should pass the returned line ending to
    :func:`write_text` to keep the on-disk representation stable.
    """
    raw = path.read_bytes()
    enc = encoding or (detect_encoding(raw) if auto_detect else "utf-8")
    eol = detect_line_ending(raw)
    return raw.decode(enc, errors="replace"), enc, eol


def write_text(path: Path, content: str, *, encoding: str = "utf-8", newline: str = "\n") -> None:
    if newline == "":
        # Caller owns line terminators (e.g. the CSV writer); write content verbatim.
        path.write_bytes(content.encode(encoding))
        return
    normalized = content.replace("\r\n", "\n").replace("\r", "\n")
    if newline != "\n":
        normalized = normalized.replace("\n", newline)
    path.write_bytes(normalized.encode(encoding))
