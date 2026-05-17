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


def _dir_size(path: Path) -> int:
    """Sum of all file sizes under ``path`` (best-effort, OSError -> 0)."""
    total = 0
    try:
        for child in path.rglob("*"):
            try:
                if child.is_file():  # pragma: no branch
                    total += child.stat().st_size
            except OSError:  # pragma: no cover - hard to hit between rglob and stat
                continue
    except OSError:
        return 0
    return total


def register_diagnose(mcp: FastMCP, ctx: AppContext) -> None:
    """Register the workspace_diagnose health-check tool."""

    @mcp.tool(
        name="workspace_diagnose",
        description=(
            "Health check across config, snapshot store, audit log, extract "
            "cache, semantic index, and per-root disk usage. Read-only - never "
            "mutates anything. Returns a diagnostics report with warnings for "
            "common operational issues (missing roots, oversized stores, "
            "stale caches). Use this when something feels off."
        ),
    )
    def workspace_diagnose() -> dict[str, Any]:
        cfg = ctx.config
        warnings: list[str] = []

        # Config + roots ----------------------------------------------------
        roots_info: list[dict[str, Any]] = []
        for root_cfg, abs_path in ctx.guard.roots:
            exists = abs_path.exists()
            entry: dict[str, Any] = {
                "name": root_cfg.name,
                "path": str(abs_path),
                "writable": root_cfg.writable,
                "exists": exists,
            }
            if exists and abs_path.is_dir():
                entry["disk_usage_bytes"] = _dir_size(abs_path)
            else:
                entry["disk_usage_bytes"] = None
            if not exists:
                warnings.append(f"root '{root_cfg.name}' path does not exist: {abs_path}")
            roots_info.append(entry)

        # Snapshot store ----------------------------------------------------
        snapshot_info: dict[str, Any] = {
            "enabled": cfg.versioning.enabled,
            "storage_mode": cfg.versioning.storage_mode,
            "retention_days": cfg.versioning.retention_days,
            "max_versions_per_file": cfg.versioning.max_versions_per_file,
        }
        try:
            db_path = Path(ctx.versions._db_path)  # type: ignore[attr-defined]
            snapshot_info["index_db"] = str(db_path)
            snapshot_info["index_db_size_bytes"] = db_path.stat().st_size if db_path.exists() else 0
        except (AttributeError, OSError):  # pragma: no cover - defensive
            snapshot_info["index_db"] = None

        try:
            snapshot_info["snapshot_count"] = ctx.versions.count_all()  # type: ignore[attr-defined]
        except AttributeError:
            # Older VersionStore without the helper - count via SQL fallback.
            snapshot_info["snapshot_count"] = _count_snapshots_via_sql(ctx)

        # Audit log ---------------------------------------------------------
        audit_info: dict[str, Any] = {
            "enabled": cfg.audit.enabled,
            "path": str(ctx.audit.path),
        }
        try:
            audit_path = Path(ctx.audit.path)
            if audit_path.exists():
                audit_info["size_bytes"] = audit_path.stat().st_size
                # Cheap line count (audit is JSONL).
                with audit_path.open("rb") as fh:
                    audit_info["entries"] = sum(1 for _ in fh)
            else:
                audit_info["size_bytes"] = 0
                audit_info["entries"] = 0
        except OSError:
            audit_info["size_bytes"] = None
            audit_info["entries"] = None

        # Extract cache -----------------------------------------------------
        cache_info: dict[str, Any] = {
            "enabled": ctx.extract_cache.enabled,
            "path": str(ctx.extract_cache.db_path),
        }
        try:
            cache_path = Path(ctx.extract_cache.db_path)
            cache_info["size_bytes"] = cache_path.stat().st_size if cache_path.exists() else 0
        except OSError:  # pragma: no cover - defensive
            cache_info["size_bytes"] = None

        # Semantic index (optional) ----------------------------------------
        semantic_info: dict[str, Any] = {"enabled": cfg.semantic_search.enabled}
        if hasattr(ctx, "_semantic_index"):
            try:
                stats = ctx._semantic_index.stats()  # type: ignore[attr-defined]
                semantic_info["chunks"] = stats.get("chunks")
                semantic_info["documents"] = stats.get("documents")
                semantic_info["model"] = stats.get("model")
            except Exception:  # noqa: BLE001 - best effort
                pass

        # Heuristic warnings ------------------------------------------------
        snap_db_size = snapshot_info.get("index_db_size_bytes") or 0
        if snap_db_size > 100 * 1024 * 1024:
            warnings.append(
                f"snapshot index db is {snap_db_size // (1024 * 1024)} MB "
                "(> 100 MB) - consider version_purge"
            )
        if audit_info.get("size_bytes") and audit_info["size_bytes"] > 50 * 1024 * 1024:
            warnings.append(
                f"audit log is {audit_info['size_bytes'] // (1024 * 1024)} MB "
                "(> 50 MB) - consider rotating or archiving"
            )
        if cache_info.get("size_bytes") and cache_info["size_bytes"] > 200 * 1024 * 1024:
            warnings.append(
                f"extract cache is {cache_info['size_bytes'] // (1024 * 1024)} MB "
                "(> 200 MB) - call extract_cache.clear() to reset"
            )

        return {
            "config": {
                "max_file_size_mb": cfg.max_file_size_mb,
                "default_encoding": cfg.default_encoding,
                "auto_detect_encoding": cfg.auto_detect_encoding,
                "exclude_patterns": list(cfg.exclude_patterns),
            },
            "roots": roots_info,
            "snapshot_store": snapshot_info,
            "audit_log": audit_info,
            "extract_cache": cache_info,
            "semantic_search": semantic_info,
            "warnings": warnings,
        }


def _count_snapshots_via_sql(ctx: AppContext) -> int:
    """Fallback snapshot counter when VersionStore has no count_all helper."""
    import sqlite3
    from contextlib import closing

    try:
        db_path = Path(ctx.versions._db_path)  # type: ignore[attr-defined]
    except AttributeError:  # pragma: no cover - defensive
        return -1
    if not db_path.exists():
        return 0
    try:
        with closing(sqlite3.connect(db_path)) as conn:
            row = conn.execute("SELECT COUNT(*) FROM versions").fetchone()
            return int(row[0]) if row else 0
    except sqlite3.Error:  # pragma: no cover - defensive
        return -1
