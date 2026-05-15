"""Document IR (intermediate representation) and validation.

The IR is a JSON-shaped dict::

    {
      "meta": {"title": ..., "author": ..., "subject": ...},   # optional
      "blocks": [
        {"type": "heading",    "level": 1, "text": "Judul"},
        {"type": "paragraph",  "runs": [{"text": "Hi", "bold": true}, ...]},
        {"type": "paragraph",  "text": "Plain text shortcut."},
        {"type": "list",       "ordered": false, "items": ["a","b"]},
        {"type": "table",      "header": ["A","B"], "rows": [["1","2"]]},
        {"type": "image",      "path": "kp:/diagram.png", "width_cm": 10},
        {"type": "page_break"},
        {"type": "code",       "language": "python", "text": "..."},
        {"type": "math",       "latex": "E = mc^2"},
        {"type": "hr"},
        {"type": "blockquote", "text": "..."}
      ]
    }

Validation is *structural only* — no rendering side-effects. Callers may
pass either a `dict` or a JSON string; helpers normalize both.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Mapping


class SpecError(ValueError):
    """Raised when a document spec is malformed."""


# Supported block types (kept here so renderers can share the truth).
SUPPORTED_BLOCK_TYPES: frozenset[str] = frozenset(
    {
        "heading",
        "paragraph",
        "list",
        "table",
        "image",
        "page_break",
        "code",
        "math",
        "hr",
        "blockquote",
    }
)

# Run-level keys recognized on inline text runs.
RUN_KEYS: frozenset[str] = frozenset(
    {"text", "bold", "italic", "underline", "code", "font_size", "color"}
)


@dataclass
class DocumentSpec:
    """Validated, normalized document IR."""

    blocks: list[dict[str, Any]] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_raw(cls, raw: Mapping[str, Any] | str) -> "DocumentSpec":
        return validate_spec(raw)

    def to_dict(self) -> dict[str, Any]:
        return {"meta": dict(self.meta), "blocks": [dict(b) for b in self.blocks]}


def _coerce_obj(raw: Mapping[str, Any] | str) -> dict[str, Any]:
    if isinstance(raw, str):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise SpecError(f"spec is not valid JSON: {exc}") from exc
    else:
        data = dict(raw)
    if not isinstance(data, dict):
        raise SpecError("spec must be a JSON object at the top level")
    return data


def _validate_run(run: Any, *, idx: int, block_idx: int) -> dict[str, Any]:
    if not isinstance(run, dict):
        raise SpecError(
            f"block[{block_idx}].runs[{idx}] must be an object, got "
            f"{type(run).__name__}"
        )
    if "text" not in run or not isinstance(run["text"], str):
        raise SpecError(
            f"block[{block_idx}].runs[{idx}].text is required (string)"
        )
    unknown = set(run) - RUN_KEYS
    if unknown:
        raise SpecError(
            f"block[{block_idx}].runs[{idx}] has unknown keys: {sorted(unknown)}"
        )
    out: dict[str, Any] = {"text": run["text"]}
    for flag in ("bold", "italic", "underline", "code"):
        if flag in run:
            if not isinstance(run[flag], bool):
                raise SpecError(
                    f"block[{block_idx}].runs[{idx}].{flag} must be boolean"
                )
            out[flag] = run[flag]
    if "font_size" in run:
        fs = run["font_size"]
        if not isinstance(fs, (int, float)) or fs <= 0:
            raise SpecError(
                f"block[{block_idx}].runs[{idx}].font_size must be a positive number"
            )
        out["font_size"] = float(fs)
    if "color" in run:
        color = run["color"]
        if not isinstance(color, str):
            raise SpecError(
                f"block[{block_idx}].runs[{idx}].color must be a string (#RRGGBB)"
            )
        out["color"] = color
    return out


def _validate_paragraph(block: dict[str, Any], idx: int) -> dict[str, Any]:
    if "runs" in block and "text" in block:
        raise SpecError(
            f"block[{idx}]: paragraph cannot have both 'text' and 'runs'"
        )
    if "runs" in block:
        runs = block["runs"]
        if not isinstance(runs, list):
            raise SpecError(f"block[{idx}].runs must be a list")
        validated = [
            _validate_run(r, idx=i, block_idx=idx) for i, r in enumerate(runs)
        ]
        return {"type": "paragraph", "runs": validated}
    if "text" in block:
        if not isinstance(block["text"], str):
            raise SpecError(f"block[{idx}].text must be a string")
        return {"type": "paragraph", "runs": [{"text": block["text"]}]}
    raise SpecError(f"block[{idx}]: paragraph needs 'text' or 'runs'")


def _validate_heading(block: dict[str, Any], idx: int) -> dict[str, Any]:
    level = block.get("level", 1)
    if not isinstance(level, int) or level < 1 or level > 6:
        raise SpecError(f"block[{idx}].level must be integer 1..6")
    if "text" not in block or not isinstance(block["text"], str):
        raise SpecError(f"block[{idx}]: heading needs 'text' string")
    return {"type": "heading", "level": level, "text": block["text"]}


def _validate_list(block: dict[str, Any], idx: int) -> dict[str, Any]:
    items = block.get("items")
    if not isinstance(items, list) or not items:
        raise SpecError(f"block[{idx}].items must be a non-empty list")
    for j, it in enumerate(items):
        if not isinstance(it, str):
            raise SpecError(
                f"block[{idx}].items[{j}] must be a string"
            )
    ordered = bool(block.get("ordered", False))
    return {"type": "list", "ordered": ordered, "items": list(items)}


def _validate_table(block: dict[str, Any], idx: int) -> dict[str, Any]:
    header = block.get("header")
    rows = block.get("rows", [])
    if header is not None:
        if not isinstance(header, list) or not all(isinstance(c, str) for c in header):
            raise SpecError(f"block[{idx}].header must be a list of strings")
    if not isinstance(rows, list):
        raise SpecError(f"block[{idx}].rows must be a list")
    cleaned: list[list[str]] = []
    for r_i, row in enumerate(rows):
        if not isinstance(row, list):
            raise SpecError(f"block[{idx}].rows[{r_i}] must be a list")
        cleaned.append(["" if c is None else str(c) for c in row])
    return {
        "type": "table",
        "header": list(header) if header else None,
        "rows": cleaned,
    }


def _validate_image(block: dict[str, Any], idx: int) -> dict[str, Any]:
    path = block.get("path")
    if not isinstance(path, str) or not path:
        raise SpecError(f"block[{idx}].path is required for image (string)")
    width_cm = block.get("width_cm")
    if width_cm is not None and (
        not isinstance(width_cm, (int, float)) or width_cm <= 0
    ):
        raise SpecError(f"block[{idx}].width_cm must be a positive number")
    out: dict[str, Any] = {"type": "image", "path": path}
    if width_cm is not None:
        out["width_cm"] = float(width_cm)
    if "caption" in block:
        if not isinstance(block["caption"], str):
            raise SpecError(f"block[{idx}].caption must be a string")
        out["caption"] = block["caption"]
    return out


def _validate_code(block: dict[str, Any], idx: int) -> dict[str, Any]:
    if "text" not in block or not isinstance(block["text"], str):
        raise SpecError(f"block[{idx}]: code needs 'text' string")
    language = block.get("language")
    if language is not None and not isinstance(language, str):
        raise SpecError(f"block[{idx}].language must be a string")
    return {"type": "code", "language": language, "text": block["text"]}


def _validate_math(block: dict[str, Any], idx: int) -> dict[str, Any]:
    if "latex" not in block or not isinstance(block["latex"], str):
        raise SpecError(f"block[{idx}]: math needs 'latex' string")
    return {"type": "math", "latex": block["latex"]}


def _validate_blockquote(block: dict[str, Any], idx: int) -> dict[str, Any]:
    if "text" not in block or not isinstance(block["text"], str):
        raise SpecError(f"block[{idx}]: blockquote needs 'text' string")
    return {"type": "blockquote", "text": block["text"]}


_BLOCK_VALIDATORS = {
    "heading": _validate_heading,
    "paragraph": _validate_paragraph,
    "list": _validate_list,
    "table": _validate_table,
    "image": _validate_image,
    "code": _validate_code,
    "math": _validate_math,
    "blockquote": _validate_blockquote,
}


def _validate_meta(meta: Any) -> dict[str, Any]:
    if meta is None:
        return {}
    if not isinstance(meta, dict):
        raise SpecError("meta must be an object")
    out: dict[str, Any] = {}
    for key in ("title", "author", "subject", "keywords"):
        if key in meta:
            v = meta[key]
            if v is not None and not isinstance(v, str):
                raise SpecError(f"meta.{key} must be a string or null")
            out[key] = v
    return out


def validate_spec(raw: Mapping[str, Any] | str) -> DocumentSpec:
    """Validate a raw spec object/JSON string and return a DocumentSpec.

    Raises :class:`SpecError` with a path-qualified message on the first
    structural problem.
    """
    data = _coerce_obj(raw)
    if "blocks" not in data:
        raise SpecError("spec missing 'blocks' list")
    blocks_raw = data["blocks"]
    if not isinstance(blocks_raw, list):
        raise SpecError("'blocks' must be a list")

    out_blocks: list[dict[str, Any]] = []
    for i, b in enumerate(blocks_raw):
        if not isinstance(b, dict):
            raise SpecError(f"block[{i}] must be an object, got {type(b).__name__}")
        btype = b.get("type")
        if btype not in SUPPORTED_BLOCK_TYPES:
            raise SpecError(
                f"block[{i}].type {btype!r} is not supported; expected one of "
                f"{sorted(SUPPORTED_BLOCK_TYPES)}"
            )
        if btype == "page_break":
            out_blocks.append({"type": "page_break"})
            continue
        if btype == "hr":
            out_blocks.append({"type": "hr"})
            continue
        validator = _BLOCK_VALIDATORS[btype]
        out_blocks.append(validator(b, i))

    meta = _validate_meta(data.get("meta"))
    return DocumentSpec(blocks=out_blocks, meta=meta)
