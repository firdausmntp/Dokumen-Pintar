"""Content-level CRUD tools (text-oriented)."""

from __future__ import annotations

import re
from typing import Any

from mcp.server.fastmcp import FastMCP

from ..context import AppContext
from ..errors import HandlerError, UnsupportedFormatError, ValidationError
from ..utils.encoding import read_text, write_text
from ..utils.locks import file_lock
from ._common import (
    BINARY_CONTAINER_FORMATS,
    handler_for,
    refuse_binary_text_op,
    resolve_for_read,
    resolve_for_write,
    summarize_resolved,
)


def register(mcp: FastMCP, ctx: AppContext) -> None:
    def _snapshot(resolved, action: str):  # type: ignore[no-untyped-def]
        if resolved.absolute.exists() and resolved.absolute.is_file():
            return ctx.versions.snapshot(
                root_name=resolved.root.name,
                rel_path=resolved.rel_to_root.as_posix(),
                source=resolved.absolute,
                action=action,
            )
        return None

    def _read_for_text(resolved) -> tuple[str, str]:  # type: ignore[no-untyped-def]
        ctx.guard.ensure_within_size_limit(resolved.absolute)
        # Prefer handler-aware text extraction so DOCX/PDF etc still work.
        handler = ctx.registry.for_path(resolved.absolute)
        if handler is not None:
            try:
                text = handler.read_text(resolved.absolute)
                return text, "utf-8"
            except UnsupportedFormatError:
                pass
        return read_text(resolved.absolute, auto_detect=ctx.config.auto_detect_encoding)

    @mcp.tool(
        name="content_read",
        description=(
            "Read the textual content of a file. Optional line slicing keeps "
            "responses small. Works on text-like formats; DOCX/PDF/XLSX delegate "
            "to their handler's `read_text` view."
        ),
    )
    def content_read(
        path: str,
        start_line: int | None = None,
        end_line: int | None = None,
        encoding: str | None = None,
    ) -> dict[str, Any]:
        resolved = resolve_for_read(ctx, path)
        text, used_encoding = _read_for_text(resolved)
        lines = text.splitlines(keepends=True)
        if start_line is not None or end_line is not None:
            s = max(1, start_line or 1) - 1
            e = end_line if end_line is not None else len(lines)
            slice_text = "".join(lines[s:e])
        else:
            slice_text = text
        return {
            **summarize_resolved(resolved),
            "encoding": encoding or used_encoding,
            "line_count": len(lines),
            "content": slice_text,
        }

    @mcp.tool(
        name="content_write",
        description=(
            "Replace the entire textual content of a file. The previous version "
            "is snapshotted to the version store first. For text-like formats."
        ),
    )
    def content_write(path: str, content: str, encoding: str = "utf-8") -> dict[str, Any]:
        from ..handlers.base import HandlerCapability

        resolved = resolve_for_write(ctx, path)
        # Refuse mutating an existing binary container (docx/xlsx/pptx/pdf)
        # via raw-text write. Creating a brand-new docx is still allowed
        # because DocxHandler.write_text can synthesize one from paragraphs.
        refuse_binary_text_op(ctx, resolved, "content_write")
        with file_lock(resolved.absolute):
            _snapshot(resolved, "content_write_pre")
            handler = ctx.registry.for_path(resolved.absolute)
            resolved.absolute.parent.mkdir(parents=True, exist_ok=True)
            if handler is not None and HandlerCapability.WRITE_TEXT in handler.capabilities:
                # Use the handler's format-aware writer so JSON/YAML stay
                # valid, CSV preserves delimiters, and a new docx is built
                # via python-docx rather than written as raw bytes.
                try:
                    handler.write_text(resolved.absolute, content, encoding=encoding)
                except UnsupportedFormatError:
                    # Defensive fallback for text-like handlers that opt out at
                    # runtime. Safe here because binary container formats were
                    # already refused above (refuse_binary_text_op + elif below).
                    if handler.name in BINARY_CONTAINER_FORMATS:
                        raise
                    write_text(resolved.absolute, content, encoding=encoding)
            elif handler is not None and handler.name in {"xlsx", "pptx", "pdf"}:
                # Binary container with no WRITE_TEXT capability — refuse
                # rather than fall back to a raw byte write that would
                # produce a non-conforming file with a binary extension.
                raise UnsupportedFormatError(
                    f"content_write: {handler.name} has no write_text support; "
                    "use struct_set or a dedicated tool to build the file."
                )
            else:
                write_text(resolved.absolute, content, encoding=encoding)
            snap = _snapshot(resolved, "content_write_post")
        ctx.audit.log("content_write", path=str(resolved.absolute), root=resolved.root.name)
        return {**summarize_resolved(resolved), "snapshot": snap}

    @mcp.tool(
        name="content_append",
        description="Append text to the end of a text-like file.",
    )
    def content_append(path: str, content: str) -> dict[str, Any]:
        resolved = resolve_for_write(ctx, path)
        refuse_binary_text_op(ctx, resolved, "content_append")
        with file_lock(resolved.absolute):
            existing, used_enc = (
                _read_for_text(resolved)
                if resolved.absolute.exists()
                else ("", ctx.config.default_encoding)
            )
            _snapshot(resolved, "append_pre")
            new_text = existing + content
            write_text(resolved.absolute, new_text, encoding=used_enc)
            snap = _snapshot(resolved, "append_post")
        ctx.audit.log("content_append", path=str(resolved.absolute))
        return {**summarize_resolved(resolved), "snapshot": snap, "new_size": len(new_text)}

    @mcp.tool(
        name="content_insert",
        description=(
            "Insert text at `line_number` (1-based). Existing text from that line is shifted down."
        ),
    )
    def content_insert(path: str, line_number: int, content: str) -> dict[str, Any]:
        if line_number < 1:
            raise ValidationError("line_number must be >= 1")
        resolved = resolve_for_write(ctx, path)
        refuse_binary_text_op(ctx, resolved, "content_insert")
        with file_lock(resolved.absolute):
            existing, used_enc = (
                _read_for_text(resolved)
                if resolved.absolute.exists()
                else ("", ctx.config.default_encoding)
            )
            lines = existing.splitlines(keepends=True)
            idx = min(line_number - 1, len(lines))
            insert_block = content if content.endswith("\n") else content + "\n"
            new_text = "".join(lines[:idx]) + insert_block + "".join(lines[idx:])
            _snapshot(resolved, "insert_pre")
            write_text(resolved.absolute, new_text, encoding=used_enc)
            snap = _snapshot(resolved, "insert_post")
        ctx.audit.log("content_insert", path=str(resolved.absolute), line=line_number)
        return {**summarize_resolved(resolved), "snapshot": snap}

    @mcp.tool(
        name="content_replace",
        description=(
            "Find/replace within text. `regex=True` enables Python regex. "
            "`count=-1` replaces all occurrences."
        ),
    )
    def content_replace(
        path: str,
        old: str,
        new: str,
        count: int = -1,
        regex: bool = False,
    ) -> dict[str, Any]:
        resolved = resolve_for_write(ctx, path)
        refuse_binary_text_op(ctx, resolved, "content_replace")
        with file_lock(resolved.absolute):
            text, used_enc = _read_for_text(resolved)
            if regex:
                if count < 0:
                    new_text, n = re.subn(old, new, text)
                else:
                    new_text, n = re.subn(old, new, text, count=count)
            else:
                if count < 0:
                    n = text.count(old)
                    new_text = text.replace(old, new)
                else:
                    new_text = text.replace(old, new, count)
                    n = min(count, text.count(old))
            if n == 0:
                return {**summarize_resolved(resolved), "replacements": 0}
            _snapshot(resolved, "replace_pre")
            write_text(resolved.absolute, new_text, encoding=used_enc)
            snap = _snapshot(resolved, "replace_post")
        ctx.audit.log("content_replace", path=str(resolved.absolute), replacements=n, regex=regex)
        return {**summarize_resolved(resolved), "replacements": n, "snapshot": snap}

    @mcp.tool(
        name="content_delete_range",
        description="Delete lines in [start_line, end_line] (1-based, inclusive).",
    )
    def content_delete_range(path: str, start_line: int, end_line: int) -> dict[str, Any]:
        if start_line < 1 or end_line < start_line:
            raise ValidationError("invalid line range")
        resolved = resolve_for_write(ctx, path)
        refuse_binary_text_op(ctx, resolved, "content_delete_range")
        with file_lock(resolved.absolute):
            text, used_enc = _read_for_text(resolved)
            lines = text.splitlines(keepends=True)
            new_lines = lines[: start_line - 1] + lines[end_line:]
            new_text = "".join(new_lines)
            _snapshot(resolved, "delete_range_pre")
            write_text(resolved.absolute, new_text, encoding=used_enc)
            snap = _snapshot(resolved, "delete_range_post")
        ctx.audit.log(
            "content_delete_range",
            path=str(resolved.absolute),
            start=start_line,
            end=end_line,
        )
        return {**summarize_resolved(resolved), "snapshot": snap}

    @mcp.tool(
        name="content_patch",
        description=(
            "Apply a unified diff to a file. The diff must contain the file "
            "internals; headers (`---`, `+++`) are tolerated and ignored."
        ),
    )
    def content_patch(path: str, unified_diff: str) -> dict[str, Any]:
        resolved = resolve_for_write(ctx, path)
        refuse_binary_text_op(ctx, resolved, "content_patch")
        with file_lock(resolved.absolute):
            text, used_enc = _read_for_text(resolved)
            patched = _apply_unified_diff(text, unified_diff)
            _snapshot(resolved, "patch_pre")
            write_text(resolved.absolute, patched, encoding=used_enc)
            snap = _snapshot(resolved, "patch_post")
        ctx.audit.log("content_patch", path=str(resolved.absolute))
        return {**summarize_resolved(resolved), "snapshot": snap}


