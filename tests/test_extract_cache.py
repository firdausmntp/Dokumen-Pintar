"""Unit tests for the extract_cache subsystem."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest

from dokumen_pintar.extract_cache import ExtractCache


def test_init_creates_db(tmp_path: Path) -> None:
    db = tmp_path / "sub" / "ec.sqlite"
    cache = ExtractCache(db)
    assert cache.enabled is True
    assert db.exists()
    assert cache.db_path == db


def test_init_disabled_on_oserror(tmp_path: Path) -> None:
    """If we cannot create the parent dir or db, cache is disabled but never raises."""
    bad = tmp_path / "no" / "such" / "dir" / "ec.sqlite"
    with patch.object(Path, "mkdir", side_effect=OSError("read-only")):
        cache = ExtractCache(bad)
    assert cache.enabled is False


def test_get_or_extract_cache_miss_then_hit(tmp_path: Path) -> None:
    db = tmp_path / "ec.sqlite"
    cache = ExtractCache(db)
    target = tmp_path / "doc.txt"
    target.write_text("hello world", encoding="utf-8")

    calls = {"n": 0}

    def extractor(p: Path) -> str:
        calls["n"] += 1
        return f"extracted:{p.read_text()}"

    # First call: miss → extractor invoked.
    text1 = cache.get_or_extract(target, extractor)
    assert text1 == "extracted:hello world"
    assert calls["n"] == 1

    # Second call (no change): hit → extractor NOT invoked again.
    text2 = cache.get_or_extract(target, extractor)
    assert text2 == "extracted:hello world"
    assert calls["n"] == 1


def test_get_or_extract_invalidated_on_mtime_change(tmp_path: Path) -> None:
    """A file edit (mtime/size change) must invalidate the cached entry."""
    import os
    import time

    db = tmp_path / "ec.sqlite"
    cache = ExtractCache(db)
    target = tmp_path / "doc.txt"
    target.write_text("v1", encoding="utf-8")

    calls = {"n": 0}

    def extractor(p: Path) -> str:
        calls["n"] += 1
        return f"v={p.read_text()}"

    assert cache.get_or_extract(target, extractor) == "v=v1"

    # Force a different mtime (mtime resolution can be 1s on some filesystems).
    time.sleep(0.05)
    target.write_text("v2_with_more_bytes", encoding="utf-8")
    # Bump mtime explicitly to be safe across FS resolutions.
    new_time = target.stat().st_mtime + 5
    os.utime(target, (new_time, new_time))

    assert cache.get_or_extract(target, extractor) == "v=v2_with_more_bytes"
    assert calls["n"] == 2


def test_get_or_extract_disabled_passthrough(tmp_path: Path) -> None:
    bad = tmp_path / "x" / "y" / "ec.sqlite"
    with patch.object(Path, "mkdir", side_effect=OSError("read-only")):
        cache = ExtractCache(bad)
    target = tmp_path / "doc.txt"
    target.write_text("hi", encoding="utf-8")
    calls = {"n": 0}

    def extractor(p: Path) -> str:
        calls["n"] += 1
        return p.read_text()

    # Disabled cache always re-runs the extractor.
    assert cache.get_or_extract(target, extractor) == "hi"
    assert cache.get_or_extract(target, extractor) == "hi"
    assert calls["n"] == 2


def test_get_or_extract_missing_file_passthrough(tmp_path: Path) -> None:
    db = tmp_path / "ec.sqlite"
    cache = ExtractCache(db)
    missing = tmp_path / "nope.txt"
    calls = {"n": 0}

    def extractor(p: Path) -> str:
        calls["n"] += 1
        return "fallback"

    # stat() on missing path raises OSError → extractor called directly.
    assert cache.get_or_extract(missing, extractor) == "fallback"
    assert calls["n"] == 1


def test_get_or_extract_lookup_sqlite_error_falls_through(tmp_path: Path) -> None:
    db = tmp_path / "ec.sqlite"
    cache = ExtractCache(db)
    target = tmp_path / "doc.txt"
    target.write_text("body", encoding="utf-8")

    calls = {"n": 0}

    def extractor(p: Path) -> str:
        calls["n"] += 1
        return "live"

    # Make every connect() raise sqlite3.Error during lookup.
    with patch.object(ExtractCache, "_connect", side_effect=sqlite3.OperationalError("locked")):
        result = cache.get_or_extract(target, extractor)
    assert result == "live"
    assert calls["n"] == 1


def test_get_or_extract_insert_sqlite_error_silent(tmp_path: Path) -> None:
    """A failed cache write must not break the call - user still gets fresh text."""
    db = tmp_path / "ec.sqlite"
    cache = ExtractCache(db)
    target = tmp_path / "doc.txt"
    target.write_text("body", encoding="utf-8")

    real_connect = ExtractCache._connect
    state = {"calls": 0}

    def fail_on_insert(self):  # type: ignore[no-untyped-def]
        state["calls"] += 1
        # First connect = lookup (allowed); second = insert (fail).
        if state["calls"] >= 2:
            raise sqlite3.OperationalError("disk full")
        return real_connect(self)

    def extractor(_: Path) -> str:
        return "fresh"

    with patch.object(ExtractCache, "_connect", autospec=True, side_effect=fail_on_insert):
        text = cache.get_or_extract(target, extractor)
    assert text == "fresh"


def test_invalidate_drops_entry(tmp_path: Path) -> None:
    db = tmp_path / "ec.sqlite"
    cache = ExtractCache(db)
    target = tmp_path / "doc.txt"
    target.write_text("body", encoding="utf-8")

    calls = {"n": 0}

    def extractor(_: Path) -> str:
        calls["n"] += 1
        return "extracted"

    cache.get_or_extract(target, extractor)
    cache.invalidate(target)
    cache.get_or_extract(target, extractor)
    assert calls["n"] == 2  # invalidation forced re-extraction


def test_invalidate_disabled_noop(tmp_path: Path) -> None:
    with patch.object(Path, "mkdir", side_effect=OSError("ro")):
        cache = ExtractCache(tmp_path / "x" / "ec.sqlite")
    # Should not raise.
    cache.invalidate(tmp_path / "anything.txt")


def test_invalidate_sqlite_error_silent(tmp_path: Path) -> None:
    db = tmp_path / "ec.sqlite"
    cache = ExtractCache(db)
    with patch.object(ExtractCache, "_connect", side_effect=sqlite3.OperationalError("x")):
        cache.invalidate(tmp_path / "any.txt")  # must not raise


def test_clear_drops_all(tmp_path: Path) -> None:
    db = tmp_path / "ec.sqlite"
    cache = ExtractCache(db)
    a = tmp_path / "a.txt"
    b = tmp_path / "b.txt"
    a.write_text("aa", encoding="utf-8")
    b.write_text("bb", encoding="utf-8")
    cache.get_or_extract(a, lambda p: p.read_text())
    cache.get_or_extract(b, lambda p: p.read_text())
    removed = cache.clear()
    assert removed == 2
    assert cache.clear() == 0  # second clear is no-op


def test_clear_disabled_returns_zero(tmp_path: Path) -> None:
    with patch.object(Path, "mkdir", side_effect=OSError("ro")):
        cache = ExtractCache(tmp_path / "x" / "ec.sqlite")
    assert cache.clear() == 0


def test_clear_sqlite_error_returns_zero(tmp_path: Path) -> None:
    db = tmp_path / "ec.sqlite"
    cache = ExtractCache(db)
    with patch.object(ExtractCache, "_connect", side_effect=sqlite3.OperationalError("x")):
        assert cache.clear() == 0
