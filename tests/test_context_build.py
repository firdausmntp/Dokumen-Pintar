"""Tests for :func:`dokumen_pintar.context.build_context`."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from dokumen_pintar.audit import AuditLogger
from dokumen_pintar.config import AppConfig
from dokumen_pintar.context import AppContext, build_context
from dokumen_pintar.handlers import HandlerRegistry
from dokumen_pintar.pathguard import PathGuard
from dokumen_pintar.versioning import VersionStore


def test_build_context_wires_subsystems(
    make_config: Callable[..., AppConfig],
) -> None:
    cfg = make_config()
    ctx = build_context(cfg)
    assert isinstance(ctx, AppContext)
    assert isinstance(ctx.guard, PathGuard)
    assert isinstance(ctx.versions, VersionStore)
    assert isinstance(ctx.audit, AuditLogger)
    assert isinstance(ctx.registry, HandlerRegistry)


def test_registry_has_required_handlers(
    make_config: Callable[..., AppConfig],
) -> None:
    cfg = make_config()
    ctx = build_context(cfg)

    required = ["text", "json", "yaml", "csv", "xml", "docx", "xlsx", "pptx", "pdf"]
    for fmt in required:
        assert ctx.registry.by_format(fmt) is not None, f"missing handler: {fmt}"


def test_audit_log_path_exists_after_event(
    make_config: Callable[..., AppConfig],
    tmp_path: Path,
) -> None:
    cfg = make_config()
    ctx = build_context(cfg)
    ctx.audit.log("test_event", foo="bar")

    assert ctx.audit.path.exists()
    content = ctx.audit.path.read_text(encoding="utf-8")
    assert "test_event" in content
    assert "bar" in content


def test_context_exposes_roots(make_config: Callable[..., AppConfig]) -> None:
    cfg = make_config()
    ctx = build_context(cfg)
    names = [r.name for r, _ in ctx.roots]
    assert "documents" in names
    assert "ref" in names


def test_context_with_global_storage_path(
    make_config: Callable[..., AppConfig], tmp_path: Path
) -> None:
    cfg = make_config()
    cfg.versioning.global_storage_path = str(tmp_path / "custom_global")
    ctx = build_context(cfg)
    assert isinstance(ctx.versions, VersionStore)


def test_context_no_writable_roots(tmp_path: Path) -> None:
    from dokumen_pintar.config import AppConfig, RootConfig
    cfg = AppConfig(
        roots=[RootConfig(name="ro", path=str(tmp_path / "ro"), writable=False)],
    )
    (tmp_path / "ro").mkdir()
    ctx = build_context(cfg)
    assert isinstance(ctx.versions, VersionStore)


def test_context_writable_root_no_global_storage(tmp_path: Path) -> None:
    from dokumen_pintar.config import AppConfig, RootConfig
    cfg = AppConfig(
        roots=[RootConfig(name="docs", path=str(tmp_path / "docs"), writable=True)],
    )
    cfg.versioning.global_storage_path = ""
    (tmp_path / "docs").mkdir()
    ctx = build_context(cfg)
    assert isinstance(ctx.versions, VersionStore)


def test_context_swallows_startup_purge_failure(
    make_config: Callable[..., AppConfig],
    monkeypatch,
) -> None:
    """A corrupt snapshot index must not block server boot — the startup
    retention sweep is best-effort and silently ignores failures."""
    from dokumen_pintar import context as context_module

    calls = {"n": 0}
    real_init = context_module.VersionStore.__init__

    def _init(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        real_init(self, *args, **kwargs)
        # Replace purge with one that raises on first call.
        def _boom(*a, **kw):  # type: ignore[no-untyped-def]
            calls["n"] += 1
            raise RuntimeError("snapshot index corrupt")
        self.purge = _boom  # type: ignore[method-assign]

    monkeypatch.setattr(context_module.VersionStore, "__init__", _init)

    cfg = make_config()
    # Must not raise — the failure is swallowed.
    ctx = build_context(cfg)
    assert isinstance(ctx, AppContext)
    assert calls["n"] == 1
