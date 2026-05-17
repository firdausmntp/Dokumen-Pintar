"""Unified metadata read/write/strip tools.

These tools dispatch to the per-format handler's ``write_meta`` /
``strip_meta`` methods. All operations are snapshotted via the version
store so they can be rolled back with ``version_restore``.

Supported targets in v1.1.0:

- **Images** (.jpg, .jpeg, .tif, .tiff, .webp): EXIF tags via piexif.
- **DOCX / XLSX / PPTX**: OOXML core properties (author, title, etc.).
- **PDF**: docinfo dictionary (Title, Author, Subject, ...) plus a
  best-effort XMP clear on ``metadata_strip``.

Calling these tools on a format that does not advertise
``HandlerCapability.WRITE_META`` returns an ``UnsupportedFormatError``.
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from ..context import AppContext
from ..errors import HandlerError, UnsupportedFormatError
from ..handlers.base import HandlerCapability
from ..utils.walking import iter_files
from ._common import resolve_for_write, summarize_resolved


def _require_writable(ctx: AppContext, path: str):
    """Resolve ``path`` and confirm its handler supports WRITE_META."""
    resolved = resolve_for_write(ctx, path)
    handler = ctx.registry.for_path(resolved.absolute)
    if handler is None:
        raise UnsupportedFormatError(f"no handler registered for {resolved.absolute.suffix!r}")
    if not (handler.capabilities & HandlerCapability.WRITE_META):
        raise UnsupportedFormatError(f"handler {handler.name!r} does not support metadata writes")
    return resolved, handler


def register(mcp: FastMCP, ctx: AppContext) -> None:
    """Register the four metadata tools on ``mcp``."""

    @mcp.tool(
        name="metadata_read",
        description=(
            "Read all metadata exposed by the handler for `path`. Returns the "
            "handler-native metadata dict (EXIF for images, core_properties "
            "for Office formats, docinfo for PDF)."
        ),
    )
    def metadata_read(path: str) -> dict[str, Any]:
        resolved = resolve_for_write(ctx, path)  # read also goes through guard
        handler = ctx.registry.for_path(resolved.absolute)
        if handler is None:
            raise UnsupportedFormatError(f"no handler registered for {resolved.absolute.suffix!r}")
        meta = handler.read_meta(resolved.absolute)
        ctx.audit.log("metadata_read", path=str(resolved.absolute))
        return {
            **summarize_resolved(resolved),
            "format": handler.name,
            "meta": meta,
        }

    @mcp.tool(
        name="metadata_write",
        description=(
            "Merge `updates` into the file's metadata. Snapshots the file "
            "pre+post so the change can be rolled back via `version_restore`. "
            "Keys must match the handler's writable set; unknown keys raise "
            "an error. Set a value to null to delete that field (where "
            "supported)."
        ),
    )
    def metadata_write(path: str, updates: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(updates, dict) or not updates:
            raise HandlerError("`updates` must be a non-empty dict")
        resolved, handler = _require_writable(ctx, path)

        ctx.versions.snapshot(
            root_name=resolved.root.name,
            rel_path=resolved.rel_to_root.as_posix(),
            source=resolved.absolute,
            action="metadata_write_pre",
        ) if resolved.absolute.exists() else None

        applied = handler.write_meta(resolved.absolute, updates)

        ctx.versions.snapshot(
            root_name=resolved.root.name,
            rel_path=resolved.rel_to_root.as_posix(),
            source=resolved.absolute,
            action="metadata_write_post",
        )
        ctx.audit.log(
            "metadata_write",
            path=str(resolved.absolute),
            keys=list(applied.keys()),
        )
        return {
            **summarize_resolved(resolved),
            "format": handler.name,
            "applied": applied,
        }

    @mcp.tool(
        name="metadata_delete",
        description=(
            "Delete specific metadata `keys` from a file. Equivalent to "
            "`metadata_write` with each key mapped to null. Snapshots pre+post."
        ),
    )
    def metadata_delete(path: str, keys: list[str]) -> dict[str, Any]:
        if not keys:
            raise HandlerError("`keys` must be a non-empty list")
        resolved, handler = _require_writable(ctx, path)

        ctx.versions.snapshot(
            root_name=resolved.root.name,
            rel_path=resolved.rel_to_root.as_posix(),
            source=resolved.absolute,
            action="metadata_delete_pre",
        ) if resolved.absolute.exists() else None

        updates = {k: None for k in keys}
        applied = handler.write_meta(resolved.absolute, updates)

        ctx.versions.snapshot(
            root_name=resolved.root.name,
            rel_path=resolved.rel_to_root.as_posix(),
            source=resolved.absolute,
            action="metadata_delete_post",
        )
        ctx.audit.log(
            "metadata_delete",
            path=str(resolved.absolute),
            keys=list(applied.keys()),
        )
        return {
            **summarize_resolved(resolved),
            "format": handler.name,
            "deleted": list(applied.keys()),
        }

    @mcp.tool(
        name="metadata_strip",
        description=(
            "Remove **all** writable metadata from a file. Useful for "
            "privacy-sanitizing documents before sharing. Snapshots pre+post."
        ),
    )
    def metadata_strip(path: str) -> dict[str, Any]:
        resolved, handler = _require_writable(ctx, path)
        if not hasattr(handler, "strip_meta"):  # pragma: no cover — guarded
            # by the WRITE_META capability check; every handler with that
            # flag implements strip_meta.
            raise UnsupportedFormatError(f"handler {handler.name!r} does not implement strip_meta")

        ctx.versions.snapshot(
            root_name=resolved.root.name,
            rel_path=resolved.rel_to_root.as_posix(),
            source=resolved.absolute,
            action="metadata_strip_pre",
        ) if resolved.absolute.exists() else None

        result = handler.strip_meta(resolved.absolute)  # type: ignore[attr-defined]

        ctx.versions.snapshot(
            root_name=resolved.root.name,
            rel_path=resolved.rel_to_root.as_posix(),
            source=resolved.absolute,
            action="metadata_strip_post",
        )
        ctx.audit.log("metadata_strip", path=str(resolved.absolute))
        return {
            **summarize_resolved(resolved),
            "format": handler.name,
            **result,
        }



def register_batch(mcp: FastMCP, ctx: AppContext) -> None:
    """Register the bulk metadata reader. Called from server._build_server."""

    @mcp.tool(
        name="metadata_read_batch",
        description=(
            "Read metadata for every file matching `glob`. Skips files whose "
            "handler does not implement read_meta or whose parser fails. "
            "Returns a list of {uri, format, meta} entries plus a count."
        ),
    )
    def metadata_read_batch(
        glob: str,
        fields: list[str] | None = None,
        max_files: int = 5000,
    ) -> dict[str, Any]:
        files: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []
        scanned = 0
        for root_name, p, root_abs in iter_files(ctx, glob=glob):
            scanned += 1
            if scanned > max_files:
                break
            uri = f"{root_name}:/{p.relative_to(root_abs).as_posix()}"
            handler = ctx.registry.for_path(p)
            if handler is None:
                skipped.append({"uri": uri, "reason": "no_handler"})
                continue
            try:
                ctx.guard.ensure_within_size_limit(p)
                meta = handler.read_meta(p)
            except Exception as exc:  # noqa: BLE001
                skipped.append({"uri": uri, "reason": "read_failed", "error": str(exc)})
                continue
            if fields is not None:
                meta = {k: meta.get(k) for k in fields if k in meta}
            files.append({"uri": uri, "absolute": str(p), "format": handler.name, "meta": meta})
        ctx.audit.log("metadata_read_batch", glob=glob, count=len(files))
        result: dict[str, Any] = {"glob": glob, "count": len(files), "files": files}
        if skipped:
            result["skipped"] = skipped
            summary: dict[str, int] = {}
            for s in skipped:
                summary[s["reason"]] = summary.get(s["reason"], 0) + 1
            result["skipped_summary"] = summary
        return result
