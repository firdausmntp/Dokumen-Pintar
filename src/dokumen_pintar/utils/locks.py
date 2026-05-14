"""Per-path advisory locks (cross-platform)."""

from __future__ import annotations

import hashlib
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from filelock import FileLock


_LOCK_DIR = Path(tempfile.gettempdir()) / "dokumen-pintar-locks"
_LOCK_DIR.mkdir(parents=True, exist_ok=True)


def _lock_path_for(target: Path) -> Path:
    digest = hashlib.sha1(str(target.resolve()).encode("utf-8", errors="replace")).hexdigest()
    return _LOCK_DIR / f"{digest}.lock"


@contextmanager
def file_lock(target: Path, *, timeout: float = 30.0) -> Iterator[None]:
    lock = FileLock(str(_lock_path_for(target)), timeout=timeout)
    with lock:
        yield
