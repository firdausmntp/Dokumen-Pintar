"""Convert Markdown source into a :class:`DocumentSpec`.

Uses ``markdown-it-py`` (CommonMark + table) to produce a stream of tokens
and assembles them into the IR. Supports: heading, paragraph (with bold /
italic / inline code / link), unordered & ordered lists, tables, code
blocks, horizontal rule, block quotes, images, and inline math
``$..$`` / ``$$..$$`` (rendered as math blocks).
"""

from __future__ import annotations

import re
from typing import Any

from markdown_it import MarkdownIt

from .spec import DocumentSpec


def _build_md() -> MarkdownIt:
    md = MarkdownIt("commonmark", {"html": False, "breaks": False, "linkify": False})
    md.enable("table")
    return md


_MATH_BLOCK_RX = re.compile(r"^\$\$(.+?)\$\$$", re.DOTALL)


def _inline_to_runs(inline_token: Any) -> list[dict[str, Any]]:
    """Flatten a markdown-it inline token tree into a list of runs."""
    runs: list[dict[str, Any]] = []
    bold = 0
    italic = 0
    code_now = False
    underline = 0  # markdown has no underline; reserved for future ext
    for child in inline_token.children or []:
        ttype = child.type
        if ttype == "text":
            run: dict[str, Any] = {"text": child.content}
            if bold:
                run["bold"] = True
            if italic:
                run["italic"] = True
            runs.append(run)
        elif ttype == "code_inline":
            runs.append({"text": child.content, "code": True})
        elif ttype == "softbreak" or ttype == "hardbreak":
            runs.append({"text": " "})
        elif ttype == "strong_open":
            bold += 1
        elif ttype == "strong_close":
            bold = max(0, bold - 1)
        elif ttype == "em_open":
            italic += 1
        elif ttype == "em_close":
            italic = max(0, italic - 1)
        elif ttype == "s_open":
            # strikethrough — flatten as plain
            pass
        elif ttype == "s_close":
            pass
        elif ttype == "link_open":
            # Render link text only; URL is dropped (DOCX/PDF would need
            # hyperlinks at the renderer level — out of scope for v1).
            pass
        elif ttype == "link_close":
            pass
        elif ttype == "image":
            alt = child.content or ""
            if alt:
                runs.append({"text": f"[image: {alt}]", "italic": True})
        elif ttype == "html_inline":
            # Drop raw HTML for safety.
            pass
        else:
            # Fallback: append content as plain text if any.
            content = getattr(child, "content", "")
            if content:
                runs.append({"text": content})
    # Coalesce empty runs.
    return [r for r in runs if r.get("text")]


def _table_from_tokens(tokens: list[Any], start: int) -> tuple[dict[str, Any], int]:
    """Parse a table starting at ``tokens[start]`` (table_open) and return
    (block_dict, index_after_table_close)."""
    header: list[str] | None = None
    rows: list[list[str]] = []
    i = start + 1
    in_head = False
    in_body = False
    current_row: list[str] | None = None
    while i < len(tokens):
        tok = tokens[i]
        if tok.type == "table_close":
            return ({"type": "table", "header": header, "rows": rows}, i + 1)
        if tok.type == "thead_open":
            in_head = True
        elif tok.type == "thead_close":
            in_head = False
        elif tok.type == "tbody_open":
            in_body = True
        elif tok.type == "tbody_close":
            in_body = False
        elif tok.type == "tr_open":
            current_row = []
        elif tok.type == "tr_close":
            if current_row is not None:
                if in_head:
                    header = current_row
                elif in_body:
                    rows.append(current_row)
            current_row = None
        elif tok.type == "inline" and current_row is not None:
            current_row.append(tok.content or "")
        i += 1
    # Unterminated — return what we have.
    return ({"type": "table", "header": header, "rows": rows}, i)


