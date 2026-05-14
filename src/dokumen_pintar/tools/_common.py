"""Small helpers used by tool modules."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..context import AppContext
from ..errors import UnsupportedFormatError
from ..pathguard import ResolvedPath


def resolve_for_read(ctx: AppContext, path: str) -> ResolvedPath:
    resolved = ctx.guard.resolve(path)
    ctx.guard.ensure_within_size_limit(resolved.absolute)
    return resolved


def resolve_for_write(ctx: AppContext, path: str) -> ResolvedPath:
    resolved = ctx.guard.resolve(path)
    ctx.guard.ensure_writable(resolved)
    return resolved


def handler_for(ctx: AppContext, p: Path):  # type: ignore[no-untyped-def]
    h = ctx.registry.for_path(p)
    if h is None:
        raise UnsupportedFormatError(f"No handler for file: {p}")
    return h


def summarize_resolved(r: ResolvedPath) -> dict[str, Any]:
    return {
        "uri": r.workspace_uri,
        "absolute": str(r.absolute),
        "root": r.root.name,
        "rel": r.rel_to_root.as_posix(),
    }
