"""Tests for :mod:`dokumen_pintar.audit`."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from dokumen_pintar.audit import AuditLogger
from dokumen_pintar.config import AppConfig, AuditConfig


def test_audit_log_writes_jsonl(make_config: Callable[..., AppConfig], tmp_path: Path) -> None:
    cfg = make_config()
    logger = AuditLogger(cfg, default_path=tmp_path / "audit.jsonl")
    logger.log("test_action", key="value")
    logger.close()

    content = logger.path.read_text(encoding="utf-8").strip()
    record = json.loads(content)
    assert record["action"] == "test_action"
    assert record["key"] == "value"
    assert "ts" in record


def test_audit_disabled_skips_write(tmp_path: Path) -> None:
    from dokumen_pintar.config import AppConfig, RootConfig

    docs = tmp_path / "docs"
    docs.mkdir()
    cfg = AppConfig(
        roots=[RootConfig(name="d", path=str(docs), writable=True)],
        audit=AuditConfig(enabled=False),
    )
    logger = AuditLogger(cfg, default_path=tmp_path / "audit.jsonl")
    logger.log("should_not_appear", data="nope")
    logger.close()

    assert not logger.path.exists()


def test_audit_enabled_property(make_config: Callable[..., AppConfig], tmp_path: Path) -> None:
    cfg = make_config()
    logger = AuditLogger(cfg, default_path=tmp_path / "audit.jsonl")
    assert logger.enabled is True
    logger.close()


def test_audit_path_property(make_config: Callable[..., AppConfig], tmp_path: Path) -> None:
    default = tmp_path / "audit.jsonl"
    cfg = make_config()
    logger = AuditLogger(cfg, default_path=default)
    assert isinstance(logger.path, Path)
    logger.close()


def test_audit_multiple_writes(make_config: Callable[..., AppConfig], tmp_path: Path) -> None:
    cfg = make_config()
    logger = AuditLogger(cfg, default_path=tmp_path / "audit.jsonl")
    logger.log("event_1")
    logger.log("event_2")
    logger.log("event_3")
    logger.close()

    lines = logger.path.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 3
    actions = [json.loads(line)["action"] for line in lines]
    assert actions == ["event_1", "event_2", "event_3"]


def test_audit_close_idempotent(make_config: Callable[..., AppConfig], tmp_path: Path) -> None:
    cfg = make_config()
    logger = AuditLogger(cfg, default_path=tmp_path / "audit.jsonl")
    logger.log("x")
    logger.close()
    logger.close()  # should not raise


def test_audit_reopen_after_close(make_config: Callable[..., AppConfig], tmp_path: Path) -> None:
    cfg = make_config()
    logger = AuditLogger(cfg, default_path=tmp_path / "audit.jsonl")
    logger.log("first")
    logger.close()
    logger.log("second")
    logger.close()

    lines = logger.path.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 2


def test_audit_close_oserror(make_config: Callable[..., AppConfig], tmp_path: Path) -> None:
    from unittest.mock import patch
    cfg = make_config()
    logger = AuditLogger(cfg, default_path=tmp_path / "audit.jsonl")
    logger.log("x")
    # Patch flush to raise OSError
    with patch.object(logger._fh, "flush", side_effect=OSError("disk full")):
        logger.close()  # Should not raise
    # Logger should still be usable after
    assert logger._fh is None
