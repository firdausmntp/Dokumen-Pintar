"""Versioning tools (list / diff / restore / undo / purge)."""

from __future__ import annotations

import difflib
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from ..context import AppContext
from ..errors import VersioningError
from ..utils.encoding import read_text
from ..utils.locks import file_lock
from ._common import resolve_for_read, resolve_for_write, summarize_resolved


def register(mcp: FastMCP, ctx: AppContext) -> None:
    @mcp.tool(
        name="version_list",
        description="List the snapshot history for a file (newest first).",
    )
    def version_list(path: str) -> dict[str, Any]:
        resolved = resolve_for_read(ctx, path)
        items = ctx.versions.list_versions(
            root_name=resolved.root.name,
            rel_path=resolved.rel_to_root.as_posix(),
        )
        return {**summarize_resolved(resolved), "count": len(items), "versions": items}

    @mcp.tool(
        name="version_diff",
        description=(
            "Compute a unified diff between the current file and a snapshot version. "
            "Works for text-like formats; binary formats fall back to a size/sha summary."
        ),
    )
    def version_diff(path: str, version_id: int) -> dict[str, Any]:
        resolved = resolve_for_read(ctx, path)
        rec = ctx.versions.get(version_id)
        if rec is None:
            raise VersioningError(f"Version {version_id} not found")
        snap = Path(rec["snapshot_path"])
        try:
            cur_text, _ = (
                read_text(resolved.absolute) if resolved.absolute.exists() else ("", "utf-8")
            )
            old_text, _ = read_text(snap)
            diff = "\n".join(
                difflib.unified_diff(
                    old_text.splitlines(),
                    cur_text.splitlines(),
                    fromfile=f"version:{version_id}",
                    tofile="current",
                    lineterm="",
                )
            )
            return {**summarize_resolved(resolved), "version": rec, "diff": diff}
        except UnicodeDecodeError:
            return {
                **summarize_resolved(resolved),
                "version": rec,
                "diff": None,
                "binary": True,
            }

    @mcp.tool(
        name="version_restore",
        description="Replace the current file with the contents of `version_id`.",
    )
    def version_restore(path: str, version_id: int) -> dict[str, Any]:
        resolved = resolve_for_write(ctx, path)
        rec = ctx.versions.get(version_id)
        if rec is None:
            raise VersioningError(f"Version {version_id} not found")
        with file_lock(resolved.absolute):
            ctx.versions.snapshot(
                root_name=resolved.root.name,
                rel_path=resolved.rel_to_root.as_posix(),
                source=resolved.absolute
                if resolved.absolute.exists()
                else Path(rec["snapshot_path"]),
                action="restore_pre",
            ) if resolved.absolute.exists() else None
            ctx.versions.restore(version_id, resolved.absolute)
        ctx.audit.log("version_restore", path=str(resolved.absolute), version_id=version_id)
        return {**summarize_resolved(resolved), "restored_from": rec}

    @mcp.tool(
        name="version_undo",
        description="Revert the file to its most recent snapshot.",
    )
    def version_undo(path: str) -> dict[str, Any]:
        resolved = resolve_for_write(ctx, path)
        items = ctx.versions.list_versions(
            root_name=resolved.root.name,
            rel_path=resolved.rel_to_root.as_posix(),
        )
        if len(items) < 1:
            raise VersioningError("No history available for this path")
        # The most recent snapshot is the one we'd restore.  If history >=2 and the
        # head snapshot equals current state, prefer the second one.
        target = items[1] if len(items) > 1 else items[0]
        with file_lock(resolved.absolute):
            ctx.versions.restore(target["id"], resolved.absolute)
        ctx.audit.log("version_undo", path=str(resolved.absolute), version_id=target["id"])
        return {**summarize_resolved(resolved), "restored_from": target}

    @mcp.tool(
        name="version_purge",
        description=(
            "Delete snapshots older than `older_than_days` (defaults to configured retention)."
        ),
    )
    def version_purge(older_than_days: int | None = None) -> dict[str, Any]:
        removed = ctx.versions.purge(older_than_days=older_than_days)
        ctx.audit.log("version_purge", removed=removed, older_than_days=older_than_days)
        return {"removed": removed}
