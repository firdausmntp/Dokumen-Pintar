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


def read_text(
    path: Path, *, encoding: str | None = None, auto_detect: bool = True
) -> tuple[str, str]:
    raw = path.read_bytes()
    enc = encoding or (detect_encoding(raw) if auto_detect else "utf-8")
    return raw.decode(enc, errors="replace"), enc


def write_text(path: Path, content: str, *, encoding: str = "utf-8", newline: str = "\n") -> None:
    if newline == "":
        # Caller owns line terminators (e.g. the CSV writer); write content verbatim.
        path.write_bytes(content.encode(encoding))
        return
    normalized = content.replace("\r\n", "\n").replace("\r", "\n")
    if newline != "\n":
        normalized = normalized.replace("\n", newline)
    path.write_bytes(normalized.encode(encoding))
