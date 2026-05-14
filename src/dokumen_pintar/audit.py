"""JSON-Lines audit logging with persistent file handle."""

from __future__ import annotations

import atexit
import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, IO

from .config import AppConfig


class AuditLogger:
    def __init__(self, config: AppConfig, *, default_path: Path):
        self._config = config
        if config.audit.log_path:
            self._path = Path(config.audit.log_path).expanduser().resolve()
        else:
            self._path = default_path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._fh: IO[str] | None = None
        atexit.register(self.close)

    @property
    def enabled(self) -> bool:
        return self._config.audit.enabled

    @property
    def path(self) -> Path:
        return self._path

    def _ensure_open(self) -> IO[str]:
        if self._fh is None or self._fh.closed:
            # Buffered append; flush on each write but don't close.
            self._fh = self._path.open("a", encoding="utf-8", buffering=8192)
        return self._fh

    def log(self, action: str, **fields: Any) -> None:
        if not self.enabled:
            return
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "action": action,
            **fields,
        }
        line = json.dumps(record, ensure_ascii=False, default=str)
        with self._lock:
            fh = self._ensure_open()
            fh.write(line + "\n")
            fh.flush()  # durability without close

    def close(self) -> None:
        with self._lock:
            fh = self._fh
            if fh is not None and not fh.closed:
                try:
                    fh.flush()
                except OSError:
                    pass
                try:
                    fh.close()
                except OSError:
                    pass
            self._fh = None