def _apply_unified_diff(original: str, diff_text: str) -> str:
    """Minimal unified-diff applier (no fuzz, exact context match)."""
    src = original.splitlines(keepends=False)
    out: list[str] = []
    i = 0
    diff_lines = diff_text.splitlines()
    di = 0
    while di < len(diff_lines):
        line = diff_lines[di]
        if line.startswith("---") or line.startswith("+++"):
            di += 1
            continue
        if line.startswith("@@"):
            m = re.match(r"@@ -([0-9]+)(?:,([0-9]+))? \+([0-9]+)(?:,([0-9]+))? @@", line)
            if not m:
                raise HandlerError(f"Invalid hunk header: {line}")
            old_start = int(m.group(1))
            # Flush untouched prefix.
            while i < old_start - 1 and i < len(src):
                out.append(src[i])
                i += 1
            di += 1
            while di < len(diff_lines) and not diff_lines[di].startswith("@@"):
                hl = diff_lines[di]
                if hl.startswith(" "):
                    if i >= len(src) or src[i] != hl[1:]:
                        raise HandlerError(f"Patch context mismatch at line {i + 1}")
                    out.append(src[i])
                    i += 1
                elif hl.startswith("-"):
                    if i >= len(src) or src[i] != hl[1:]:
                        raise HandlerError(f"Patch removal mismatch at line {i + 1}")
                    i += 1
                elif hl.startswith("+"):
                    out.append(hl[1:])
                elif hl == "":
                    out.append("")
                di += 1
            continue
        di += 1
    while i < len(src):
        out.append(src[i])
        i += 1
    trailing_nl = original.endswith("\n")
    text = "\n".join(out)
    if trailing_nl:
        text += "\n"
    return text
