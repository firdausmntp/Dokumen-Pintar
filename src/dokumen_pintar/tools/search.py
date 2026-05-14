"""Search tools: filename, content (plain), in-format, semantic."""

from __future__ import annotations

import fnmatch
import re
from pathlib import Path
from typing import Any, Iterator

from mcp.server.fastmcp import FastMCP

from ..context import AppContext
from ..errors import DokumenPintarError
from ..utils.globbing import compile_globs, any_match
from ._common import resolve_for_read


def _iter_files(
    ctx: AppContext,
    *,
    root_filter: str | None,
    glob: str | None,
) -> Iterator[tuple[str, Path, Path]]:
    """Yield (root_name, abs_path, root_abs) for each non-excluded file."""
    excludes = compile_globs(ctx.config.exclude_patterns)
    for root_cfg, root_abs in ctx.guard.roots:
        if root_filter and root_cfg.name != root_filter:
            continue
        if not root_abs.exists():
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
            if glob and not (fnmatch.fnmatch(rel, glob) or fnmatch.fnmatch(p.name, glob)):
                continue
            yield root_cfg.name, p, root_abs


def register(mcp: FastMCP, ctx: AppContext) -> None:
    @mcp.tool(
        name="search_filename",
        description=("Search files by filename glob across the workspace (or a specific root)."),
    )
    def search_filename(
        glob_pattern: str,
        root: str | None = None,
        limit: int = 200,
    ) -> dict[str, Any]:
        hits: list[dict[str, Any]] = []
        for root_name, p, root_abs in _iter_files(ctx, root_filter=root, glob=glob_pattern):
            hits.append(
                {
                    "uri": f"{root_name}:/{p.relative_to(root_abs).as_posix()}",
                    "absolute": str(p),
                    "size": p.stat().st_size,
                }
            )
            if len(hits) >= limit:
                break
        return {"glob": glob_pattern, "count": len(hits), "matches": hits}

    @mcp.tool(
        name="search_content",
        description=(
            "Plain-text content search across the workspace. `regex=True` to use "
            "Python regex. Files are read via their handler's `extract_for_search`."
        ),
    )
    def search_content(
        query: str,
        glob: str | None = None,
        root: str | None = None,
        regex: bool = False,
        case_sensitive: bool = False,
        max_results: int = 200,
        max_files: int = 5000,
    ) -> dict[str, Any]:
        flags = 0 if case_sensitive else re.IGNORECASE
        pattern = re.compile(query if regex else re.escape(query), flags)
        hits: list[dict[str, Any]] = []
        scanned = 0
        for root_name, p, root_abs in _iter_files(ctx, root_filter=root, glob=glob):
            scanned += 1
            if scanned > max_files:
                break
            handler = ctx.registry.for_path(p)
            if handler is None:
                continue
            try:
                ctx.guard.ensure_within_size_limit(p)
                text = handler.extract_for_search(p)
            except DokumenPintarError:
                continue
            except Exception:
                continue
            for m in pattern.finditer(text):
                line_no = text.count("\n", 0, m.start()) + 1
                line_start = text.rfind("\n", 0, m.start()) + 1
                line_end = text.find("\n", m.end())
                if line_end == -1:
                    line_end = len(text)
                hits.append(
                    {
                        "uri": f"{root_name}:/{p.relative_to(root_abs).as_posix()}",
                        "line": line_no,
                        "snippet": text[line_start:line_end][:240],
                        "match": m.group(0)[:120],
                    }
                )
                if len(hits) >= max_results:
                    return {"query": query, "matches": hits, "truncated": True}
        return {"query": query, "matches": hits, "truncated": False}

    @mcp.tool(
        name="search_in_format",
        description=(
            "Search inside a specific format (pdf, docx, xlsx, pptx, csv, xml, "
            "json, yaml, text). Useful when you only want to scan e.g. PDFs."
        ),
    )
    def search_in_format(
        query: str,
        format: str,
        glob: str | None = None,
        root: str | None = None,
        regex: bool = False,
        case_sensitive: bool = False,
        max_results: int = 200,
    ) -> dict[str, Any]:
        handler = ctx.registry.by_format(format)
        if handler is None:
            raise DokumenPintarError(f"Unknown format: {format}")
        flags = 0 if case_sensitive else re.IGNORECASE
        pattern = re.compile(query if regex else re.escape(query), flags)
        hits: list[dict[str, Any]] = []
        for root_name, p, root_abs in _iter_files(ctx, root_filter=root, glob=glob):
            if p.suffix.lower() not in handler.extensions:
                continue
            try:
                text = handler.extract_for_search(p)
            except DokumenPintarError:
                continue
            for m in pattern.finditer(text):
                line_no = text.count("\n", 0, m.start()) + 1
                line_start = text.rfind("\n", 0, m.start()) + 1
                line_end = text.find("\n", m.end())
                if line_end == -1:
                    line_end = len(text)
                hits.append(
                    {
                        "uri": f"{root_name}:/{p.relative_to(root_abs).as_posix()}",
                        "format": format,
                        "line": line_no,
                        "snippet": text[line_start:line_end][:240],
                    }
                )
                if len(hits) >= max_results:
                    return {"matches": hits, "truncated": True}
        return {"matches": hits, "truncated": False}

    if ctx.config.semantic_search.enabled:
        from ..semantic import SemanticIndex

        # Build / attach lazily; reuse a single instance.
        if not hasattr(ctx, "_semantic_index"):
            from pathlib import Path

            from platformdirs import user_data_dir

            default_idx = (
                Path(user_data_dir("dokumen-pintar", "dokumen-pintar")) / "semantic.sqlite"
            )
            ctx._semantic_index = SemanticIndex(  # type: ignore[attr-defined]
                ctx.config.semantic_search, default_path=default_idx
            )

        idx: SemanticIndex = ctx._semantic_index  # type: ignore[attr-defined]

        @mcp.tool(
            name="search_semantic",
            description=(
                "Semantic (vector) search using sentence-transformers. Documents "
                "must be indexed first via `semantic_index_path`."
            ),
        )
        def search_semantic(query: str, top_k: int = 10) -> dict[str, Any]:
            hits = idx.search(query, top_k=top_k)
            return {"query": query, "hits": [h.to_dict() for h in hits]}

        @mcp.tool(
            name="semantic_index_path",
            description="Index a file (extracted text) into the semantic store.",
        )
        def semantic_index_path(path: str) -> dict[str, Any]:
            resolved = resolve_for_read(ctx, path)
            handler = ctx.registry.for_path(resolved.absolute)
            if handler is None:
                raise DokumenPintarError(f"No handler for {resolved.absolute}")
            text = handler.extract_for_search(resolved.absolute)
            chunks = idx.index_document(str(resolved.absolute), text)
            return {"path": str(resolved.absolute), "chunks": chunks}

        @mcp.tool(
            name="semantic_stats",
            description="Statistics for the semantic index (chunk + document counts).",
        )
        def semantic_stats() -> dict[str, Any]:
            return idx.stats()
