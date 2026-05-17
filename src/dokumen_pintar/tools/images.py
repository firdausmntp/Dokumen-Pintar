"""Embedded image tools for Office formats (DOCX / PPTX) and PDF.

Office docs are ZIP packages with images stored under ``word/media/``,
``ppt/media/``, etc. This module exposes them as MCP tools so an agent
can list, extract, and replace images without leaving the workspace
sandbox. PDF image extraction is a best-effort read-only operation
because rebuilding a valid PDF after image swap is significantly
trickier than DOCX/PPTX.

Every mutating operation (``image_replace``) snapshots the source file
pre+post via ``ctx.versions``, mirroring the contract of every other
tool in the project.
"""

from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from ..context import AppContext
from ..errors import HandlerError, UnsupportedFormatError, ValidationError
from ..utils.locks import file_lock
from ._common import resolve_for_read, resolve_for_write, summarize_resolved

# Mapping: handler.name -> (zip-prefix-with-images, content-type-prefix)
_IMAGE_FORMATS: dict[str, tuple[str, ...]] = {
    "docx": ("word/media/", "word/embeddings/"),
    "pptx": ("ppt/media/", "ppt/embeddings/"),
}


def _list_zip_images(path: Path, prefixes: tuple[str, ...]) -> list[dict[str, Any]]:
    """Return a list of ``{index, internal_name, size, ext}`` for each image."""
    try:
        with zipfile.ZipFile(path) as zf:
            entries: list[dict[str, Any]] = []
            for name in zf.namelist():
                if not any(name.startswith(p) for p in prefixes):
                    continue
                # Skip directory entries (zero-size with trailing /).
                if name.endswith("/"):
                    continue
                info = zf.getinfo(name)
                ext = Path(name).suffix.lower()
                # Filter by extension to skip non-image media (audio/video).
                if ext not in {
                    ".png",
                    ".jpg",
                    ".jpeg",
                    ".gif",
                    ".bmp",
                    ".tif",
                    ".tiff",
                    ".webp",
                    ".svg",
                    ".emf",
                    ".wmf",
                }:
                    continue
                entries.append(
                    {
                        "index": len(entries),
                        "internal_name": name,
                        "size": info.file_size,
                        "ext": ext,
                    }
                )
            return entries
    except zipfile.BadZipFile as exc:
        raise HandlerError(f"not a valid zip-based document: {path} ({exc})") from exc


def _extract_pdf_images(path: Path) -> list[dict[str, Any]]:
    """List images embedded in a PDF via pypdf's resource walker."""
    try:
        import pypdf
    except ImportError as exc:  # pragma: no cover - dependency is required
        raise HandlerError("pypdf is required for PDF image listing") from exc
    try:
        reader = pypdf.PdfReader(str(path))
    except Exception as exc:  # noqa: BLE001 - pypdf raises a wide net
        raise HandlerError(f"cannot read PDF: {exc}") from exc
    if reader.is_encrypted:
        try:
            ok = reader.decrypt("")
        except Exception:  # noqa: BLE001
            ok = 0
        if not ok:
            raise HandlerError("PDF is encrypted; cannot extract images")
    entries: list[dict[str, Any]] = []
    for page_idx, page in enumerate(reader.pages):
        try:
            images = page.images
        except Exception:  # noqa: BLE001 - pypdf surfaces parser-specific errors
            continue
        for img in images:
            entries.append(
                {
                    "index": len(entries),
                    "page": page_idx,
                    "internal_name": getattr(img, "name", f"page{page_idx}_image"),
                    "size": len(getattr(img, "data", b"")),
                    "ext": Path(getattr(img, "name", "img")).suffix.lower() or ".bin",
                }
            )
    return entries


def _detect_format(ctx: AppContext, p: Path) -> str:
    handler = ctx.registry.for_path(p)
    if handler is None:
        raise UnsupportedFormatError(f"no handler for {p.suffix!r}")
    return handler.name


