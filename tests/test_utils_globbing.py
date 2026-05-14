"""Tests for :mod:`dokumen_pintar.utils.globbing`."""

from __future__ import annotations

from dokumen_pintar.utils.globbing import any_match, compile_globs, posix_of


def test_compile_globs_returns_regex_list() -> None:
    patterns = ["*.py", "*.txt"]
    compiled = compile_globs(patterns)
    assert len(compiled) == 2


def test_any_match_simple_pattern() -> None:
    compiled = compile_globs(["*.py"])
    assert any_match("main.py", compiled) is True
    assert any_match("main.txt", compiled) is False


def test_any_match_double_star_pattern() -> None:
    compiled = compile_globs(["**/.git/**"])
    assert any_match(".git/HEAD", compiled) is True
    assert any_match("foo/.git/config", compiled) is True
    assert any_match("src/main.py", compiled) is False


def test_any_match_no_patterns() -> None:
    compiled = compile_globs([])
    assert any_match("anything.txt", compiled) is False


def test_posix_of_converts_separator() -> None:
    # PurePosixPath treats backslash as part of the name on POSIX,
    # but the function is meant for already-posix or mixed paths.
    result = posix_of("a/b/c.txt")
    assert result == "a/b/c.txt"


def test_posix_of_keeps_forward_slash() -> None:
    assert posix_of("a/b/c.txt") == "a/b/c.txt"
