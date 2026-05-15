"""Tests for :mod:`dokumen_pintar.handlers.markdown_handler`."""

from __future__ import annotations

from pathlib import Path

import pytest

from dokumen_pintar.errors import HandlerError, UnsupportedFormatError
from dokumen_pintar.handlers.markdown_handler import MarkdownHandler


@pytest.fixture
def handler() -> MarkdownHandler:
    return MarkdownHandler()


@pytest.fixture
def sample(tmp_path: Path) -> Path:
    p = tmp_path / "doc.md"
    p.write_text(
        "# Title\n"
        "\n"
        "Some intro paragraph with [a link](https://example.com).\n"
        "\n"
        "## Section A\n"
        "\n"
        "Body of A.\n"
        "\n"
        "### Sub A1\n"
        "\n"
        "Deeper.\n"
        "\n"
        "## Section B\n"
        "\n"
        "Body of B.\n",
        encoding="utf-8",
    )
    return p


def test_detect(handler: MarkdownHandler, tmp_path: Path) -> None:
    assert handler.detect(tmp_path / "x.md") is True
    assert handler.detect(tmp_path / "x.markdown") is True
    assert handler.detect(tmp_path / "x.txt") is False


def test_read_text(handler: MarkdownHandler, sample: Path) -> None:
    text = handler.read_text(sample)
    assert "# Title" in text


def test_read_meta_outline(handler: MarkdownHandler, sample: Path) -> None:
    meta = handler.read_meta(sample)
    assert meta["format"] == "markdown"
    assert meta["heading_count"] == 4
    assert meta["link_count"] == 1
    levels = [h["level"] for h in meta["outline"]]
    assert levels == [1, 2, 3, 2]


def test_extract_for_search(handler: MarkdownHandler, sample: Path) -> None:
    text = handler.extract_for_search(sample)
    assert "Title" in text


def test_extract_for_search_returns_empty_on_missing(
    handler: MarkdownHandler, tmp_path: Path
) -> None:
    assert handler.extract_for_search(tmp_path / "nope.md") == ""


def test_write_text_roundtrip(handler: MarkdownHandler, tmp_path: Path) -> None:
    p = tmp_path / "out.md"
    handler.write_text(p, "# hello\n")
    assert p.read_text(encoding="utf-8").startswith("# hello")


def test_structured_get_outline(handler: MarkdownHandler, sample: Path) -> None:
    out = handler.structured_get(sample, "outline")
    assert isinstance(out, list)
    assert out[0]["text"] == "Title"


def test_structured_get_headings_alias(handler: MarkdownHandler, sample: Path) -> None:
    out = handler.structured_get(sample, "headings")
    assert len(out) == 4


def test_structured_get_heading_section(handler: MarkdownHandler, sample: Path) -> None:
    section = handler.structured_get(sample, "heading:2")  # ### Sub A1
    assert section.startswith("### Sub A1")
    assert "Deeper." in section
    # Must NOT include Section B which is at level 2 (higher than ###).
    assert "Section B" not in section


def test_structured_get_heading_section_section_a_includes_sub(
    handler: MarkdownHandler, sample: Path
) -> None:
    section = handler.structured_get(sample, "heading:1")  # ## Section A
    assert section.startswith("## Section A")
    assert "Sub A1" in section
    assert "Section B" not in section


def test_structured_get_wordcount(handler: MarkdownHandler, sample: Path) -> None:
    wc = handler.structured_get(sample, "wordcount")
    assert isinstance(wc, int)
    assert wc > 5


def test_structured_get_invalid_heading_index(
    handler: MarkdownHandler, sample: Path
) -> None:
    with pytest.raises(HandlerError, match="invalid heading index"):
        handler.structured_get(sample, "heading:abc")


def test_structured_get_heading_out_of_range(
    handler: MarkdownHandler, sample: Path
) -> None:
    with pytest.raises(HandlerError, match="out of range"):
        handler.structured_get(sample, "heading:99")


def test_structured_get_unsupported(handler: MarkdownHandler, sample: Path) -> None:
    with pytest.raises(HandlerError, match="unsupported"):
        handler.structured_get(sample, "nope")


def test_structured_set_unsupported(handler: MarkdownHandler, sample: Path) -> None:
    with pytest.raises(UnsupportedFormatError):
        handler.structured_set(sample, "heading:0", "x")


def test_structured_delete_unsupported(handler: MarkdownHandler, sample: Path) -> None:
    with pytest.raises(UnsupportedFormatError):
        handler.structured_delete(sample, "heading:0")


def test_outline_eof_close(handler: MarkdownHandler, tmp_path: Path) -> None:
    """A file ending with no trailing heading must still close all
    pending sections at EOF."""
    p = tmp_path / "trailing.md"
    p.write_text("# A\n## B\ncontent without trailing heading\n", encoding="utf-8")
    section = handler.structured_get(p, "heading:1")
    assert section.startswith("## B")
    assert "content without trailing heading" in section


def test_no_headings_returns_empty_outline(
    handler: MarkdownHandler, tmp_path: Path
) -> None:
    p = tmp_path / "flat.md"
    p.write_text("just a paragraph, no heading\n", encoding="utf-8")
    meta = handler.read_meta(p)
    assert meta["heading_count"] == 0
    assert meta["outline"] == []
