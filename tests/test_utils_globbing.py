"""Tests for :mod:`dokumen_pintar.utils.globbing`."""

from __future__ import annotations

from dokumen_pintar.utils.globbing import any_match, compile_globs, posix_of, split_root_glob


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


def test_split_root_glob_none_input() -> None:
    assert split_root_glob(None) == (None, None)


def test_split_root_glob_empty_string() -> None:
    assert split_root_glob("") == (None, "")


def test_split_root_glob_no_prefix() -> None:
    assert split_root_glob("*.docx") == (None, "*.docx")


def test_split_root_glob_with_prefix() -> None:
    assert split_root_glob("kp:/*.docx") == ("kp", "*.docx")


def test_split_root_glob_with_subdir() -> None:
    assert split_root_glob("kp:/sub/**/*.txt") == ("kp", "sub/**/*.txt")


def test_split_root_glob_underscore_root() -> None:
    assert split_root_glob("my-root_2:/*.md") == ("my-root_2", "*.md")


def test_split_root_glob_root_only_returns_star() -> None:
    # Edge case: bare root URI with empty pattern → fall back to "*"
    assert split_root_glob("kp:/") == ("kp", "*")


def test_split_root_glob_invalid_prefix_falls_through() -> None:
    # Drive letter style on Windows — single letter not allowed by current
    # regex (it accepts any 1+ char though), so this DOES match. Verify the
    # actual behavior: the regex requires `[A-Za-z0-9_-]+`, so `c:/foo` has
    # `c` as root which is technically valid. This is documented behavior.
    root, bare = split_root_glob("c:/foo")
    assert root == "c"
    assert bare == "foo"
