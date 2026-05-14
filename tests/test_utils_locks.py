"""Tests for :mod:`dokumen_pintar.utils.locks`."""

from __future__ import annotations

from pathlib import Path

from dokumen_pintar.utils.locks import _lock_path_for, file_lock


def test_lock_path_deterministic(tmp_path: Path) -> None:
    target = tmp_path / "foo.txt"
    a = _lock_path_for(target)
    b = _lock_path_for(target)
    assert a == b
    assert a.suffix == ".lock"


def test_different_paths_different_locks(tmp_path: Path) -> None:
    a = _lock_path_for(tmp_path / "a.txt")
    b = _lock_path_for(tmp_path / "b.txt")
    assert a != b


def test_file_lock_context_manager(tmp_path: Path) -> None:
    target = tmp_path / "locked.txt"
    target.write_text("original", encoding="utf-8")
    with file_lock(target):
        target.write_text("modified", encoding="utf-8")
    assert target.read_text(encoding="utf-8") == "modified"


def test_file_lock_non_existent_file(tmp_path: Path) -> None:
    target = tmp_path / "nonexistent.txt"
    with file_lock(target):
        pass  # should not raise
