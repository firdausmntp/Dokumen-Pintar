"""Search tools: filename, content (plain), in-format, semantic."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from ..context import AppContext
from ..errors import DokumenPintarError
from ..utils.walking import iter_files
from ._common import resolve_for_read


def _docx_heading_context(path: Path) -> dict[str, Any] | None:
    """Build a heading-breadcrumb map for a DOCX file.

    Returns ``{"text": "...", "heading_map": {paragraph_idx: "BAB I > 1.1"}, "lines": [...]}``
    or ``None`` if the file isn't a DOCX or python-docx fails to load it.
    The ``lines`` list is the per-paragraph extracted text (1:1 with
    paragraph index), suitable for matching ``search_content`` hits to
    a structural location.
    """
    if path.suffix.lower() != ".docx":
        return None
    try:
        from docx import Document  # local import - keeps cold path lean
    except ImportError:  # pragma: no cover - python-docx is a hard dep
        return None
    try:
        doc = Document(str(path))
    except Exception:  # noqa: BLE001 - python-docx surfaces many exception types
        return None

    breadcrumb: list[tuple[int, str]] = []  # (level, text) stack
    heading_map: dict[int, str] = {}
    lines: list[str] = []
    for idx, para in enumerate(doc.paragraphs):
        style_name = getattr(getattr(para, "style", None), "name", "") or ""
        m = re.match(r"^[Hh]eading\s+(\d+)$", style_name.strip())
        if m:
            level = int(m.group(1))
            while breadcrumb and breadcrumb[-1][0] >= level:
                breadcrumb.pop()
            breadcrumb.append((level, para.text or ""))
        elif style_name.lower() == "title":
            breadcrumb = [(0, para.text or "")]
        heading_map[idx] = " > ".join(text for _, text in breadcrumb if text)
        lines.append(para.text or "")
    return {
        "text": "\n".join(lines),
        "heading_map": heading_map,
        "lines": lines,
    }


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
        for root_name, p, root_abs in iter_files(ctx, root_filter=root, glob=glob_pattern):
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
            "Python regex. Files are read via their handler's `extract_for_search`. "
            "Set `include_context=True` to enrich each hit with structural location "
            "(heading_path + paragraph_index for DOCX). Set `language='id'` and "
            "`stem=True` to enable Sastrawi-based Indonesian stemming - the query "
            "and document text are both stemmed before matching, so 'mengatakan' "
            "matches 'berkata', 'perkataan', etc. Default False keeps the response "
            "shape backwards-compatible with v1.0.x."
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
        include_context: bool = False,
        language: str | None = None,
        stem: bool = False,
    ) -> dict[str, Any]:
        if stem and language not in ("id",):
            raise DokumenPintarError(f"stemming requires language='id' (got language={language!r})")
        flags = 0 if case_sensitive else re.IGNORECASE
        # Pre-stem the query when Indonesian stemming is requested. The
        # pattern still runs against (also-stemmed) document text below.
        effective_query = query
        if stem:
            try:
                from ..utils.stemming_id import stem_text
            except ImportError as exc:  # pragma: no cover - Sastrawi is bundled in v1.1.0
                raise DokumenPintarError(
                    "Indonesian stemming requires Sastrawi. "
                    "Install with: pip install dokumen-pintar[indonesian]"
                ) from exc
            effective_query = stem_text(query)
        pattern = re.compile(effective_query if regex else re.escape(effective_query), flags)
        hits: list[dict[str, Any]] = []
        scanned = 0
        for root_name, p, root_abs in iter_files(ctx, root_filter=root, glob=glob):
            scanned += 1
            if scanned > max_files:
                break
            handler = ctx.registry.for_path(p)
            if handler is None:
                continue
            try:
                ctx.guard.ensure_within_size_limit(p)
                text = ctx.extract_cache.get_or_extract(p, handler.extract_for_search)
            except DokumenPintarError:
                continue
            except Exception:
                continue
            search_text = text
            if stem:
                from ..utils.stemming_id import stem_text as _stem

                search_text = _stem(text)

            # Pre-compute heading context per DOCX once (re-used across all hits).
            ctx_info = (
                _docx_heading_context(p) if include_context and handler.name == "docx" else None
            )
            if ctx_info is not None:
                # When we have structured context, run the regex against the
                # paragraph-by-paragraph text so paragraph_index is meaningful.
                # The cached extract is still used for the snippet so callers
                # see what they expected - tables are included, etc.
                heading_map = ctx_info["heading_map"]
                lines = ctx_info["lines"]
            else:
                heading_map = None
                lines = None

            for m in pattern.finditer(search_text):
                line_no = search_text.count("\n", 0, m.start()) + 1
                line_start = search_text.rfind("\n", 0, m.start()) + 1
                line_end = search_text.find("\n", m.end())
                if line_end == -1:
                    line_end = len(search_text)
                hit: dict[str, Any] = {
                    "uri": f"{root_name}:/{p.relative_to(root_abs).as_posix()}",
                    "line": line_no,
                    "snippet": search_text[line_start:line_end][:240],
                    "match": m.group(0)[:120],
                }
                if include_context and ctx_info is not None:
                    snippet_line = search_text[line_start:line_end]
                    para_idx: int | None = None
                    for i, line in enumerate(lines):  # type: ignore[arg-type]
                        if line == snippet_line:
                            para_idx = i
                            break
                    hit["context"] = {
                        "format": "docx",
                        "paragraph_index": para_idx,
                        "heading_path": (
                            heading_map.get(para_idx, "")  # type: ignore[union-attr]
                            if para_idx is not None
                            else ""
                        ),
                    }
                hits.append(hit)
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
        for root_name, p, root_abs in iter_files(ctx, root_filter=root, glob=glob):
            if p.suffix.lower() not in handler.extensions:
                continue
            try:
                text = ctx.extract_cache.get_or_extract(p, handler.extract_for_search)
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
