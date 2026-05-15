"""Tests for :mod:`dokumen_pintar.handlers.latex_handler`."""

from __future__ import annotations

from pathlib import Path

import pytest

from dokumen_pintar.errors import HandlerError, UnsupportedFormatError
from dokumen_pintar.handlers.latex_handler import LatexHandler


SAMPLE = r"""\documentclass[12pt]{article}
\usepackage{amsmath}
\usepackage[utf8]{inputenc}

\begin{document}
\section{Intro}
Hello world. Let \(x = 1\).

\subsection{Background}
Some background.

\section{Method}
We compute $E = mc^2$.

\begin{equation}
a^2 + b^2 = c^2
\end{equation}

\end{document}
"""


@pytest.fixture
def handler() -> LatexHandler:
    return LatexHandler()


@pytest.fixture
def sample(tmp_path: Path) -> Path:
    p = tmp_path / "doc.tex"
    p.write_text(SAMPLE, encoding="utf-8")
    return p


def test_detect(handler: LatexHandler, tmp_path: Path) -> None:
    assert handler.detect(tmp_path / "x.tex") is True
    assert handler.detect(tmp_path / "x.txt") is False


def test_read_text(handler: LatexHandler, sample: Path) -> None:
    text = handler.read_text(sample)
    assert r"\section{Intro}" in text


def test_read_meta(handler: LatexHandler, sample: Path) -> None:
    meta = handler.read_meta(sample)
    assert meta["format"] == "latex"
    assert meta["documentclass"] == "article"
    assert "amsmath" in meta["packages"]
    assert meta["section_count"] >= 3
    assert meta["environment_counts"].get("document") == 1
    assert meta["environment_counts"].get("equation") == 1


def test_extract_for_search_renders_text(
    handler: LatexHandler, sample: Path
) -> None:
    text = handler.extract_for_search(sample).lower()
    # pylatexenc should produce plain text without backslash macros (it
    # may uppercase section titles, so compare case-insensitively).
    assert "intro" in text
    assert "method" in text


def test_extract_for_search_missing_file(
    handler: LatexHandler, tmp_path: Path
) -> None:
    assert handler.extract_for_search(tmp_path / "missing.tex") == ""


def test_extract_for_search_handles_garbage(
    handler: LatexHandler, tmp_path: Path
) -> None:
    p = tmp_path / "broken.tex"
    p.write_bytes(b"\\begin{nope}\xff\\end{nope}")
    # Must not raise — fallback path returns something.
    out = handler.extract_for_search(p)
    assert isinstance(out, str)


def test_write_text_roundtrip(handler: LatexHandler, tmp_path: Path) -> None:
    p = tmp_path / "out.tex"
    handler.write_text(p, r"\section{X}")
    assert r"\section{X}" in p.read_text(encoding="utf-8")


def test_structured_get_outline(handler: LatexHandler, sample: Path) -> None:
    outline = handler.structured_get(sample, "outline")
    titles = [s["title"] for s in outline]
    assert "Intro" in titles
    assert "Background" in titles
    assert "Method" in titles


def test_structured_get_sections_alias(
    handler: LatexHandler, sample: Path
) -> None:
    sections = handler.structured_get(sample, "sections")
    assert len(sections) >= 3


def test_structured_get_packages(handler: LatexHandler, sample: Path) -> None:
    pkgs = handler.structured_get(sample, "packages")
    assert "amsmath" in pkgs
    assert "inputenc" in pkgs


def test_structured_get_documentclass(
    handler: LatexHandler, sample: Path
) -> None:
    assert handler.structured_get(sample, "documentclass") == "article"


def test_structured_get_environments(
    handler: LatexHandler, sample: Path
) -> None:
    envs = handler.structured_get(sample, "environments")
    assert envs.get("equation") == 1


def test_structured_get_section_text(
    handler: LatexHandler, sample: Path
) -> None:
    src = handler.structured_get(sample, "section:0")  # \section{Intro}
    assert src.startswith(r"\section{Intro}")
    # Must include subsection (lower level), but stop before next section.
    assert "Background" in src
    assert "Method" not in src


def test_structured_get_section_invalid_index(
    handler: LatexHandler, sample: Path
) -> None:
    with pytest.raises(HandlerError, match="invalid section index"):
        handler.structured_get(sample, "section:abc")


def test_structured_get_section_out_of_range(
    handler: LatexHandler, sample: Path
) -> None:
    with pytest.raises(HandlerError, match="out of range"):
        handler.structured_get(sample, "section:99")


def test_structured_get_unsupported(handler: LatexHandler, sample: Path) -> None:
    with pytest.raises(HandlerError, match="unsupported"):
        handler.structured_get(sample, "weird")


def test_structured_set_unsupported(handler: LatexHandler, sample: Path) -> None:
    with pytest.raises(UnsupportedFormatError):
        handler.structured_set(sample, "section:0", "x")


def test_structured_delete_unsupported(
    handler: LatexHandler, sample: Path
) -> None:
    with pytest.raises(UnsupportedFormatError):
        handler.structured_delete(sample, "section:0")


def test_documentclass_optional_arg(
    handler: LatexHandler, tmp_path: Path
) -> None:
    p = tmp_path / "min.tex"
    p.write_text(r"\documentclass{minimal}\begin{document}x\end{document}", encoding="utf-8")
    assert handler.structured_get(p, "documentclass") == "minimal"


def test_structured_get_last_section_runs_to_eof(
    handler: LatexHandler, sample: Path
) -> None:
    """Requesting the last section means the inner ``for nxt in
    outline[idx+1:]`` loop never breaks — this exercises the EOF fall-through
    in ``_section_text_at``."""
    outline = handler.structured_get(sample, "outline")
    last_idx = len(outline) - 1
    src = handler.structured_get(sample, f"section:{last_idx}")
    assert src.startswith(r"\section{Method}")
    # Up to EOF (must include the equation environment that follows).
    assert r"\end{equation}" in src


def test_meta_no_documentclass(
    handler: LatexHandler, tmp_path: Path
) -> None:
    p = tmp_path / "frag.tex"
    p.write_text("just a paragraph", encoding="utf-8")
    meta = handler.read_meta(p)
    assert meta["documentclass"] is None
    assert meta["packages"] == []
