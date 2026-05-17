"""DOCX → Markdown rendering via mammoth + html2text.

Mammoth handles the structured DOCX parsing (styles, lists, headings,
images) and produces HTML; html2text then converts the HTML into clean
Markdown that supports tables, code blocks, and nested lists.

The two-step pipeline is necessary because mammoth's native markdown
writer drops tables silently. Going through HTML preserves them.

Image extraction writes each embedded image to ``dst_dir/images/``
inside the workspace sandbox; the resulting Markdown references them
with relative ``images/<uuid>.<ext>`` paths.
"""

from __future__ import annotations

import mimetypes
import uuid
import warnings
from pathlib import Path
from typing import Any, Callable

import html2text
import mammoth

from ..errors import HandlerError


def _make_image_converter(
    images_dir: Path,
    *,
    extract_images: bool,
) -> Callable[[Any], dict[str, str]] | None:
    """Return a mammoth image converter that writes blobs to ``images_dir``.

    Returns ``None`` when ``extract_images=False`` so mammoth falls back
    to inline base64 ``data:`` URIs (still readable, no filesystem writes).
    """
    if not extract_images:
        return None

    images_dir.mkdir(parents=True, exist_ok=True)

    def _save(image: Any) -> dict[str, str]:
        ext = mimetypes.guess_extension(image.content_type) or ".bin"
        if ext == ".jpe" or ext == ".jpeg":  # pragma: no cover - mimetypes platform variance
            ext = ".jpg"
        filename = f"{uuid.uuid4().hex}{ext}"
        dest = images_dir / filename
        with image.open() as data:
            dest.write_bytes(data.read())
        return {"src": f"images/{filename}"}

    return mammoth.images.img_element(_save)


def render_docx_to_markdown(
    src: Path,
    dst: Path,
    *,
    extract_images: bool = True,
    style_map: str = "",
    body_width: int = 0,
) -> dict[str, Any]:
    """Convert a DOCX file at ``src`` to Markdown saved at ``dst``.

    Pipeline: ``mammoth.convert_to_html`` (structured + style-mapped)
    → ``html2text.HTML2Text`` (markdown with table/code-block support).

    Args:
        src: Absolute path to the source DOCX (caller's responsibility to
            sandbox via PathGuard).
        dst: Absolute path for the Markdown output. Must end in ``.md``.
            Images, when extracted, land in ``dst.parent/images/``.
        extract_images: When True (default) writes images to disk and
            references them with relative paths. When False, mammoth
            inlines them as base64 data URIs.
        style_map: Optional newline-separated mammoth style rules merged
            on top of the defaults. Applies before HTML conversion.
        body_width: Wrap column for the markdown writer. ``0`` disables
            wrapping (recommended for round-tripping).

    Returns:
        ``{"path": str, "size": int, "warnings": list[str]}``.
    """
    images_dir = dst.parent / "images"
    convert_image = _make_image_converter(images_dir, extract_images=extract_images)

    extra_map = "\n".join(
        filter(
            None,
            [
                style_map,
                # Drop comment references - they aren't part of the body.
                "comment-reference =>",
            ],
        )
    )

    try:
        with src.open("rb") as fh:
            kwargs: dict[str, Any] = {"style_map": extra_map}
            if convert_image is not None:
                kwargs["convert_image"] = convert_image
            result = mammoth.convert_to_html(fh, **kwargs)
    except (OSError, KeyError, ValueError) as exc:
        raise HandlerError(f"failed to convert docx to markdown: {src} ({exc})") from exc

    h = html2text.HTML2Text()
    h.body_width = body_width
    h.unicode_snob = True
    h.protect_links = True
    h.escape_snob = False
    md = h.handle(result.value)

    if not md.strip():
        raise HandlerError(f"document produced no markdown content: {src}")

    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(md, encoding="utf-8")

    return {
        "path": str(dst),
        "size": len(md.encode("utf-8")),
        "warnings": [f"{m.type}: {m.message}" for m in result.messages],
    }


# Capture mammoth warnings without polluting stderr in tests.
warnings.filterwarnings("default", category=UserWarning, module=__name__)
