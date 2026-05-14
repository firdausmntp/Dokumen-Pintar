"""Small helpers used by tool modules."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..context import AppContext
from ..errors import UnsupportedFormatError
from ..pathguard import ResolvedPath

# Binary container formats — replacing or appending raw text bytes corrupts
# the underlying ZIP/OLE/PDF structure. Tools that perform raw text I/O on
# the file (content_write fallback, content_append, content_insert,
# content_replace, content_delete_range, content_patch, batch_replace_content)
# must refuse these formats when the target file already exists.
BINARY_CONTAINER_FORMATS: frozenset[str] = frozenset({"docx", "xlsx", "pptx", "pdf"})


def refuse_binary_text_op(ctx: AppContext, resolved: ResolvedPath, op: str) -> None:
    """Raise UnsupportedFormatError if the target is an EXISTING binary container.

    Use this at the entry of every tool that mutates a file via raw text I/O
    (content_append / insert / replace / delete_range / patch / write).
    The helper does not refuse non-existing paths — content_write is
    allowed to bootstrap a new docx via the handler's create-new path.
    Read-only tools and tools that go through a handler's structured API
    (struct_set, struct_delete) do not need this guard.
    """
    p = resolved.absolute
    if not p.exists() or not p.is_file():
        return
    handler = ctx.registry.for_path(p)
    if handler is None:
        return
    if handler.name in BINARY_CONTAINER_FORMATS:
        raise UnsupportedFormatError(
            f"{op}: refusing to mutate existing {handler.name} file via raw "
            f"text (would corrupt the binary container). Use struct_set/"
            f"struct_get to edit it, or delete the file first to re-create it."
        )


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
