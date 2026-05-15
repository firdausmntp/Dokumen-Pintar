"""Authoring tools: compose DOCX/PDF from a JSON spec or Markdown source."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from ..authoring.markdown_to_spec import markdown_to_spec
from ..authoring.render_docx import render_docx
from ..authoring.render_pdf import render_pdf
from ..authoring.spec import DocumentSpec, SpecError, validate_spec
from ..context import AppContext
from ..errors import HandlerError, UnsupportedFormatError, ValidationError
from ..utils.locks import file_lock
from ._common import resolve_for_write, summarize_resolved


_DOCX_EXT = ".docx"
_PDF_EXT = ".pdf"


def _check_overwrite(target: Path, overwrite: bool) -> None:
    if target.exists() and not overwrite:
        raise ValidationError(
            f"refusing to overwrite existing file: {target} "
            "(pass overwrite=True to replace)"
        )


def _check_extension(target: Path, expected: str, op: str) -> None:
    if target.suffix.lower() != expected:
        raise UnsupportedFormatError(
            f"{op}: target {target.name!r} must have a {expected} extension"
        )


def _path_resolver_for(ctx: AppContext):  # type: ignore[no-untyped-def]
    """Return a resolver that turns workspace URIs (or relative paths) into
    absolute :class:`Path` objects, going through PathGuard for safety."""
    def _resolve(user_path: str) -> Path:
        try:
            r = ctx.guard.resolve(user_path, must_exist=True)
            return r.absolute
        except Exception:
            # Fall back to literal path; renderers will surface a clear
            # 'image not found' error if it does not exist.
            return Path(user_path)

    return _resolve


def _snapshot_pre(ctx: AppContext, target: Path, root_name: str, rel: str, action: str) -> None:
    if target.exists():
        try:
            ctx.versions.snapshot(
                root_name=root_name,
                rel_path=rel,
                source=target,
                action=action,
            )
        except Exception:  # noqa: BLE001
            # Snapshot failures must not block authoring — they are
            # best-effort safety nets.
            pass


def _snapshot_post(
    ctx: AppContext, target: Path, root_name: str, rel: str, action: str
) -> dict[str, Any] | None:
    try:
        return ctx.versions.snapshot(
            root_name=root_name,
            rel_path=rel,
            source=target,
            action=action,
        )
    except Exception:  # noqa: BLE001
        return None


def register(mcp: FastMCP, ctx: AppContext) -> None:
    @mcp.tool(
        name="validate_spec",
        description=(
            "Validate a document JSON spec without writing any file. Returns "
            "{valid, normalized} on success or {valid: false, error} on "
            "failure. Useful before calling compose_docx / compose_pdf."
        ),
    )
    def validate_spec_tool(spec: dict[str, Any] | str) -> dict[str, Any]:
        try:
            doc = validate_spec(spec)
        except SpecError as exc:
            return {"valid": False, "error": str(exc)}
        return {"valid": True, "normalized": doc.to_dict()}

    @mcp.tool(
        name="compose_docx",
        description=(
            "Render a JSON document spec to a `.docx` file. Block types: "
            "heading, paragraph, list, table, image, page_break, code, math, "
            "hr, blockquote. Refuses to overwrite unless `overwrite=True`. "
            "Snapshots pre+post."
        ),
    )
    def compose_docx(
        path: str,
        spec: dict[str, Any] | str,
        overwrite: bool = False,
    ) -> dict[str, Any]:
        resolved = resolve_for_write(ctx, path)
        target = resolved.absolute
        _check_extension(target, _DOCX_EXT, "compose_docx")
        _check_overwrite(target, overwrite)
        try:
            doc_spec: DocumentSpec = validate_spec(spec)
        except SpecError as exc:
            raise ValidationError(f"invalid spec: {exc}") from exc

        rel = resolved.rel_to_root.as_posix()
        root_name = resolved.root.name
        with file_lock(target):
            _snapshot_pre(ctx, target, root_name, rel, "compose_docx_pre")
            try:
                render_docx(doc_spec, target, path_resolver=_path_resolver_for(ctx))
            except HandlerError:
                raise
            snap = _snapshot_post(ctx, target, root_name, rel, "compose_docx_post")
        ctx.audit.log("compose_docx", path=str(target), blocks=len(doc_spec.blocks))
        return {
            **summarize_resolved(resolved),
            "blocks": len(doc_spec.blocks),
            "snapshot": snap,
        }

    @mcp.tool(
        name="compose_pdf",
        description=(
            "Render a JSON document spec to a `.pdf` file (reportlab). Same "
            "block schema as compose_docx. Refuses to overwrite unless "
            "`overwrite=True`."
        ),
    )
    def compose_pdf(
        path: str,
        spec: dict[str, Any] | str,
        overwrite: bool = False,
    ) -> dict[str, Any]:
        resolved = resolve_for_write(ctx, path)
        target = resolved.absolute
        _check_extension(target, _PDF_EXT, "compose_pdf")
        _check_overwrite(target, overwrite)
        try:
            doc_spec: DocumentSpec = validate_spec(spec)
        except SpecError as exc:
            raise ValidationError(f"invalid spec: {exc}") from exc

        rel = resolved.rel_to_root.as_posix()
        root_name = resolved.root.name
        with file_lock(target):
            _snapshot_pre(ctx, target, root_name, rel, "compose_pdf_pre")
            render_pdf(doc_spec, target, path_resolver=_path_resolver_for(ctx))
            snap = _snapshot_post(ctx, target, root_name, rel, "compose_pdf_post")
        ctx.audit.log("compose_pdf", path=str(target), blocks=len(doc_spec.blocks))
        return {
            **summarize_resolved(resolved),
            "blocks": len(doc_spec.blocks),
            "snapshot": snap,
        }

    @mcp.tool(
        name="compose_from_markdown",
        description=(
            "Convert a Markdown source string into a document spec, then "
            "render it to `.docx` or `.pdf` (selected by the target's "
            "extension or the explicit `format` argument)."
        ),
    )
    def compose_from_markdown(
        path: str,
        markdown: str,
        format: str | None = None,
        meta: dict[str, Any] | None = None,
        overwrite: bool = False,
    ) -> dict[str, Any]:
        if not isinstance(markdown, str) or not markdown.strip():
            raise ValidationError("markdown must be a non-empty string")
        resolved = resolve_for_write(ctx, path)
        target = resolved.absolute
        suffix = target.suffix.lower()
        fmt = (format or "").lower() or {
            _DOCX_EXT: "docx",
            _PDF_EXT: "pdf",
        }.get(suffix, "")
        if fmt not in ("docx", "pdf"):
            raise UnsupportedFormatError(
                "compose_from_markdown: target must end in .docx or .pdf, "
                "or pass format='docx'|'pdf' explicitly"
            )
        expected_ext = _DOCX_EXT if fmt == "docx" else _PDF_EXT
        _check_extension(target, expected_ext, "compose_from_markdown")
        _check_overwrite(target, overwrite)
        try:
            doc_spec = markdown_to_spec(markdown, meta=meta)
        except SpecError as exc:
            raise ValidationError(f"invalid markdown spec: {exc}") from exc

        rel = resolved.rel_to_root.as_posix()
        root_name = resolved.root.name
        with file_lock(target):
            _snapshot_pre(ctx, target, root_name, rel, f"compose_md_{fmt}_pre")
            if fmt == "docx":
                render_docx(doc_spec, target, path_resolver=_path_resolver_for(ctx))
            else:
                render_pdf(doc_spec, target, path_resolver=_path_resolver_for(ctx))
            snap = _snapshot_post(ctx, target, root_name, rel, f"compose_md_{fmt}_post")
        ctx.audit.log(
            "compose_from_markdown",
            path=str(target),
            format=fmt,
            blocks=len(doc_spec.blocks),
        )
        return {
            **summarize_resolved(resolved),
            "format": fmt,
            "blocks": len(doc_spec.blocks),
            "snapshot": snap,
        }
