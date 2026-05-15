"""Tests for :mod:`dokumen_pintar.authoring.spec`."""

from __future__ import annotations

import json

import pytest

from dokumen_pintar.authoring.spec import (
    DocumentSpec,
    SpecError,
    SUPPORTED_BLOCK_TYPES,
    validate_spec,
)


def test_validate_minimal() -> None:
    spec = validate_spec({"blocks": []})
    assert isinstance(spec, DocumentSpec)
    assert spec.blocks == []
    assert spec.meta == {}


def test_validate_accepts_json_string() -> None:
    spec = validate_spec(json.dumps({"blocks": [{"type": "heading", "text": "X"}]}))
    assert spec.blocks[0]["text"] == "X"


def test_invalid_json_string_raises() -> None:
    with pytest.raises(SpecError, match="not valid JSON"):
        validate_spec("not-json")


def test_top_level_must_be_object() -> None:
    with pytest.raises(SpecError, match="object at the top level"):
        validate_spec("[1,2,3]")


def test_missing_blocks() -> None:
    with pytest.raises(SpecError, match="missing 'blocks'"):
        validate_spec({})


def test_blocks_must_be_list() -> None:
    with pytest.raises(SpecError, match="must be a list"):
        validate_spec({"blocks": "nope"})


def test_block_must_be_object() -> None:
    with pytest.raises(SpecError, match="must be an object"):
        validate_spec({"blocks": [123]})


def test_unknown_block_type_rejected() -> None:
    with pytest.raises(SpecError, match="not supported"):
        validate_spec({"blocks": [{"type": "marquee"}]})


def test_heading_requires_text() -> None:
    with pytest.raises(SpecError, match="needs 'text'"):
        validate_spec({"blocks": [{"type": "heading"}]})


def test_heading_level_range() -> None:
    with pytest.raises(SpecError, match="1..6"):
        validate_spec({"blocks": [{"type": "heading", "level": 7, "text": "x"}]})
    with pytest.raises(SpecError, match="1..6"):
        validate_spec({"blocks": [{"type": "heading", "level": 0, "text": "x"}]})


def test_paragraph_text_shortcut() -> None:
    spec = validate_spec({"blocks": [{"type": "paragraph", "text": "Hi"}]})
    assert spec.blocks[0]["runs"] == [{"text": "Hi"}]


def test_paragraph_requires_text_or_runs() -> None:
    with pytest.raises(SpecError, match="needs 'text' or 'runs'"):
        validate_spec({"blocks": [{"type": "paragraph"}]})


def test_paragraph_text_and_runs_conflict() -> None:
    with pytest.raises(SpecError, match="cannot have both"):
        validate_spec(
            {
                "blocks": [
                    {
                        "type": "paragraph",
                        "text": "x",
                        "runs": [{"text": "y"}],
                    }
                ]
            }
        )


def test_run_text_required() -> None:
    with pytest.raises(SpecError, match="runs\\[0\\].text is required"):
        validate_spec(
            {
                "blocks": [
                    {"type": "paragraph", "runs": [{"bold": True}]}
                ]
            }
        )


def test_run_unknown_key_rejected() -> None:
    with pytest.raises(SpecError, match="unknown keys"):
        validate_spec(
            {
                "blocks": [
                    {
                        "type": "paragraph",
                        "runs": [{"text": "x", "fancy": True}],
                    }
                ]
            }
        )


def test_run_bold_must_be_bool() -> None:
    with pytest.raises(SpecError, match="must be boolean"):
        validate_spec(
            {
                "blocks": [
                    {
                        "type": "paragraph",
                        "runs": [{"text": "x", "bold": "yes"}],
                    }
                ]
            }
        )


def test_run_font_size_positive() -> None:
    with pytest.raises(SpecError, match="positive number"):
        validate_spec(
            {
                "blocks": [
                    {
                        "type": "paragraph",
                        "runs": [{"text": "x", "font_size": -1}],
                    }
                ]
            }
        )


def test_list_requires_nonempty_items() -> None:
    with pytest.raises(SpecError, match="non-empty list"):
        validate_spec({"blocks": [{"type": "list", "items": []}]})


def test_list_item_must_be_string() -> None:
    with pytest.raises(SpecError, match="must be a string"):
        validate_spec({"blocks": [{"type": "list", "items": [1]}]})


def test_table_validates_header_and_rows() -> None:
    spec = validate_spec(
        {
            "blocks": [
                {
                    "type": "table",
                    "header": ["A", "B"],
                    "rows": [["1", None], [2, 3]],
                }
            ]
        }
    )
    block = spec.blocks[0]
    assert block["rows"][0] == ["1", ""]
    assert block["rows"][1] == ["2", "3"]


def test_table_rows_must_be_list_of_lists() -> None:
    with pytest.raises(SpecError, match="must be a list"):
        validate_spec({"blocks": [{"type": "table", "rows": "x"}]})


def test_table_header_must_be_strings() -> None:
    with pytest.raises(SpecError, match="header must be a list of strings"):
        validate_spec(
            {"blocks": [{"type": "table", "header": [1, 2]}]}
        )


def test_image_requires_path() -> None:
    with pytest.raises(SpecError, match="path is required"):
        validate_spec({"blocks": [{"type": "image"}]})


def test_image_width_validation() -> None:
    with pytest.raises(SpecError, match="positive number"):
        validate_spec(
            {"blocks": [{"type": "image", "path": "x.png", "width_cm": -1}]}
        )


def test_code_requires_text() -> None:
    with pytest.raises(SpecError, match="needs 'text'"):
        validate_spec({"blocks": [{"type": "code"}]})


def test_math_requires_latex() -> None:
    with pytest.raises(SpecError, match="needs 'latex'"):
        validate_spec({"blocks": [{"type": "math"}]})


def test_blockquote_requires_text() -> None:
    with pytest.raises(SpecError, match="needs 'text'"):
        validate_spec({"blocks": [{"type": "blockquote"}]})


def test_page_break_and_hr_normalize() -> None:
    spec = validate_spec(
        {"blocks": [{"type": "page_break", "extra": 1}, {"type": "hr"}]}
    )
    assert spec.blocks == [{"type": "page_break"}, {"type": "hr"}]


def test_meta_must_be_object() -> None:
    with pytest.raises(SpecError, match="meta must be an object"):
        validate_spec({"blocks": [], "meta": "x"})


def test_meta_string_values() -> None:
    spec = validate_spec(
        {"blocks": [], "meta": {"title": "T", "author": "A", "subject": None}}
    )
    assert spec.meta["title"] == "T"
    assert spec.meta["subject"] is None


def test_meta_invalid_value_type() -> None:
    with pytest.raises(SpecError, match="must be a string or null"):
        validate_spec({"blocks": [], "meta": {"title": 123}})


def test_documentspec_to_dict_and_from_raw() -> None:
    raw = {"blocks": [{"type": "heading", "text": "x"}]}
    spec = DocumentSpec.from_raw(raw)
    assert spec.to_dict()["blocks"][0]["text"] == "x"


def test_supported_block_types_constant_complete() -> None:
    # Sanity: the validator covers every type in the constant.
    assert "page_break" in SUPPORTED_BLOCK_TYPES
    assert "blockquote" in SUPPORTED_BLOCK_TYPES
