"""File-level CRUD tools."""

from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from ..context import AppContext
from ..errors import UnsupportedFormatError, ValidationError
from ..utils.locks import file_lock
from ._common import (
    BINARY_CONTAINER_FORMATS,
    resolve_for_read,
    resolve_for_write,
    summarize_resolved,
)


def register(mcp: FastMCP, ctx: AppContext) -> None:
    def _snapshot(resolved, action: str) -> dict | None:  # type: ignore[no-untyped-def]
        if not resolved.absolute.exists() or resolved.absolute.is_dir():  # pragma: no cover
            return None
        return ctx.versions.snapshot(
            root_name=resolved.root.name,
            rel_path=resolved.rel_to_root.as_posix(),
            source=resolved.absolute,
            action=action,
        )

    @mcp.tool(
        name="file_create",
        description=(
            "Create a new file. `content` defaults to empty. Set `overwrite=True` "
            "to replace an existing file (a snapshot is captured first)."
        ),
    )
    def file_create(path: str, content: str = "", overwrite: bool = False) -> dict[str, Any]:
        resolved = resolve_for_write(ctx, path)
        target = resolved.absolute
        # Refuse to create binary container formats via raw text — the
        # resulting file would be a non-conforming "fake" docx/xlsx/etc.
        # An empty placeholder is also blocked because consumers will try
        # to open it and get parse errors.
        handler = ctx.registry.for_path(target)
        if handler is not None and handler.name in BINARY_CONTAINER_FORMATS:
            raise UnsupportedFormatError(
                f"file_create: refusing to write {handler.name} via raw text "
                "(would produce a non-conforming file). Use content_write to "
                "go through the format-aware writer (docx only), or struct_set "
                "for xlsx/pptx; pdf is read-only."
            )
        with file_lock(target):
            if target.exists():
                if not overwrite:
                    raise ValidationError(f"File exists; pass overwrite=true: {target}")
                _snapshot(resolved, "overwrite_pre_create")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            snap = _snapshot(resolved, "create")
        ctx.audit.log("file_create", path=str(target), root=resolved.root.name, size=len(content))
        return {**summarize_resolved(resolved), "created": True, "snapshot": snap}

    @mcp.tool(
        name="file_delete",
        description=(
            "Delete a file or (with `recursive=True`) a directory. A snapshot of "
            "the file is preserved in the version store first."
        ),
    )
    def file_delete(path: str, recursive: bool = False) -> dict[str, Any]:
        resolved = resolve_for_write(ctx, path)
        target = resolved.absolute
        # Refuse to delete the workspace root itself — that would wipe the
        # entire root the user mounted (and almost never reflects intent).
        if target == resolved.root_absolute:
            raise ValidationError(
                f"Refusing to delete workspace root '{resolved.root.name}' "
                f"({target}). Delete its contents individually instead."
            )
        with file_lock(target):
            if not target.exists():
                raise ValidationError(f"Path does not exist: {target}")
            snap = None
            snapshot_count = 0
            if target.is_file():
                snap = _snapshot(resolved, "delete")
                target.unlink()
            else:
                if not recursive:
                    raise ValidationError(
                        f"Path is a directory; pass recursive=true to delete: {target}"
                    )
                # B15: snapshot every file inside the directory BEFORE the
                # recursive remove, so users can recover individual entries
                # via `version_list` + `version_restore`. Bounded by the
                # global max_versions_per_file so this stays predictable.
                for child in target.rglob("*"):
                    if child.is_file():
                        try:
                            rel_to_root = child.relative_to(resolved.root_absolute).as_posix()
                        except ValueError:
                            continue
                        try:
                            ctx.versions.snapshot(
                                root_name=resolved.root.name,
                                rel_path=rel_to_root,
                                source=child,
                                action="recursive_delete",
                            )
                            snapshot_count += 1
                        except Exception:  # noqa: BLE001
                            # Never block the delete on a single snapshot failure.
                            pass
                shutil.rmtree(target)
        ctx.audit.log(
            "file_delete",
            path=str(target),
            root=resolved.root.name,
            recursive=recursive,
            snapshots=snapshot_count,
        )
        result: dict[str, Any] = {**summarize_resolved(resolved), "deleted": True, "snapshot": snap}
        if snapshot_count:
            result["snapshots_taken"] = snapshot_count
        return result

    @mcp.tool(
        name="file_rename",
        description="Rename a file or directory inside the same parent directory.",
    )
    def file_rename(src: str, dst: str) -> dict[str, Any]:
        s = resolve_for_write(ctx, src)
        d = resolve_for_write(ctx, dst)
        if s.absolute == s.root_absolute:
            raise ValidationError(
                f"Refusing to rename workspace root '{s.root.name}' ({s.absolute})."
            )
        if not s.absolute.exists():
            raise ValidationError(f"Source does not exist: {s.absolute}")
        if d.absolute.exists():
            raise ValidationError(f"Destination exists: {d.absolute}")
        if s.absolute.parent != d.absolute.parent:
            raise ValidationError("rename requires same parent dir; use file_move otherwise")
        with file_lock(s.absolute):
            _snapshot(s, "rename")
            s.absolute.rename(d.absolute)
        ctx.audit.log("file_rename", src=str(s.absolute), dst=str(d.absolute))
        return {"src": summarize_resolved(s), "dst": summarize_resolved(d)}

    @mcp.tool(
        name="file_move",
        description="Move a file or directory across paths/roots (within the workspace).",
    )
    def file_move(src: str, dst: str, overwrite: bool = False) -> dict[str, Any]:
        s = resolve_for_write(ctx, src)
        d = resolve_for_write(ctx, dst)
        if s.absolute == s.root_absolute:
            raise ValidationError(
                f"Refusing to move workspace root '{s.root.name}' ({s.absolute})."
            )
        if not s.absolute.exists():
            raise ValidationError(f"Source does not exist: {s.absolute}")
        if d.absolute.exists() and not overwrite:
            raise ValidationError(f"Destination exists; pass overwrite=true: {d.absolute}")
        with file_lock(s.absolute):
            _snapshot(s, "move")
            d.absolute.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(s.absolute), str(d.absolute))
        ctx.audit.log("file_move", src=str(s.absolute), dst=str(d.absolute))
        return {"src": summarize_resolved(s), "dst": summarize_resolved(d)}

    @mcp.tool(
        name="file_copy",
        description="Copy a file or directory.",
    )
    def file_copy(src: str, dst: str, overwrite: bool = False) -> dict[str, Any]:
        s = resolve_for_read(ctx, src)
        d = resolve_for_write(ctx, dst)
        # Refuse copying the workspace root itself or overwriting one — with
        # `overwrite=True` the directory branch below would `rmtree(dst)` and
        # nuke the entire mounted root.
        if s.absolute == s.root_absolute:
            raise ValidationError(
                f"Refusing to copy workspace root '{s.root.name}' ({s.absolute})."
            )
        if d.absolute == d.root_absolute:
            raise ValidationError(
                f"Refusing to copy onto workspace root '{d.root.name}' ({d.absolute})."
            )
        if not s.absolute.exists():
            raise ValidationError(f"Source does not exist: {s.absolute}")
        if d.absolute.exists() and not overwrite:
            raise ValidationError(f"Destination exists; pass overwrite=true: {d.absolute}")
        d.absolute.parent.mkdir(parents=True, exist_ok=True)
        if s.absolute.is_dir():
            if d.absolute.exists():
                shutil.rmtree(d.absolute)
            shutil.copytree(s.absolute, d.absolute)
        else:
            shutil.copy2(s.absolute, d.absolute)
        ctx.audit.log("file_copy", src=str(s.absolute), dst=str(d.absolute))
        return {"src": summarize_resolved(s), "dst": summarize_resolved(d)}