def register(mcp: FastMCP, ctx: AppContext) -> None:
    """Register image_list / image_extract / image_extract_all / image_replace."""

    @mcp.tool(
        name="image_list",
        description=(
            "List embedded images in a DOCX, PPTX, or PDF file. Returns a "
            "list of {index, internal_name, size, ext} entries. PDF entries "
            "additionally carry a `page` field. The `index` is stable for "
            "the same file revision and is the value to pass to "
            "image_extract / image_replace."
        ),
    )
    def image_list(path: str) -> dict[str, Any]:
        resolved = resolve_for_read(ctx, path)
        fmt = _detect_format(ctx, resolved.absolute)
        if fmt in _IMAGE_FORMATS:
            entries = _list_zip_images(resolved.absolute, _IMAGE_FORMATS[fmt])
        elif fmt == "pdf":
            entries = _extract_pdf_images(resolved.absolute)
        else:
            raise UnsupportedFormatError(
                f"image_list not supported for format {fmt!r} (supported: docx, pptx, pdf)"
            )
        return {
            **summarize_resolved(resolved),
            "format": fmt,
            "count": len(entries),
            "images": entries,
        }

    @mcp.tool(
        name="image_extract",
        description=(
            "Extract one embedded image to a destination file. Use index from "
            "image_list. The destination's extension is overridden to match "
            "the source image's actual ext. Refuses to overwrite unless "
            "overwrite=True."
        ),
    )
    def image_extract(
        path: str,
        index: int,
        dst: str,
        overwrite: bool = False,
    ) -> dict[str, Any]:
        if index < 0:
            raise ValidationError("index must be >= 0")
        resolved_src = resolve_for_read(ctx, path)
        resolved_dst = resolve_for_write(ctx, dst)
        fmt = _detect_format(ctx, resolved_src.absolute)
        if fmt not in _IMAGE_FORMATS and fmt != "pdf":
            raise UnsupportedFormatError(f"image_extract not supported for format {fmt!r}")

        if resolved_dst.absolute.exists() and not overwrite:
            raise ValidationError(
                f"destination exists: {resolved_dst.absolute}; pass overwrite=True to replace"
            )

        if fmt in _IMAGE_FORMATS:
            entries = _list_zip_images(resolved_src.absolute, _IMAGE_FORMATS[fmt])
            if index >= len(entries):
                raise ValidationError(f"image index {index} out of range (have {len(entries)})")
            internal = entries[index]["internal_name"]
            with zipfile.ZipFile(resolved_src.absolute) as zf:
                blob = zf.read(internal)
        else:  # pdf
            blob = _read_pdf_image_bytes(resolved_src.absolute, index)
            entries = _extract_pdf_images(resolved_src.absolute)
            if index >= len(entries):  # pragma: no cover - defensive double-check
                raise ValidationError(f"image index {index} out of range (have {len(entries)})")

        # Force the destination extension to match the source image type.
        actual_ext = entries[index]["ext"]
        target = resolved_dst.absolute
        if target.suffix.lower() != actual_ext:
            target = target.with_suffix(actual_ext)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(blob)
        ctx.audit.log(
            "image_extract",
            src=str(resolved_src.absolute),
            dst=str(target),
            index=index,
            size=len(blob),
        )
        return {
            "src": summarize_resolved(resolved_src),
            "dst": str(target),
            "size": len(blob),
            "ext": actual_ext,
        }

    @mcp.tool(
        name="image_extract_all",
        description=(
            "Extract every embedded image into `dst_dir`. Filenames follow "
            "`naming_pattern` which defaults to `image_{index:03d}{ext}`. "
            "Returns the list of files written."
        ),
    )
    def image_extract_all(
        path: str,
        dst_dir: str,
        naming_pattern: str = "image_{index:03d}{ext}",
    ) -> dict[str, Any]:
        resolved_src = resolve_for_read(ctx, path)
        resolved_dir = resolve_for_write(ctx, dst_dir)
        fmt = _detect_format(ctx, resolved_src.absolute)
        if fmt not in _IMAGE_FORMATS and fmt != "pdf":
            raise UnsupportedFormatError(f"image_extract_all not supported for format {fmt!r}")
        if fmt in _IMAGE_FORMATS:
            entries = _list_zip_images(resolved_src.absolute, _IMAGE_FORMATS[fmt])
            with zipfile.ZipFile(resolved_src.absolute) as zf:
                blobs = [zf.read(e["internal_name"]) for e in entries]
        else:  # pdf
            entries = _extract_pdf_images(resolved_src.absolute)
            blobs = [_read_pdf_image_bytes(resolved_src.absolute, i) for i in range(len(entries))]

        resolved_dir.absolute.mkdir(parents=True, exist_ok=True)
        written: list[dict[str, Any]] = []
        for entry, blob in zip(entries, blobs):
            filename = naming_pattern.format(index=entry["index"], ext=entry["ext"])
            target = resolved_dir.absolute / filename
            target.write_bytes(blob)
            written.append({"index": entry["index"], "path": str(target), "size": len(blob)})
        ctx.audit.log(
            "image_extract_all",
            src=str(resolved_src.absolute),
            dst_dir=str(resolved_dir.absolute),
            count=len(written),
        )
        return {
            "src": summarize_resolved(resolved_src),
            "dst_dir": str(resolved_dir.absolute),
            "count": len(written),
            "files": written,
        }

    @mcp.tool(
        name="image_replace",
        description=(
            "Replace an embedded image at `index` with the bytes from `src`. "
            "Only DOCX and PPTX are supported (PDF is read-only). The "
            "replacement keeps the same internal_name so existing references "
            "in the document continue to point at the new image. Snapshots "
            "the destination pre+post."
        ),
    )
    def image_replace(
        path: str,
        index: int,
        src: str,
    ) -> dict[str, Any]:
        if index < 0:
            raise ValidationError("index must be >= 0")
        resolved_dst = resolve_for_write(ctx, path)
        resolved_src = resolve_for_read(ctx, src)
        fmt = _detect_format(ctx, resolved_dst.absolute)
        if fmt not in _IMAGE_FORMATS:
            raise UnsupportedFormatError(
                f"image_replace not supported for format {fmt!r} (supported: docx, pptx)"
            )

        entries = _list_zip_images(resolved_dst.absolute, _IMAGE_FORMATS[fmt])
        if index >= len(entries):
            raise ValidationError(f"image index {index} out of range (have {len(entries)})")
        internal = entries[index]["internal_name"]
        new_bytes = resolved_src.absolute.read_bytes()

        with file_lock(resolved_dst.absolute):
            ctx.versions.snapshot(
                root_name=resolved_dst.root.name,
                rel_path=resolved_dst.rel_to_root.as_posix(),
                source=resolved_dst.absolute,
                action="image_replace_pre",
            )
            _replace_zip_member(resolved_dst.absolute, internal, new_bytes)
            snap = ctx.versions.snapshot(
                root_name=resolved_dst.root.name,
                rel_path=resolved_dst.rel_to_root.as_posix(),
                source=resolved_dst.absolute,
                action="image_replace_post",
            )
        ctx.audit.log(
            "image_replace",
            path=str(resolved_dst.absolute),
            src=str(resolved_src.absolute),
            index=index,
            internal_name=internal,
        )
        return {
            **summarize_resolved(resolved_dst),
            "index": index,
            "internal_name": internal,
            "size_old": entries[index]["size"],
            "size_new": len(new_bytes),
            "snapshot": snap,
        }


