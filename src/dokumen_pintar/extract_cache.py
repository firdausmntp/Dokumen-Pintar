"""SQLite-backed cache for handler ``extract_for_search`` results.

Plain-text content search re-parses every matching file on every call,
which is expensive for DOCX/XLSX/PDF in workspaces with many documents.
This cache stores the extracted text keyed by absolute path; entries
are invalidated whenever the file's ``(mtime, size)`` pair changes,
which is a cheap and reliable freshness signal that does not require
re-reading the file content.

The cache is best-effort: any I/O or sqlite error silently falls back
to the live extractor. It never blocks search behaviour.
"""

from __future__ import annotations

import sqlite3
import threading
from contextlib import closing
from pathlib import Path
from typing import Callable

_SCHEMA = """
CREATE TABLE IF NOT EXISTS extract_cache (
    abs_path TEXT PRIMARY KEY,
    mtime_ns INTEGER NOT NULL,
    size INTEGER NOT NULL,
    text TEXT NOT NULL,
    cached_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_extract_cache_age ON extract_cache (cached_at);
"""


class ExtractCache:
    """Mtime/size-keyed cache of extracted text per absolute path."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._lock = threading.Lock()
        try:
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
            with self._lock, closing(self._connect()) as conn, conn:
                conn.executescript(_SCHEMA)
            self._enabled = True
        except (OSError, sqlite3.Error):
            # Disabled cache silently degrades to a no-op pass-through.
            self._enabled = False

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def db_path(self) -> Path:
        return self._db_path

    def get_or_extract(
        self,
        path: Path,
        extractor: Callable[[Path], str],
    ) -> str:
        """Return cached text if fresh; otherwise call ``extractor`` and cache.

        Freshness key: ``(mtime_ns, size)``. Any failure on cache lookup
        or insert falls back to the live extractor without raising.
        """
        if not self._enabled:
            return extractor(path)

        try:
            stat = path.stat()
        except OSError:
            return extractor(path)
        mtime_ns = stat.st_mtime_ns
        size = stat.st_size
        key = str(path.resolve())

        # Lookup
        try:
            with self._lock, closing(self._connect()) as conn:
                row = conn.execute(
                    "SELECT mtime_ns, size, text FROM extract_cache WHERE abs_path=?",
                    (key,),
                ).fetchone()
            if row is not None and row[0] == mtime_ns and row[1] == size:
                return row[2]
        except sqlite3.Error:
            # Cache lookup failed - proceed with fresh extraction.
            pass

        # Miss / stale: extract live, then attempt to cache.
        text = extractor(path)
        try:
            import time

            with self._lock, closing(self._connect()) as conn, conn:
                conn.execute(
                    "INSERT OR REPLACE INTO extract_cache"
                    "(abs_path, mtime_ns, size, text, cached_at) VALUES (?,?,?,?,?)",
                    (key, mtime_ns, size, text, int(time.time())),
                )
        except sqlite3.Error:
            pass
        return text

    def invalidate(self, path: Path) -> None:
        """Drop the cache entry for ``path`` (best-effort)."""
        if not self._enabled:
            return
        key = str(path.resolve())
        try:
            with self._lock, closing(self._connect()) as conn, conn:
                conn.execute("DELETE FROM extract_cache WHERE abs_path=?", (key,))
        except sqlite3.Error:
            pass

    def clear(self) -> int:
        """Drop all cached entries. Returns the row count removed."""
        if not self._enabled:
            return 0
        try:
            with self._lock, closing(self._connect()) as conn, conn:
                cur = conn.execute("DELETE FROM extract_cache")
                return cur.rowcount
        except sqlite3.Error:
            return 0

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn
