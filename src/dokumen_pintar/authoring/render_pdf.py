"""Render a :class:`DocumentSpec` to a `.pdf` file via reportlab."""

from __future__ import annotations

import html
from pathlib import Path
from typing import Any, Callable

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable,
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from dokumen_pintar.errors import HandlerError

from .spec import DocumentSpec


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    code_style = ParagraphStyle(
        "Code",
        parent=base["Code"],
        fontName="Courier",
        fontSize=9,
        backColor=colors.whitesmoke,
        borderPadding=4,
        leading=11,
    )
    blockquote = ParagraphStyle(
        "Blockquote",
        parent=base["BodyText"],
        leftIndent=18,
        textColor=colors.HexColor("#444444"),
        italic=True,
    )
    caption = ParagraphStyle(
        "Caption",
        parent=base["Italic"],
        fontSize=9,
        alignment=1,  # TA_CENTER
        textColor=colors.HexColor("#555555"),
    )
    return {
        "Title": base["Title"],
        "Heading1": base["Heading1"],
        "Heading2": base["Heading2"],
        "Heading3": base["Heading3"],
        "Heading4": base["Heading4"],
        "Heading5": base["Heading5"],
        "Heading6": base["Heading6"],
        "Body": base["BodyText"],
        "Bullet": base["Bullet"],
        "Code": code_style,
        "Blockquote": blockquote,
        "Caption": caption,
    }


def _runs_to_html(runs: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for r in runs:
        text = html.escape(r.get("text", ""))
        if r.get("bold"):
            text = f"<b>{text}</b>"
        if r.get("italic"):
            text = f"<i>{text}</i>"
        if r.get("underline"):
            text = f"<u>{text}</u>"
        if r.get("code"):
            text = f'<font face="Courier">{text}</font>'
        if "font_size" in r:
            text = f'<font size="{int(float(r["font_size"]))}">{text}</font>'
        if "color" in r:
            text = f'<font color="{html.escape(str(r["color"]))}">{text}</font>'
        parts.append(text)
    return "".join(parts)


def _resolve_image_path(
    path_str: str, path_resolver: Callable[[str], Path] | None
) -> Path:
    if path_resolver is not None:
        return path_resolver(path_str)
    return Path(path_str)


def _build_table(block: dict[str, Any]) -> Table:
    header = block.get("header")
    rows = block["rows"]
    data: list[list[str]] = []
    if header:
        data.append(list(header))
    for r in rows:
        data.append(list(r))
    if not data:
        # Empty table — return an empty placeholder.
        data = [[""]]
    table = Table(data, repeatRows=1 if header else 0)
    style_cmds: list[tuple[Any, ...]] = [
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    if header:
        style_cmds.append(("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#ECECEC")))
        style_cmds.append(("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"))
    table.setStyle(TableStyle(style_cmds))
    return table


def _render_block(
    block: dict[str, Any],
    *,
    styles: dict[str, ParagraphStyle],
    path_resolver: Callable[[str], Path] | None,
    out: list[Any],
) -> None:
    btype = block["type"]
    if btype == "heading":
        level = max(1, min(6, int(block["level"])))
        out.append(Paragraph(html.escape(block["text"]), styles[f"Heading{level}"]))
        return
    if btype == "paragraph":
        out.append(Paragraph(_runs_to_html(block.get("runs", [])), styles["Body"]))
        return
    if btype == "list":
        ordered = bool(block.get("ordered"))
        for i, item in enumerate(block["items"], start=1):
            prefix = f"{i}. " if ordered else "• "
            out.append(
                Paragraph(html.escape(prefix + item), styles["Body"])
            )
        return
    if btype == "table":
        out.append(_build_table(block))
        out.append(Spacer(1, 6))
        return
    if btype == "image":
        img_path = _resolve_image_path(block["path"], path_resolver)
        if not img_path.exists():
            raise HandlerError(f"image not found: {img_path}")
        kwargs: dict[str, Any] = {}
        if "width_cm" in block:
            kwargs["width"] = float(block["width_cm"]) * cm
            # height auto-scaled by reportlab when only width given? No —
            # reportlab requires both. Use kind='proportional' workaround:
            from PIL import Image as PILImage  # lazy: pillow ships with reportlab

            with PILImage.open(str(img_path)) as im:
                w, h = im.size
            ratio = h / w if w else 1.0
            kwargs["height"] = kwargs["width"] * ratio
        out.append(Image(str(img_path), **kwargs))
        if "caption" in block:
            out.append(Paragraph(html.escape(block["caption"]), styles["Caption"]))
        out.append(Spacer(1, 6))
        return
    if btype == "page_break":
        out.append(PageBreak())
        return
    if btype == "code":
        # Preserve newlines using <br/> and escape HTML special chars.
        text = html.escape(block["text"]).replace("\n", "<br/>").replace(" ", "&nbsp;")
        out.append(Paragraph(text, styles["Code"]))
        out.append(Spacer(1, 4))
        return
    if btype == "math":
        out.append(
            Paragraph(
                f'<font face="Courier"><i>[math] {html.escape(block["latex"])}</i></font>',
                styles["Body"],
            )
        )
        return
    if btype == "hr":
        out.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
        return
    if btype == "blockquote":
        out.append(
            Paragraph(
                f'<i>{html.escape(block["text"])}</i>',
                styles["Blockquote"],
            )
        )
        return
    raise HandlerError(f"unsupported block type for pdf: {btype!r}")


def render_pdf(
    spec: DocumentSpec,
    out_path: Path,
    *,
    path_resolver: Callable[[str], Path] | None = None,
) -> None:
    """Render `spec` to `out_path` as a PDF. Caller handles locks/snapshots."""
    styles = _styles()
    flowables: list[Any] = []

    if spec.meta.get("title"):
        flowables.append(Paragraph(html.escape(spec.meta["title"]), styles["Title"]))
        flowables.append(Spacer(1, 12))

    for block in spec.blocks:
        _render_block(
            block, styles=styles, path_resolver=path_resolver, out=flowables
        )

    doc = SimpleDocTemplate(
        str(out_path),
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        title=spec.meta.get("title") or "",
        author=spec.meta.get("author") or "",
        subject=spec.meta.get("subject") or "",
        keywords=spec.meta.get("keywords") or "",
    )
    try:
        doc.build(flowables)
    except Exception as exc:  # noqa: BLE001
        raise HandlerError(f"failed to write pdf: {out_path} ({exc})") from exc
