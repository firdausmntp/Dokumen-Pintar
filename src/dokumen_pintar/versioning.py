"""Copy-on-write versioning with SQLite index and flexible storage."""

from __future__ import annotations

import hashlib
import shutil
import sqlite3
import threading
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Iterable

from .config import AppConfig
from .errors import VersioningError


_SCHEMA = """
CREATE TABLE IF NOT EXISTS versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    root_name TEXT NOT NULL,
    rel_path TEXT NOT NULL,
    snapshot_path TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    size INTEGER NOT NULL,
    timestamp TEXT NOT NULL,
    action TEXT NOT NULL,
    note TEXT
);
CREATE INDEX IF NOT EXISTS idx_versions_path ON versions (root_name, rel_path, id DESC);
CREATE INDEX IF NOT EXISTS idx_versions_ts ON versions (timestamp);
"""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S-%fZ")


class VersionStore:
    """Manages per-root (with global fallback) snapshots."""

    def __init__(
        self,
        config: AppConfig,
        *,
        per_root_dirs: dict[str, Path],
        global_dir: Path,
    ):
        self._config = config
        self._per_root_dirs = per_root_dirs
        self._global_dir = global_dir
        self._db_lock = threading.Lock()
        self._db_path = global_dir / "index.sqlite"
        global_dir.mkdir(parents=True, exist_ok=True)
        self._init_db()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    @property
    def enabled(self) -> bool:
        return self._config.versioning.enabled

    def snapshot(
        self,
        *,
        root_name: str,
        rel_path: str,
        source: Path,
        action: str,
        note: str | None = None,
    ) -> dict | None:
        if not self.enabled:
            return None
        if not source.exists() or not source.is_file():
            return None

        data = source.read_bytes()
        digest = _sha256(data)
        latest = self.latest(root_name=root_name, rel_path=rel_path)
        if latest and latest["sha256"] == digest and action != "delete":
            # No change, skip snapshot.
            return latest

        ts = _timestamp()
        safe_rel = rel_path.replace("/", "__").replace("\\", "__")
        snap_dir = self._storage_for(root_name) / "versions" / safe_rel
        snap_dir.mkdir(parents=True, exist_ok=True)
        snap_file = snap_dir / f"{ts}_{digest[:12]}{source.suffix}"
        snap_file.write_bytes(data)

        record = {
            "root_name": root_name,
            "rel_path": rel_path,
            "snapshot_path": str(snap_file),
            "sha256": digest,
            "size": len(data),
            "timestamp": ts,
            "action": action,
            "note": note,
        }
        with self._db_lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO versions(root_name, rel_path, snapshot_path, sha256, size, timestamp, action, note)"
                " VALUES (?,?,?,?,?,?,?,?)",
                (
                    record["root_name"],
                    record["rel_path"],
                    record["snapshot_path"],
                    record["sha256"],
                    record["size"],
                    record["timestamp"],
                    record["action"],
                    record["note"],
                ),
            )
            rid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            record["id"] = rid
        self._enforce_retention(root_name=root_name, rel_path=rel_path)
        return record

    def list_versions(self, *, root_name: str, rel_path: str) -> list[dict]:
        with self._db_lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT id, root_name, rel_path, snapshot_path, sha256, size, timestamp, action, note"
                " FROM versions WHERE root_name=? AND rel_path=? ORDER BY id DESC",
                (root_name, rel_path),
            ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def latest(self, *, root_name: str, rel_path: str) -> dict | None:
        with self._db_lock, self._connect() as conn:
            row = conn.execute(
                "SELECT id, root_name, rel_path, snapshot_path, sha256, size, timestamp, action, note"
                " FROM versions WHERE root_name=? AND rel_path=? ORDER BY id DESC LIMIT 1",
                (root_name, rel_path),
            ).fetchone()
        return self._row_to_dict(row) if row else None

    def get(self, version_id: int) -> dict | None:
        with self._db_lock, self._connect() as conn:
            row = conn.execute(
                "SELECT id, root_name, rel_path, snapshot_path, sha256, size, timestamp, action, note"
                " FROM versions WHERE id=?",
                (version_id,),
            ).fetchone()
        return self._row_to_dict(row) if row else None

    def restore(self, version_id: int, target: Path) -> dict:
        rec = self.get(version_id)
        if rec is None:
            raise VersioningError(f"Version id {version_id} not found")
        snap = Path(rec["snapshot_path"])
        if not snap.exists():
            raise VersioningError(f"Snapshot file missing: {snap}")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(snap, target)
        return rec

    def purge(self, *, older_than_days: int | None = None) -> int:
        days = (
            older_than_days
            if older_than_days is not None
            else self._config.versioning.retention_days
        )
        if days <= 0:
            return 0
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        cutoff_str = cutoff.strftime("%Y-%m-%dT%H-%M-%S-%fZ")
        removed = 0
        with self._db_lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT id, snapshot_path FROM versions WHERE timestamp < ?",
                (cutoff_str,),
            ).fetchall()
            for rid, snap_path in rows:
                try:
                    Path(snap_path).unlink(missing_ok=True)
                except OSError:  # pragma: no cover
                    pass
                conn.execute("DELETE FROM versions WHERE id=?", (rid,))
                removed += 1
        return removed

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _storage_for(self, root_name: str) -> Path:
        mode = self._config.versioning.storage_mode
        per_root = self._per_root_dirs.get(root_name)
        if mode == "global" or per_root is None:
            return self._global_dir
        if mode == "per_root":
            return per_root
        # flexible: per-root preferred, global as fallback.
        try:
            per_root.mkdir(parents=True, exist_ok=True)
            # Probe writability
            probe = per_root / ".write-probe"
            probe.write_bytes(b"")
            probe.unlink()
            return per_root
        except OSError:
            return self._global_dir

    def _enforce_retention(self, *, root_name: str, rel_path: str) -> None:
        max_v = self._config.versioning.max_versions_per_file
        if max_v <= 0:
            return
        with self._db_lock, self._connect() as conn:
            ids = [
                r[0]
                for r in conn.execute(
                    "SELECT id FROM versions WHERE root_name=? AND rel_path=? ORDER BY id DESC",
                    (root_name, rel_path),
                ).fetchall()
            ]
            stale = ids[max_v:]
            for vid in stale:
                snap = conn.execute(
                    "SELECT snapshot_path FROM versions WHERE id=?", (vid,)
                ).fetchone()
                if snap:  # pragma: no branch
                    try:
                        Path(snap[0]).unlink(missing_ok=True)
                    except OSError:  # pragma: no cover
                        pass
                conn.execute("DELETE FROM versions WHERE id=?", (vid,))

    def _init_db(self) -> None:
        with self._db_lock, self._connect() as conn:
            conn.executescript(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    @staticmethod
    def _row_to_dict(row: Iterable | None) -> dict:
        if row is None:
            return {}
        (rid, rn, rp, sp, sha, size, ts, act, note) = row
        return {
            "id": rid,
            "root_name": rn,
            "rel_path": rp,
            "snapshot_path": sp,
            "sha256": sha,
            "size": size,
            "timestamp": ts,
            "action": act,
            "note": note,
        }
