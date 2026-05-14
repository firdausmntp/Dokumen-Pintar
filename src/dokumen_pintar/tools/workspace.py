"""Workspace introspection tools."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from ..context import AppContext
from ..utils.mime import detect_format
from ._common import resolve_for_read, summarize_resolved


def register(mcp: FastMCP, ctx: AppContext) -> None:
    @mcp.tool(
        name="workspace_list_roots",
        description=(
            "List every configured workspace root with its absolute path and "
            "writable flag. Use this first to discover what the agent may touch."
        ),
    )
    def workspace_list_roots() -> dict[str, Any]:
        roots = []
        for r, abs_path in ctx.guard.roots:
            roots.append(
                {
                    "name": r.name,
                    "path": str(abs_path),
                    "writable": r.writable,
                    "exists": abs_path.exists(),
                }
            )
        return {"roots": roots, "count": len(roots)}

    @mcp.tool(
        name="workspace_stat",
        description=(
            "Return rich metadata about a path: existence, type, size, mtime, "
            "detected format, and a workspace URI (`<root>:/relative/path`)."
        ),
    )
    def workspace_stat(path: str) -> dict[str, Any]:
        resolved = ctx.guard.resolve(path)
        info: dict[str, Any] = summarize_resolved(resolved)
        p = resolved.absolute
        info["exists"] = p.exists()
        if not p.exists():
            return info
        st = p.stat()
        info["is_dir"] = p.is_dir()
        info["is_file"] = p.is_file()
        info["is_symlink"] = p.is_symlink()
        info["size"] = st.st_size
        info["mtime"] = datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat()
        if p.is_file():
            info["format"] = detect_format(p)
            handler = ctx.registry.for_path(p)
            info["handler"] = handler.name if handler else None
        return info

    @mcp.tool(
        name="workspace_tree",
        description=(
            "Recursive directory listing. `glob` filters file names. "
            "`depth` -1 = unlimited (default 3 to keep responses small)."
        ),
    )
    def workspace_tree(
        path: str,
        depth: int = 3,
        glob: str | None = None,
        include_hidden: bool = False,
    ) -> dict[str, Any]:
        resolved = resolve_for_read(ctx, path)
        root = resolved.absolute
        if not root.exists() or not root.is_dir():
            return {"error": "not a directory", "path": str(root)}

        from ..utils.globbing import compile_globs, any_match

        excludes = compile_globs(ctx.config.exclude_patterns)

        def walk(dir_path: Path, current_depth: int) -> list[dict[str, Any]]:
            entries: list[dict[str, Any]] = []
            try:
                children = sorted(dir_path.iterdir(), key=lambda c: (c.is_file(), c.name.lower()))
            except PermissionError:
                return entries
            for child in children:
                if not include_hidden and child.name.startswith("."):
                    if child.name not in {".github"}:
                        continue
                rel_to_root = child.relative_to(resolved.root_absolute).as_posix()
                if any_match(rel_to_root, excludes):
                    continue
                if child.is_dir():
                    node: dict[str, Any] = {
                        "name": child.name,
                        "type": "dir",
                        "rel": rel_to_root,
                    }
                    if depth == -1 or current_depth < depth:
                        node["children"] = walk(child, current_depth + 1)
                    entries.append(node)
                else:
                    if glob and not _glob_match(child.name, glob):
                        continue
                    try:
                        size = child.stat().st_size
                    except OSError:
                        size = -1
                    entries.append(
                        {
                            "name": child.name,
                            "type": "file",
                            "rel": rel_to_root,
                            "size": size,
                            "format": detect_format(child),
                        }
                    )
            return entries

        return {
            "root": resolved.root.name,
            "path": str(root),
            "tree": walk(root, 1),
        }


def _glob_match(name: str, pattern: str) -> bool:
    import fnmatch

    return fnmatch.fnmatch(name, pattern)
