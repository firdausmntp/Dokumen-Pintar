"""Shared runtime context for every tool call."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .audit import AuditLogger
from .config import AppConfig
from .handlers import HandlerRegistry
from .pathguard import PathGuard
from .versioning import VersionStore


@dataclass
class AppContext:
    config: AppConfig
    guard: PathGuard
    versions: VersionStore
    audit: AuditLogger
    registry: HandlerRegistry

    @property
    def roots(self):  # type: ignore[no-untyped-def]
        return self.guard.roots


def build_context(config: AppConfig) -> AppContext:
    """Create an :class:`AppContext` wired with all subsystems."""
    from .handlers import default_registry  # late import to allow registration side-effects

    guard = PathGuard(config)

    per_root: dict[str, Path] = {}
    for r, abs_path in guard.roots:
        if r.writable:
            per_root[r.name] = abs_path / ".mcpdocs"

    if config.versioning.global_storage_path:
        global_dir = Path(config.versioning.global_storage_path).expanduser().resolve()
    else:
        # default: first writable root, else temp dir
        if per_root:
            global_dir = next(iter(per_root.values())) / "global"
        else:
            from platformdirs import user_data_dir

            global_dir = Path(user_data_dir("dokumen-pintar", "dokumen-pintar")) / "global"

    versions = VersionStore(config, per_root_dirs=per_root, global_dir=global_dir)

    audit_default = global_dir / "audit.jsonl"
    audit = AuditLogger(config, default_path=audit_default)

    # Register built-in handlers lazily.
    from .handlers import text_handler  # noqa: F401 — side-effect
    from .handlers import json_yaml_handler  # noqa: F401
    from .handlers import csv_handler  # noqa: F401
    from .handlers import xml_handler  # noqa: F401
    from .handlers import docx_handler  # noqa: F401
    from .handlers import xlsx_handler  # noqa: F401
    from .handlers import pptx_handler  # noqa: F401
    from .handlers import pdf_handler  # noqa: F401
    # MarkdownHandler & LatexHandler register AFTER text_handler so they win
    # the .md / .markdown / .tex extension lookups (registry overwrites).
    from .handlers import markdown_handler  # noqa: F401
    from .handlers import latex_handler  # noqa: F401
    from .handlers import image_handler  # noqa: F401

    ctx = AppContext(
        config=config,
        guard=guard,
        versions=versions,
        audit=audit,
        registry=default_registry,
    )

    # Best-effort retention enforcement at startup. Without this the
    # `retention_days` config is only enforced by manual `version_purge`
    # calls, so a long-running server's snapshot store would grow forever.
    if config.versioning.enabled and config.versioning.retention_days > 0:
        try:
            versions.purge()
        except Exception:  # noqa: BLE001
            # Never let a startup-time cleanup failure block the server.
            pass

    return ctx
