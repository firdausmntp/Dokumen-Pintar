"""Structured (format-aware) CRUD tools."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from ..context import AppContext
from ..errors import UnsupportedFormatError
from ..utils.locks import file_lock
from ._common import handler_for, resolve_for_read, resolve_for_write, summarize_resolved


def register(mcp: FastMCP, ctx: AppContext) -> None:
    def _snapshot(resolved, action: str):  # type: ignore[no-untyped-def]
        return ctx.versions.snapshot(
            root_name=resolved.root.name,
            rel_path=resolved.rel_to_root.as_posix(),
            source=resolved.absolute,
            action=action,
        )

    @mcp.tool(
        name="struct_get",
        description=(
            "Format-aware read using the file's handler. `expr` syntax depends on "
            "the format: JSONPath for JSON/YAML, XPath for XML, or sub-paths "
            "like `cell:Sheet1!A1`, `paragraph:3`, `slide:0`, `page:0`, `metadata`."
        ),
    )
    def struct_get(path: str, expr: str) -> dict[str, Any]:
        resolved = resolve_for_read(ctx, path)
        handler = handler_for(ctx, resolved.absolute)
        result = handler.structured_get(resolved.absolute, expr)
        return {
            **summarize_resolved(resolved),
            "handler": handler.name,
            "expr": expr,
            "result": result,
        }

    @mcp.tool(
        name="struct_set",
        description=(
            "Format-aware write. Snapshots the file first, then mutates via "
            "the handler. See `struct_get` for `expr` syntax per format."
        ),
    )
    def struct_set(path: str, expr: str, value: Any) -> dict[str, Any]:
        resolved = resolve_for_write(ctx, path)
        handler = handler_for(ctx, resolved.absolute)
        with file_lock(resolved.absolute):
            _snapshot(resolved, "struct_set_pre")
            handler.structured_set(resolved.absolute, expr, value)
            snap = _snapshot(resolved, "struct_set_post")
        ctx.audit.log(
            "struct_set",
            path=str(resolved.absolute),
            expr=expr,
            handler=handler.name,
        )
        return {**summarize_resolved(resolved), "snapshot": snap}

    @mcp.tool(
        name="struct_delete",
        description="Format-aware delete (paragraph, row, sheet, slide, key, attribute).",
    )
    def struct_delete(path: str, expr: str) -> dict[str, Any]:
        resolved = resolve_for_write(ctx, path)
        handler = handler_for(ctx, resolved.absolute)
        with file_lock(resolved.absolute):
            _snapshot(resolved, "struct_delete_pre")
            handler.structured_delete(resolved.absolute, expr)
            snap = _snapshot(resolved, "struct_delete_post")
        ctx.audit.log(
            "struct_delete",
            path=str(resolved.absolute),
            expr=expr,
            handler=handler.name,
        )
        return {**summarize_resolved(resolved), "snapshot": snap}

    @mcp.tool(
        name="struct_meta",
        description="Format-aware metadata for a file (delegates to handler.read_meta).",
    )
    def struct_meta(path: str) -> dict[str, Any]:
        resolved = resolve_for_read(ctx, path)
        handler = handler_for(ctx, resolved.absolute)
        meta = handler.read_meta(resolved.absolute)
        return {**summarize_resolved(resolved), "handler": handler.name, "meta": meta}