def _list_from_tokens(
    tokens: list[Any], start: int, ordered: bool
) -> tuple[dict[str, Any], int]:
    """Parse a list starting at tokens[start] (bullet/ordered_list_open)."""
    items: list[str] = []
    depth = 1
    i = start + 1
    current: list[str] = []
    in_item = False
    while i < len(tokens):
        tok = tokens[i]
        if tok.type in ("bullet_list_close", "ordered_list_close"):
            depth -= 1
            if depth == 0:
                return ({"type": "list", "ordered": ordered, "items": items}, i + 1)
        elif tok.type in ("bullet_list_open", "ordered_list_open"):
            depth += 1
        elif tok.type == "list_item_open":
            in_item = True
            current = []
        elif tok.type == "list_item_close":
            if current:
                items.append(" ".join(current).strip())
            in_item = False
            current = []
        elif tok.type == "inline" and in_item:
            text = tok.content or ""
            if text:
                current.append(text)
        i += 1
    return ({"type": "list", "ordered": ordered, "items": items}, i)


def markdown_to_spec(source: str, *, meta: dict[str, Any] | None = None) -> DocumentSpec:
    """Parse `source` into a :class:`DocumentSpec`."""
    md = _build_md()
    tokens = md.parse(source)
    blocks: list[dict[str, Any]] = []
    i = 0
    n = len(tokens)
    while i < n:
        tok = tokens[i]
        ttype = tok.type
        if ttype == "heading_open":
            level = int(tok.tag[1:]) if tok.tag and tok.tag[0] == "h" else 1
            inline = tokens[i + 1] if i + 1 < n else None
            text = inline.content if inline is not None else ""
            blocks.append({"type": "heading", "level": level, "text": text})
            i += 3  # heading_open, inline, heading_close
            continue
        if ttype == "paragraph_open":
            inline = tokens[i + 1] if i + 1 < n else None
            content = inline.content if inline is not None else ""
            m = _MATH_BLOCK_RX.match(content.strip())
            if m:
                blocks.append({"type": "math", "latex": m.group(1).strip()})
            else:
                runs = _inline_to_runs(inline) if inline is not None else []
                if runs:
                    blocks.append({"type": "paragraph", "runs": runs})
                else:
                    blocks.append({"type": "paragraph", "runs": [{"text": ""}]})
            i += 3  # paragraph_open, inline, paragraph_close
            continue
        if ttype == "fence" or ttype == "code_block":
            language = tok.info.strip() if tok.info else None
            blocks.append({"type": "code", "language": language, "text": tok.content})
            i += 1
            continue
        if ttype == "hr":
            blocks.append({"type": "hr"})
            i += 1
            continue
        if ttype == "blockquote_open":
            # Capture inline contents until blockquote_close.
            depth = 1
            j = i + 1
            buf: list[str] = []
            while j < n and depth > 0:
                t = tokens[j]
                if t.type == "blockquote_open":
                    depth += 1
                elif t.type == "blockquote_close":
                    depth -= 1
                    if depth == 0:
                        break
                elif t.type == "inline":
                    buf.append(t.content or "")
                j += 1
            blocks.append({"type": "blockquote", "text": "\n".join(buf).strip()})
            i = j + 1
            continue
        if ttype == "bullet_list_open":
            block, ni = _list_from_tokens(tokens, i, ordered=False)
            if block["items"]:
                blocks.append(block)
            i = ni
            continue
        if ttype == "ordered_list_open":
            block, ni = _list_from_tokens(tokens, i, ordered=True)
            if block["items"]:
                blocks.append(block)
            i = ni
            continue
        if ttype == "table_open":
            block, ni = _table_from_tokens(tokens, i)
            blocks.append(block)
            i = ni
            continue
        # Unknown token — skip safely.
        i += 1

    spec = DocumentSpec(blocks=blocks, meta=dict(meta or {}))
    # Round-trip through validate_spec to normalize and catch any issues.
    from .spec import validate_spec

    return validate_spec(spec.to_dict())
