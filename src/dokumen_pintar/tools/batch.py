"""Batch operations across multiple files (with dry-run by default)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from ..context import AppContext
from ..errors import ValidationError
from ..utils.encoding import read_text, write_text
from ..utils.locks import file_lock
from ..utils.walking import iter_files
from ._common import resolve_for_write

# Formats that are binary containers (ZIP, OLE, PDF) — never safe for raw
# text find-and-replace, even though their handlers expose WRITE_TEXT
# (which goes through the format-aware writer, not raw bytes).
_BINARY_FORMATS = frozenset({"docx", "xlsx", "pptx", "pdf"})

# Extensions matching _BINARY_FORMATS plus a handful of common archive /
# image / audio formats. Used as a fast pre-filter so we can skip the
# 8KB nul-byte probe entirely for files that are obviously binary.
_BINARY_EXTENSIONS = frozenset(
    {
        ".docx",
        ".xlsx",
        ".pptx",
        ".pdf",
        ".zip",
        ".tar",
        ".gz",
        ".bz2",
        ".xz",
        ".7z",
        ".rar",
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".bmp",
        ".webp",
        ".tif",
        ".tiff",
        ".ico",
        ".mp3",
        ".mp4",
        ".wav",
        ".avi",
        ".mov",
        ".mkv",
        ".flac",
        ".ogg",
        ".exe",
        ".dll",
        ".so",
        ".dylib",
        ".bin",
        ".o",
        ".obj",
        ".class",
        ".pyc",
        ".pyd",
        ".whl",
    }
)


def _looks_binary(path: Path, sample_size: int = 8192) -> bool:
    """Return True if the file is binary by extension or first-chunk probe."""
    if path.suffix.lower() in _BINARY_EXTENSIONS:
        return True
    try:
        with path.open("rb") as fh:
            chunk = fh.read(sample_size)
    except OSError:
        return True
    return b"\x00" in chunk


def _iter_writable_files(ctx: AppContext, glob_pattern: str) -> list[tuple[str, Path, Path]]:
    """List ``(root_name, abs, root_abs)`` for matching files in writable roots."""
    return list(iter_files(ctx, glob=glob_pattern, writable_only=True))


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
        skipped: list[dict[str, Any]] = []
        max_bytes = ctx.config.max_file_size_bytes
        for root_name, p, root_abs in _iter_writable_files(ctx, glob):
            uri = f"{root_name}:/{p.relative_to(root_abs).as_posix()}"
            handler = ctx.registry.for_path(p)
            if handler is None:
                skipped.append({"uri": uri, "reason": "no_handler"})
                continue
            # Refuse to mangle binary container formats (docx, xlsx, pptx, pdf).
            if handler.name in _BINARY_FORMATS:
                skipped.append({"uri": uri, "reason": "binary_format"})
                continue
            # Skip files that look binary (null bytes in head).
            if _looks_binary(p):
                skipped.append({"uri": uri, "reason": "binary_content"})
                continue
            # Skip oversized files to prevent regex hangs / memory blow-ups.
            try:
                if p.stat().st_size > max_bytes:
                    skipped.append({"uri": uri, "reason": "exceeds_max_file_size"})
                    continue
            except OSError:
                skipped.append({"uri": uri, "reason": "stat_failed"})
                continue
            try:
                text, used_enc = read_text(p, auto_detect=ctx.config.auto_detect_encoding)
            except OSError:
                skipped.append({"uri": uri, "reason": "read_failed"})
                continue
            new_text, n = pattern.subn(new, text)
            if n == 0:
                continue
            entry: dict[str, Any] = {
                "uri": uri,
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
        result: dict[str, Any] = {"dry_run": dry_run, "count": len(plan), "files": plan}
        if skipped:
            result["skipped"] = skipped
            summary: dict[str, int] = {}
            for s in skipped:
                summary[s["reason"]] = summary.get(s["reason"], 0) + 1
            result["skipped_summary"] = summary
        return result

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
