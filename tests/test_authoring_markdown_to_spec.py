"""Tests for :mod:`dokumen_pintar.authoring.markdown_to_spec`."""

from __future__ import annotations

from dokumen_pintar.authoring.markdown_to_spec import markdown_to_spec


def test_heading_levels() -> None:
    spec = markdown_to_spec("# H1\n\n## H2\n\n### H3\n")
    levels = [b["level"] for b in spec.blocks if b["type"] == "heading"]
    assert levels == [1, 2, 3]


def test_paragraph_with_bold_italic_code() -> None:
    spec = markdown_to_spec("Plain **bold** *italic* `code` end.\n")
    para = next(b for b in spec.blocks if b["type"] == "paragraph")
    flags = [(r.get("text"), r.get("bold"), r.get("italic"), r.get("code")) for r in para["runs"]]
    assert ("bold", True, None, None) in flags
    assert ("italic", None, True, None) in flags
    assert ("code", None, None, True) in flags


def test_unordered_list() -> None:
    spec = markdown_to_spec("- a\n- b\n- c\n")
    block = next(b for b in spec.blocks if b["type"] == "list")
    assert block["ordered"] is False
    assert block["items"] == ["a", "b", "c"]


def test_ordered_list() -> None:
    spec = markdown_to_spec("1. one\n2. two\n")
    block = next(b for b in spec.blocks if b["type"] == "list")
    assert block["ordered"] is True
    assert block["items"] == ["one", "two"]


def test_table() -> None:
    md = "| A | B |\n|---|---|\n| 1 | 2 |\n| 3 | 4 |\n"
    spec = markdown_to_spec(md)
    block = next(b for b in spec.blocks if b["type"] == "table")
    assert block["header"] == ["A", "B"]
    assert block["rows"] == [["1", "2"], ["3", "4"]]


def test_code_block_with_language() -> None:
    md = "```python\nprint('x')\n```\n"
    spec = markdown_to_spec(md)
    block = next(b for b in spec.blocks if b["type"] == "code")
    assert block["language"] == "python"
    assert "print('x')" in block["text"]


def test_hr() -> None:
    spec = markdown_to_spec("Para A\n\n---\n\nPara B\n")
    types = [b["type"] for b in spec.blocks]
    assert "hr" in types


def test_blockquote() -> None:
    spec = markdown_to_spec("> quoted text\n> second line\n")
    bq = next(b for b in spec.blocks if b["type"] == "blockquote")
    assert "quoted text" in bq["text"]


def test_math_block() -> None:
    spec = markdown_to_spec("$$E = mc^2$$\n")
    math = next(b for b in spec.blocks if b["type"] == "math")
    assert math["latex"] == "E = mc^2"


def test_link_text_kept_url_dropped() -> None:
    spec = markdown_to_spec("See [docs](https://example.com).\n")
    para = next(b for b in spec.blocks if b["type"] == "paragraph")
    text_combined = "".join(r["text"] for r in para["runs"])
    assert "docs" in text_combined
    assert "https://example.com" not in text_combined


def test_image_inline_kept_as_alt_text() -> None:
    spec = markdown_to_spec("Inline ![alt](pic.png).\n")
    para = next(b for b in spec.blocks if b["type"] == "paragraph")
    text_combined = "".join(r["text"] for r in para["runs"])
    assert "[image: alt]" in text_combined


def test_meta_propagated() -> None:
    spec = markdown_to_spec("# X\n", meta={"title": "T"})
    assert spec.meta["title"] == "T"


def test_empty_paragraph_safe() -> None:
    spec = markdown_to_spec("\n\n")
    # Should not raise; may produce zero blocks.
    assert isinstance(spec.blocks, list)


def test_html_inline_kept_as_text() -> None:
    """With ``html: False`` markdown-it emits inline HTML as plain text
    (escaped at render time). It must not be interpreted as bold."""
    spec = markdown_to_spec("Hello <b>world</b>.\n")
    para = next(b for b in spec.blocks if b["type"] == "paragraph")
    text_combined = "".join(r["text"] for r in para["runs"])
    assert "world" in text_combined
    # No run should be bold purely because of the HTML.
    assert all(not r.get("bold") for r in para["runs"])
