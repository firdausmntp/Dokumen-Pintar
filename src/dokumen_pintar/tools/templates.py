"""Template rendering with Jinja2 syntax (docxtpl).

Renders a DOCX template that contains ``{{ variable }}`` placeholders,
``{% for %}`` loops, ``{% if %}`` conditionals, and ``{% tr %} / {% tbl %}
/ {% cell %}`` macros for repeating tabular content. Image variables can
be injected by passing a path-like value into ``inline_images`` - the
tool resolves it through PathGuard and substitutes a docxtpl
``InlineImage`` at render time.

This module also exposes a built-in templates registry so packaged
academic templates ship with the project and can be rendered by name.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from ..context import AppContext
from ..errors import HandlerError, UnsupportedFormatError, ValidationError
from ..utils.locks import file_lock
from ._common import resolve_for_read, resolve_for_write, summarize_resolved


# Templates registry directory (packaged with the project under templates/).
_REGISTRY_ROOT = Path(__file__).resolve().parent.parent.parent.parent / "templates"


def _registry_path(template_id: str) -> Path:
    """Convert ``category/name`` template id into the on-disk template path."""
    if not template_id or "/" not in template_id:
        raise ValidationError(f"template_id must be 'category/name' (got {template_id!r})")
    parts = template_id.strip("/").split("/")
    if len(parts) != 2 or any(not p or p.startswith(".") for p in parts):
        raise ValidationError(
            f"template_id must be 'category/name' with no '..' or empty parts (got {template_id!r})"
        )
    return _REGISTRY_ROOT / parts[0] / parts[1] / "template.docx"


def _registry_manifest(template_id: str) -> Path:  # pragma: no cover - helper for external callers
    parts = template_id.strip("/").split("/")
    return _REGISTRY_ROOT / parts[0] / parts[1] / "manifest.json"


def _list_registry() -> list[dict[str, Any]]:
    """Walk the templates/ tree and return a flat list of available templates."""
    if not _REGISTRY_ROOT.exists():
        return []
    out: list[dict[str, Any]] = []
    for category_dir in sorted(_REGISTRY_ROOT.iterdir()):
        if not category_dir.is_dir():
            continue
        for tpl_dir in sorted(category_dir.iterdir()):
            if not tpl_dir.is_dir():
                continue
            tpl_path = tpl_dir / "template.docx"
            manifest_path = tpl_dir / "manifest.json"
            if not tpl_path.exists():
                continue
            entry: dict[str, Any] = {
                "id": f"{category_dir.name}/{tpl_dir.name}",
                "category": category_dir.name,
                "name": tpl_dir.name,
                "template_path": str(tpl_path),
            }
            if manifest_path.exists():
                try:
                    entry["manifest"] = json.loads(manifest_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    entry["manifest"] = None
            out.append(entry)
    return out


def _build_inline_images(
    inline_images: dict[str, str] | None,
    ctx: AppContext,
) -> dict[str, Any]:
    """Resolve every path in ``inline_images`` through PathGuard and wrap as InlineImage."""
    if not inline_images:
        return {}
    from docxtpl import InlineImage
    from docx.shared import Mm

    resolved: dict[str, Any] = {}
    for var_name, spec in inline_images.items():
        if isinstance(spec, str):
            path_str, width_mm = spec, None
        elif isinstance(spec, dict):
            if "path" not in spec:
                raise ValidationError(f"inline_images[{var_name!r}] dict must contain 'path'")
            path_str = str(spec["path"])
            width_mm = spec.get("width_mm")
        else:
            raise ValidationError(f"inline_images[{var_name!r}] must be a path string or dict")
        path_resolved = resolve_for_read(ctx, path_str).absolute
        if not path_resolved.exists():
            raise ValidationError(f"inline image not found: {path_resolved}")
        # docxtpl's InlineImage needs the docxtpl object as first arg; the
        # tool builds that lazily after the template loads, so we stash
        # raw inputs here and finalise inside ``_render``.
        resolved[var_name] = {"path": str(path_resolved), "width_mm": width_mm}

    def _materialise(tpl: Any) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for k, v in resolved.items():
            if v["width_mm"] is not None:
                out[k] = InlineImage(tpl, v["path"], width=Mm(float(v["width_mm"])))
            else:
                out[k] = InlineImage(tpl, v["path"])
        return out

    # Python's typing wants a uniform dict; use a special marker key
    # that the renderer drains and replaces with materialised images.
    return {"__dp_inline_images__": _materialise}


def _render(
    template_path: Path,
    out_path: Path,
    *,
    vars: dict[str, Any],
    loops: dict[str, Any] | None,
    conditionals: dict[str, Any] | None,
    inline_images: dict[str, Any],
) -> None:
    """Load ``template_path`` via docxtpl, render with the merged context, save."""
    try:
        from docxtpl import DocxTemplate
    except ImportError as exc:  # pragma: no cover - hard dep
        raise HandlerError("docxtpl is required for template_render") from exc

    try:
        tpl = DocxTemplate(str(template_path))
    except Exception as exc:  # pragma: no cover - docxtpl typically defers errors to render()
        raise HandlerError(f"failed to load template: {template_path} ({exc})") from exc

    context: dict[str, Any] = dict(vars)
    if loops:
        for k, v in loops.items():
            if not isinstance(v, list):
                raise ValidationError(f"loops[{k!r}] must be a list (got {type(v).__name__})")
            context[k] = v
    if conditionals:
        for k, v in conditionals.items():
            context[k] = bool(v)

    # Materialise inline images now that we have the DocxTemplate instance.
    if "__dp_inline_images__" in inline_images:
        materialised = inline_images["__dp_inline_images__"](tpl)
        context.update(materialised)

    try:
        tpl.render(context)
        tpl.save(str(out_path))
    except Exception as exc:  # noqa: BLE001 - jinja2 + docxtpl raise various types
        raise HandlerError(f"failed to render template: {template_path} ({exc})") from exc


def register(mcp: FastMCP, ctx: AppContext) -> None:
    """Register template_render / template_list / template_install /
    template_render_named tools."""

    @mcp.tool(
        name="template_render",
        description=(
            "Render a Jinja2-style DOCX template into a new file. "
            "Supports `{{ variable }}` substitution, `{% for %}` loops, "
            "`{% if %}` conditionals, and docxtpl table macros "
            "(`{% tr %}`, `{% tbl %}`, `{% cell %}`). Images can be injected "
            "via `inline_images={var: 'workspace:/path.png'}` or "
            "`{var: {path: ..., width_mm: 60}}`. Refuses to overwrite "
            "unless `overwrite=True`. Snapshots pre+post."
        ),
    )
    def template_render(
        template: str,
        dst: str,
        vars: dict[str, Any] | None = None,
        loops: dict[str, Any] | None = None,
        conditionals: dict[str, Any] | None = None,
        inline_images: dict[str, Any] | None = None,
        overwrite: bool = False,
    ) -> dict[str, Any]:
        resolved_tpl = resolve_for_read(ctx, template)
        resolved_dst = resolve_for_write(ctx, dst)
        if resolved_tpl.absolute.suffix.lower() != ".docx":
            raise UnsupportedFormatError(
                f"template_render: template must be .docx, got {resolved_tpl.absolute.suffix!r}"
            )
        if resolved_dst.absolute.suffix.lower() != ".docx":
            raise UnsupportedFormatError(
                f"template_render: dst must be .docx, got {resolved_dst.absolute.suffix!r}"
            )
        if not resolved_tpl.absolute.exists():
            raise ValidationError(f"template not found: {resolved_tpl.absolute}")
        if resolved_dst.absolute.exists() and not overwrite:
            raise ValidationError(
                f"destination exists: {resolved_dst.absolute}; pass overwrite=True"
            )
        materialiser = _build_inline_images(inline_images, ctx)

        rel = resolved_dst.rel_to_root.as_posix()
        root_name = resolved_dst.root.name
        with file_lock(resolved_dst.absolute):
            if resolved_dst.absolute.exists():
                ctx.versions.snapshot(
                    root_name=root_name,
                    rel_path=rel,
                    source=resolved_dst.absolute,
                    action="template_render_pre",
                )
            _render(
                resolved_tpl.absolute,
                resolved_dst.absolute,
                vars=vars or {},
                loops=loops,
                conditionals=conditionals,
                inline_images=materialiser,
            )
            snap = ctx.versions.snapshot(
                root_name=root_name,
                rel_path=rel,
                source=resolved_dst.absolute,
                action="template_render_post",
            )
        ctx.audit.log(
            "template_render",
            template=str(resolved_tpl.absolute),
            dst=str(resolved_dst.absolute),
            vars=sorted((vars or {}).keys()),
            loops=sorted((loops or {}).keys()),
            conditionals=sorted((conditionals or {}).keys()),
        )
        return {
            "template": summarize_resolved(resolved_tpl),
            "dst": summarize_resolved(resolved_dst),
            "snapshot": snap,
        }

    @mcp.tool(
        name="template_list",
        description=(
            "List built-in templates from the registry under "
            "<repo>/templates/<category>/<name>/. Each entry includes "
            "an id (`category/name`), the absolute template_path, and the "
            "manifest.json contents (when present)."
        ),
    )
    def template_list(category: str | None = None) -> dict[str, Any]:
        entries = _list_registry()
        if category:
            entries = [e for e in entries if e["category"] == category]
        return {"count": len(entries), "templates": entries}

    @mcp.tool(
        name="template_install",
        description=(
            "Copy a built-in template into the workspace at `dst`. "
            "Use `template_list` first to see available ids."
        ),
    )
    def template_install(template_id: str, dst: str) -> dict[str, Any]:
        src_path = _registry_path(template_id)
        if not src_path.exists():
            raise ValidationError(f"template not found in registry: {template_id}")
        resolved_dst = resolve_for_write(ctx, dst)
        if resolved_dst.absolute.suffix.lower() != ".docx":
            raise UnsupportedFormatError(
                f"template_install: dst must be .docx, got {resolved_dst.absolute.suffix!r}"
            )
        resolved_dst.absolute.parent.mkdir(parents=True, exist_ok=True)
        resolved_dst.absolute.write_bytes(src_path.read_bytes())
        ctx.audit.log(
            "template_install",
            template_id=template_id,
            dst=str(resolved_dst.absolute),
        )
        return {
            "template_id": template_id,
            "src": str(src_path),
            "dst": summarize_resolved(resolved_dst),
        }

    @mcp.tool(
        name="template_render_named",
        description=(
            "Render a built-in template directly without copying it first. "
            "`template_id` is `category/name`; same vars/loops/conditionals/"
            "inline_images shape as `template_render`."
        ),
    )
    def template_render_named(
        template_id: str,
        dst: str,
        vars: dict[str, Any] | None = None,
        loops: dict[str, Any] | None = None,
        conditionals: dict[str, Any] | None = None,
        inline_images: dict[str, Any] | None = None,
        overwrite: bool = False,
    ) -> dict[str, Any]:
        src_path = _registry_path(template_id)
        if not src_path.exists():
            raise ValidationError(f"template not found in registry: {template_id}")
        resolved_dst = resolve_for_write(ctx, dst)
        if resolved_dst.absolute.suffix.lower() != ".docx":
            raise UnsupportedFormatError(
                f"template_render_named: dst must be .docx, got {resolved_dst.absolute.suffix!r}"
            )
        if resolved_dst.absolute.exists() and not overwrite:
            raise ValidationError(
                f"destination exists: {resolved_dst.absolute}; pass overwrite=True"
            )
        materialiser = _build_inline_images(inline_images, ctx)
        rel = resolved_dst.rel_to_root.as_posix()
        root_name = resolved_dst.root.name
        with file_lock(resolved_dst.absolute):
            if resolved_dst.absolute.exists():
                ctx.versions.snapshot(
                    root_name=root_name,
                    rel_path=rel,
                    source=resolved_dst.absolute,
                    action="template_render_named_pre",
                )
            _render(
                src_path,
                resolved_dst.absolute,
                vars=vars or {},
                loops=loops,
                conditionals=conditionals,
                inline_images=materialiser,
            )
            snap = ctx.versions.snapshot(
                root_name=root_name,
                rel_path=rel,
                source=resolved_dst.absolute,
                action="template_render_named_post",
            )
        ctx.audit.log(
            "template_render_named",
            template_id=template_id,
            dst=str(resolved_dst.absolute),
        )
        return {
            "template_id": template_id,
            "dst": summarize_resolved(resolved_dst),
            "snapshot": snap,
        }
