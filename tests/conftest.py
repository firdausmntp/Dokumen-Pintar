"""Shared pytest fixtures for Dokumen-Pintar tests."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Iterator

import pytest

from dokumen_pintar.config import AppConfig, AuditConfig, RootConfig, VersioningConfig
from dokumen_pintar.context import AppContext, build_context
from dokumen_pintar.pathguard import PathGuard


@pytest.fixture
def tmp_roots(tmp_path: Path) -> tuple[Path, Path]:
    """Create two directories: ``docs`` (writable) and ``ref`` (read-only)."""
    docs_dir = tmp_path / "docs"
    ref_dir = tmp_path / "ref"
    docs_dir.mkdir()
    ref_dir.mkdir()
    return docs_dir, ref_dir


@pytest.fixture
def make_config(tmp_path: Path, tmp_roots: tuple[Path, Path]) -> Callable[..., AppConfig]:
    """Return a callable that builds an :class:`AppConfig` with the two roots."""
    docs_dir, ref_dir = tmp_roots
    global_storage = tmp_path / "versions-global"
    global_storage.mkdir(parents=True, exist_ok=True)
    audit_path = tmp_path / "audit.jsonl"

    def _make(**overrides: object) -> AppConfig:
        kwargs: dict[str, object] = {
            "roots": [
                RootConfig(name="documents", path=str(docs_dir), writable=True),
                RootConfig(name="ref", path=str(ref_dir), writable=False),
            ],
            "versioning": VersioningConfig(
                enabled=True,
                storage_mode="global",
                global_storage_path=str(global_storage),
                retention_days=30,
                max_versions_per_file=50,
            ),
            "audit": AuditConfig(enabled=True, log_path=str(audit_path)),
        }
        kwargs.update(overrides)
        return AppConfig(**kwargs)  # type: ignore[arg-type]

    return _make


@pytest.fixture
def context(make_config: Callable[..., AppConfig]) -> Iterator[AppContext]:
    """Build an :class:`AppContext` wired with guard, versions, audit, and registry."""
    cfg = make_config()
    ctx = build_context(cfg)
    yield ctx


@pytest.fixture
def guard(context: AppContext) -> PathGuard:
    return context.guard