def _read_pdf_image_bytes(path: Path, index: int) -> bytes:
    """Return raw bytes of the Nth image found via pypdf page walking."""
    import pypdf

    reader = pypdf.PdfReader(str(path))
    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception:  # noqa: BLE001
            raise HandlerError("PDF is encrypted; cannot extract image")
    seen = 0
    for page in reader.pages:
        try:
            for img in page.images:
                if seen == index:
                    return getattr(img, "data", b"")
                seen += 1
        except Exception:  # noqa: BLE001
            continue
    raise ValidationError(f"image index {index} not found")


def _replace_zip_member(zip_path: Path, member: str, new_bytes: bytes) -> None:
    """Rewrite a ZIP archive replacing one member's bytes.

    Python's stdlib does not support in-place ZIP mutation, so we read
    every entry and write a fresh archive to a sibling tempfile, then
    swap. The original archive is left intact if the rebuild fails.
    """
    tmp = zip_path.with_suffix(zip_path.suffix + ".tmp")
    try:
        with (
            zipfile.ZipFile(zip_path, "r") as zin,
            zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout,
        ):
            for item in zin.infolist():
                if item.filename == member:
                    zout.writestr(item, new_bytes)
                else:
                    zout.writestr(item, zin.read(item.filename))
        # Replace original atomically (cross-platform best-effort).
        zip_path.write_bytes(tmp.read_bytes())
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:  # pragma: no cover - defensive
                pass
