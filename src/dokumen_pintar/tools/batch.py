"""Batch operations across multiple files (with dry-run by default)."""

from __future__ import annotations

import fnmatch
import re
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from ..context import AppContext
from ..errors import DokumenPintarError, ValidationError
from ..utils.encoding import read_text, write_text
from ..utils.globbing import any_match, compile_globs
from ..utils.locks import file_lock
from ._common import resolve_for_write


def _iter_writable_files(ctx: AppContext, glob_pattern: str) -> list[tuple[str, Path, Path]]:
    """List (root_name, abs_path, root_abs) for files matching the glob in writable roots."""
    excludes = compile_globs(ctx.config.exclude_patterns)
    out: list[tuple[str, Path, Path]] = []
    for root_cfg, root_abs in ctx.guard.roots:
        if not root_cfg.writable or not root_abs.exists():
            continue
        for p in root_abs.rglob("*"):
            if not p.is_file():
                continue
            try:
                rel = p.relative_to(root_abs).as_posix()
            except ValueError:
                continue
            if any_match(rel, excludes):
                continue
            if not (fnmatch.fnmatch(rel, glob_pattern) or fnmatch.fnmatch(p.name, glob_pattern)):
                continue
            out.append((root_cfg.name, p, root_abs))
    return out


def register(mcp: FastMCP, ctx: AppContext) -> None:
    @mcp.tool(
        name="batch_rename",
        description=(
            "Rename files matching `glob` by regex `pattern` -> `replacement`. "
            "`dry_run` is True by default; preview first, then run again with "
            "dry_run=False to apply."
        ),
    )
    def batch_rename(
        glob: str,
        pattern: str,
        replacement: str,
        dry_run: bool = True,
    ) -> dict[str, Any]:
        rx = re.compile(pattern)
        plan: list[dict[str, Any]] = []
        for root_name, p, root_abs in _iter_writable_files(ctx, glob):
            new_name = rx.sub(replacement, p.name)
            if new_name == p.name:
                continue
            new_path = p.with_name(new_name)
            plan.append(
                {
                    "from": f"{root_name}:/{p.relative_to(root_abs).as_posix()}",
                    "to": f"{root_name}:/{new_path.relative_to(root_abs).as_posix()}",
                    "absolute_from": str(p),
                    "absolute_to": str(new_path),
                }
            )
        if dry_run:
            return {"dry_run": True, "count": len(plan), "plan": plan}
        applied: list[dict[str, Any]] = []
        for item in plan:
            src_p = Path(item["absolute_from"])
            dst_p = Path(item["absolute_to"])
            if dst_p.exists():
                raise ValidationError(f"Target exists: {dst_p}")
            with file_lock(src_p):
                src_p.rename(dst_p)
            applied.append(item)
            ctx.audit.log("batch_rename", **item)
        return {"dry_run": False, "count": len(applied), "applied": applied}

    @mcp.tool(
        name="batch_replace_content",
        description=(
            "Find/replace inside text-like files matching `glob`. Snapshots each "
            "modified file. `dry_run` defaults to True."
        ),
    )
    def batch_replace_content(
        glob: str,
        old: str,
        new: str,
        regex: bool = False,
        dry_run: bool = True,
        case_sensitive: bool = True,
    ) -> dict[str, Any]:
        flags = 0 if case_sensitive else re.IGNORECASE
        pattern = re.compile(old if regex else re.escape(old), flags)
        plan: list[dict[str, Any]] = []
        for root_name, p, root_abs in _iter_writable_files(ctx, glob):
            handler = ctx.registry.for_path(p)
            if handler is None:
                continue
            try:
                text, used_enc = read_text(p, auto_detect=ctx.config.auto_detect_encoding)
            except OSError:
                continue
            new_text, n = pattern.subn(new, text)
            if n == 0:
                continue
            entry: dict[str, Any] = {
                "uri": f"{root_name}:/{p.relative_to(root_abs).as_posix()}",
                "absolute": str(p),
                "replacements": n,
            }
            plan.append(entry)
            if not dry_run:
                resolved = resolve_for_write(ctx, str(p))
                with file_lock(p):
                    ctx.versions.snapshot(
                        root_name=root_name,
                        rel_path=p.relative_to(root_abs).as_posix(),
                        source=p,
                        action="batch_replace_pre",
                    )
                    write_text(p, new_text, encoding=used_enc)
                    ctx.versions.snapshot(
                        root_name=root_name,
                        rel_path=p.relative_to(root_abs).as_posix(),
                        source=p,
                        action="batch_replace_post",
                    )
                ctx.audit.log("batch_replace_content", **entry)
        return {"dry_run": dry_run, "count": len(plan), "files": plan}

    @mcp.tool(
        name="batch_delete",
        description=(
            "Delete files matching `glob`. Always snapshots before deletion. "
            "`dry_run` defaults to True."
        ),
    )
    def batch_delete(glob: str, dry_run: bool = True) -> dict[str, Any]:
        plan: list[dict[str, Any]] = []
        for root_name, p, root_abs in _iter_writable_files(ctx, glob):
            entry = {
                "uri": f"{root_name}:/{p.relative_to(root_abs).as_posix()}",
                "absolute": str(p),
                "size": p.stat().st_size,
            }
            plan.append(entry)
            if not dry_run:
                with file_lock(p):
                    ctx.versions.snapshot(
                        root_name=root_name,
                        rel_path=p.relative_to(root_abs).as_posix(),
                        source=p,
                        action="batch_delete",
                    )
                    p.unlink()
                ctx.audit.log("batch_delete", **entry)
        return {"dry_run": dry_run, "count": len(plan), "files": plan}
