"""Tests for :mod:`dokumen_pintar.tools.file_crud`."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import pytest
from mcp.server.fastmcp import FastMCP

from dokumen_pintar.config import AppConfig
from dokumen_pintar.context import AppContext, build_context
from dokumen_pintar.errors import UnsupportedFormatError, ValidationError
from dokumen_pintar.tools import file_crud


def _setup(cfg: AppConfig) -> tuple[FastMCP, AppContext]:
    ctx = build_context(cfg)
    mcp = FastMCP(name="test")
    file_crud.register(mcp, ctx)
    return mcp, ctx


def test_file_create(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    cfg = make_config()
    mcp, ctx = _setup(cfg)
    fn = mcp._tool_manager._tools["file_create"].fn
    result = fn(path="documents:/new.txt", content="hello world")
    assert result["created"] is True


def test_file_create_exists_no_overwrite(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    docs_dir, _ = tmp_roots
    (docs_dir / "exist.txt").write_text("x", encoding="utf-8")
    cfg = make_config()
    mcp, ctx = _setup(cfg)
    fn = mcp._tool_manager._tools["file_create"].fn
    with pytest.raises(ValidationError, match="exists"):
        fn(path="documents:/exist.txt", content="y")


def test_file_create_overwrite(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    docs_dir, _ = tmp_roots
    (docs_dir / "exist.txt").write_text("x", encoding="utf-8")
    cfg = make_config()
    mcp, ctx = _setup(cfg)
    fn = mcp._tool_manager._tools["file_create"].fn
    result = fn(path="documents:/exist.txt", content="replaced", overwrite=True)
    assert result["created"] is True
    assert (docs_dir / "exist.txt").read_text(encoding="utf-8") == "replaced"


def test_file_delete(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    docs_dir, _ = tmp_roots
    (docs_dir / "del.txt").write_text("bye", encoding="utf-8")
    cfg = make_config()
    mcp, ctx = _setup(cfg)
    fn = mcp._tool_manager._tools["file_delete"].fn
    result = fn(path="documents:/del.txt")
    assert result["deleted"] is True
    assert not (docs_dir / "del.txt").exists()


def test_file_delete_nonexistent(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    cfg = make_config()
    mcp, ctx = _setup(cfg)
    fn = mcp._tool_manager._tools["file_delete"].fn
    with pytest.raises(ValidationError, match="does not exist"):
        fn(path="documents:/ghost.txt")


def test_file_rename(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    docs_dir, _ = tmp_roots
    (docs_dir / "old.txt").write_text("data", encoding="utf-8")
    cfg = make_config()
    mcp, ctx = _setup(cfg)
    fn = mcp._tool_manager._tools["file_rename"].fn
    fn(src="documents:/old.txt", dst="documents:/new.txt")
    assert not (docs_dir / "old.txt").exists()
    assert (docs_dir / "new.txt").exists()


def test_file_copy(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    docs_dir, _ = tmp_roots
    (docs_dir / "src.txt").write_text("copy me", encoding="utf-8")
    cfg = make_config()
    mcp, ctx = _setup(cfg)
    fn = mcp._tool_manager._tools["file_copy"].fn
    fn(src="documents:/src.txt", dst="documents:/dst.txt")
    assert (docs_dir / "src.txt").exists()
    assert (docs_dir / "dst.txt").exists()
    assert (docs_dir / "dst.txt").read_text(encoding="utf-8") == "copy me"


def test_file_move(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    docs_dir, _ = tmp_roots
    sub = docs_dir / "subdir"
    sub.mkdir()
    (docs_dir / "moveme.txt").write_text("moving", encoding="utf-8")
    cfg = make_config()
    mcp, ctx = _setup(cfg)
    fn = mcp._tool_manager._tools["file_move"].fn
    fn(src="documents:/moveme.txt", dst="documents:/subdir/moved.txt")
    assert not (docs_dir / "moveme.txt").exists()
    assert (sub / "moved.txt").exists()


# ── Additional file_crud coverage ──


def test_file_delete_dir_not_recursive(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    docs_dir, _ = tmp_roots
    d = docs_dir / "mydir"
    d.mkdir()
    (d / "child.txt").write_text("x", encoding="utf-8")
    cfg = make_config()
    mcp, ctx = _setup(cfg)
    fn = mcp._tool_manager._tools["file_delete"].fn
    with pytest.raises(ValidationError, match="directory"):
        fn(path="documents:/mydir")


def test_file_delete_dir_recursive(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    docs_dir, _ = tmp_roots
    d = docs_dir / "mydir2"
    d.mkdir()
    (d / "child.txt").write_text("x", encoding="utf-8")
    cfg = make_config()
    mcp, ctx = _setup(cfg)
    fn = mcp._tool_manager._tools["file_delete"].fn
    result = fn(path="documents:/mydir2", recursive=True)
    assert result["deleted"] is True
    assert not d.exists()


def test_file_rename_src_not_exists(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    cfg = make_config()
    mcp, ctx = _setup(cfg)
    fn = mcp._tool_manager._tools["file_rename"].fn
    with pytest.raises(ValidationError, match="does not exist"):
        fn(src="documents:/ghost.txt", dst="documents:/new.txt")


def test_file_rename_dst_exists(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    docs_dir, _ = tmp_roots
    (docs_dir / "a.txt").write_text("a", encoding="utf-8")
    (docs_dir / "b.txt").write_text("b", encoding="utf-8")
    cfg = make_config()
    mcp, ctx = _setup(cfg)
    fn = mcp._tool_manager._tools["file_rename"].fn
    with pytest.raises(ValidationError, match="exists"):
        fn(src="documents:/a.txt", dst="documents:/b.txt")


def test_file_rename_cross_dir_rejected(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    docs_dir, _ = tmp_roots
    sub = docs_dir / "sub"
    sub.mkdir()
    (docs_dir / "c.txt").write_text("c", encoding="utf-8")
    cfg = make_config()
    mcp, ctx = _setup(cfg)
    fn = mcp._tool_manager._tools["file_rename"].fn
    with pytest.raises(ValidationError, match="same parent"):
        fn(src="documents:/c.txt", dst="documents:/sub/c.txt")


def test_file_move_src_not_exists(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    cfg = make_config()
    mcp, ctx = _setup(cfg)
    fn = mcp._tool_manager._tools["file_move"].fn
    with pytest.raises(ValidationError, match="does not exist"):
        fn(src="documents:/ghost.txt", dst="documents:/x.txt")


def test_file_move_dst_exists_no_overwrite(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    docs_dir, _ = tmp_roots
    (docs_dir / "mv1.txt").write_text("1", encoding="utf-8")
    (docs_dir / "mv2.txt").write_text("2", encoding="utf-8")
    cfg = make_config()
    mcp, ctx = _setup(cfg)
    fn = mcp._tool_manager._tools["file_move"].fn
    with pytest.raises(ValidationError, match="exists"):
        fn(src="documents:/mv1.txt", dst="documents:/mv2.txt")


def test_file_copy_src_not_exists(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    cfg = make_config()
    mcp, ctx = _setup(cfg)
    fn = mcp._tool_manager._tools["file_copy"].fn
    with pytest.raises(ValidationError, match="does not exist"):
        fn(src="documents:/ghost.txt", dst="documents:/x.txt")


def test_file_copy_dst_exists_no_overwrite(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    docs_dir, _ = tmp_roots
    (docs_dir / "cp1.txt").write_text("1", encoding="utf-8")
    (docs_dir / "cp2.txt").write_text("2", encoding="utf-8")
    cfg = make_config()
    mcp, ctx = _setup(cfg)
    fn = mcp._tool_manager._tools["file_copy"].fn
    with pytest.raises(ValidationError, match="exists"):
        fn(src="documents:/cp1.txt", dst="documents:/cp2.txt")


def test_file_copy_directory(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    docs_dir, _ = tmp_roots
    src = docs_dir / "srcdir"
    src.mkdir()
    (src / "f.txt").write_text("hello", encoding="utf-8")
    cfg = make_config()
    mcp, ctx = _setup(cfg)
    fn = mcp._tool_manager._tools["file_copy"].fn
    fn(src="documents:/srcdir", dst="documents:/dstdir")
    assert (docs_dir / "dstdir" / "f.txt").exists()


def test_file_copy_directory_overwrite(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    docs_dir, _ = tmp_roots
    src = docs_dir / "owsrc"
    src.mkdir()
    (src / "a.txt").write_text("new", encoding="utf-8")
    dst = docs_dir / "owdst"
    dst.mkdir()
    (dst / "old.txt").write_text("old", encoding="utf-8")
    cfg = make_config()
    mcp, ctx = _setup(cfg)
    fn = mcp._tool_manager._tools["file_copy"].fn
    fn(src="documents:/owsrc", dst="documents:/owdst", overwrite=True)
    assert (docs_dir / "owdst" / "a.txt").exists()
    assert not (docs_dir / "owdst" / "old.txt").exists()


def test_snapshot_skips_directory(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    docs_dir, _ = tmp_roots
    d = docs_dir / "snapdir"
    d.mkdir()
    (d / "inside.txt").write_text("x", encoding="utf-8")
    cfg = make_config()
    mcp, ctx = _setup(cfg)
    # file_delete on a directory (recursive) — _snapshot returns None for dirs
    fn = mcp._tool_manager._tools["file_delete"].fn
    result = fn(path="documents:/snapdir", recursive=True)
    assert not d.exists()
    assert result["snapshot"] is None


def test_snapshot_returns_none_when_not_exists(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    from unittest.mock import patch
    docs_dir, _ = tmp_roots
    # Patch _snapshot to call it with a non-existent path (simulates race condition)
    # The real coverage hit: file_delete on a dir calls _snapshot AFTER rmtree
    # so resolved.absolute no longer exists → line 21 returns None
    d = docs_dir / "racetest"
    d.mkdir()
    (d / "f.txt").write_text("x", encoding="utf-8")
    mcp, ctx = _setup(make_config())
    fn = mcp._tool_manager._tools["file_delete"].fn
    result = fn(path="documents:/racetest", recursive=True)
    assert not d.exists()
    # snapshot is None because dir was already deleted when _snapshot was called
    assert result["snapshot"] is None


# ── B13: file_create refuses binary container formats ──


@pytest.mark.parametrize("ext", ["docx", "xlsx", "pptx", "pdf"])
def test_file_create_refuses_binary_container(
    make_config: Callable[..., AppConfig],
    tmp_roots: tuple[Path, Path],
    ext: str,
) -> None:
    """file_create must refuse to write raw text into a binary container — that
    would yield a non-conforming file that handlers cannot open."""
    docs_dir, _ = tmp_roots
    cfg = make_config()
    mcp, ctx = _setup(cfg)
    fn = mcp._tool_manager._tools["file_create"].fn
    with pytest.raises(UnsupportedFormatError, match=ext):
        fn(path=f"documents:/fake.{ext}", content="not a real file")
    # And also when content is empty — empty docx is still a corrupt docx.
    with pytest.raises(UnsupportedFormatError):
        fn(path=f"documents:/empty.{ext}", content="")
    # No file should have been created.
    assert not (docs_dir / f"fake.{ext}").exists()
    assert not (docs_dir / f"empty.{ext}").exists()


def test_file_create_text_format_still_works(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    """Sanity check: text formats (json/yaml/csv/xml/plain) are unaffected."""
    docs_dir, _ = tmp_roots
    mcp, _ = _setup(make_config())
    fn = mcp._tool_manager._tools["file_create"].fn
    fn(path="documents:/data.json", content="{}")
    fn(path="documents:/notes.md", content="# title")
    assert (docs_dir / "data.json").read_text(encoding="utf-8") == "{}"
    assert (docs_dir / "notes.md").read_text(encoding="utf-8") == "# title"


# ── B14: file_delete refuses to wipe the workspace root ──


def test_file_delete_refuses_workspace_root(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    """Deleting `documents:/` recursively would wipe the entire mounted root."""
    docs_dir, _ = tmp_roots
    (docs_dir / "important.txt").write_text("keepme", encoding="utf-8")
    mcp, _ = _setup(make_config())
    fn = mcp._tool_manager._tools["file_delete"].fn
    for path in ("documents:/", "documents:"):
        with pytest.raises(ValidationError, match="workspace root"):
            fn(path=path, recursive=True)
    # Root and contents must still exist.
    assert docs_dir.exists()
    assert (docs_dir / "important.txt").exists()


def test_file_rename_refuses_workspace_root(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    mcp, _ = _setup(make_config())
    fn = mcp._tool_manager._tools["file_rename"].fn
    with pytest.raises(ValidationError, match="workspace root"):
        fn(src="documents:/", dst="documents:/renamed_root")


def test_file_move_refuses_workspace_root(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    mcp, _ = _setup(make_config())
    fn = mcp._tool_manager._tools["file_move"].fn
    with pytest.raises(ValidationError, match="workspace root"):
        fn(src="documents:/", dst="documents:/elsewhere")


def test_file_copy_refuses_root_as_src(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    """Copying the entire root duplicates the workspace and is almost always a mistake."""
    mcp, _ = _setup(make_config())
    fn = mcp._tool_manager._tools["file_copy"].fn
    with pytest.raises(ValidationError, match="workspace root"):
        fn(src="documents:/", dst="documents:/clone")


def test_file_copy_refuses_root_as_dst_with_overwrite(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    """With overwrite=True, copying onto the root would rmtree the entire root."""
    docs_dir, _ = tmp_roots
    src = docs_dir / "src"
    src.mkdir()
    (src / "f.txt").write_text("x", encoding="utf-8")
    (docs_dir / "important.txt").write_text("keep", encoding="utf-8")
    mcp, _ = _setup(make_config())
    fn = mcp._tool_manager._tools["file_copy"].fn
    with pytest.raises(ValidationError, match="workspace root"):
        fn(src="documents:/src", dst="documents:/", overwrite=True)
    # Pre-existing content must still exist.
    assert (docs_dir / "important.txt").exists()


# ── B15: recursive directory delete snapshots every contained file ──


def test_file_delete_recursive_snapshots_children(
    make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]
) -> None:
    """Every file inside the deleted directory must be recoverable via the
    version store after a recursive delete."""
    docs_dir, _ = tmp_roots
    d = docs_dir / "tree"
    (d / "sub").mkdir(parents=True)
    (d / "a.txt").write_text("alpha", encoding="utf-8")
    (d / "b.txt").write_text("beta", encoding="utf-8")
    (d / "sub" / "c.txt").write_text("gamma", encoding="utf-8")
    mcp, ctx = _setup(make_config())
    fn = mcp._tool_manager._tools["file_delete"].fn

    result = fn(path="documents:/tree", recursive=True)
    assert result["deleted"] is True
    assert result["snapshots_taken"] == 3
    assert not d.exists()

    # All three files should be retrievable from the version store.
    for rel, body in [("tree/a.txt", "alpha"), ("tree/b.txt", "beta"), ("tree/sub/c.txt", "gamma")]:
        versions = ctx.versions.list_versions(root_name="documents", rel_path=rel)
        assert versions, f"missing snapshots for {rel}"
        latest = versions[0]
        assert latest["action"] == "recursive_delete"
        # Restore round-trip.
        target = docs_dir / rel
        ctx.versions.restore(latest["id"], target)
        assert target.read_text(encoding="utf-8") == body


def test_file_delete_recursive_continues_on_snapshot_failure(
    make_config: Callable[..., AppConfig],
    tmp_roots: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A snapshot failure on one child must NOT abort the delete itself."""
    docs_dir, _ = tmp_roots
    d = docs_dir / "tree2"
    d.mkdir()
    (d / "a.txt").write_text("a", encoding="utf-8")
    (d / "b.txt").write_text("b", encoding="utf-8")
    mcp, ctx = _setup(make_config())

    real_snapshot = ctx.versions.snapshot
    calls = {"n": 0}

    def flaky_snapshot(**kwargs):  # type: ignore[no-untyped-def]
        calls["n"] += 1
        if kwargs.get("rel_path", "").endswith("a.txt"):
            raise RuntimeError("disk full")
        return real_snapshot(**kwargs)

    monkeypatch.setattr(ctx.versions, "snapshot", flaky_snapshot)

    fn = mcp._tool_manager._tools["file_delete"].fn
    result = fn(path="documents:/tree2", recursive=True)
    assert result["deleted"] is True
    assert not d.exists()
    # Only b.txt could be snapshotted; a.txt was swallowed.
    assert result.get("snapshots_taken") == 1


def test_file_delete_recursive_skips_unrelated_paths(
    make_config: Callable[..., AppConfig],
    tmp_roots: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Defensive guard: if `child.relative_to(root_absolute)` ever raises
    ValueError (e.g. a symlink that escapes mid-iteration), we must skip
    that child silently and continue snapshotting the rest."""
    docs_dir, _ = tmp_roots
    d = docs_dir / "tree3"
    d.mkdir()
    (d / "good.txt").write_text("ok", encoding="utf-8")
    (d / "bad.txt").write_text("bad", encoding="utf-8")
    mcp, ctx = _setup(make_config())

    real_relative_to = Path.relative_to

    def flaky_relative_to(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        if self.name == "bad.txt":
            raise ValueError("simulated escape")
        return real_relative_to(self, *args, **kwargs)

    monkeypatch.setattr(Path, "relative_to", flaky_relative_to)

    fn = mcp._tool_manager._tools["file_delete"].fn
    result = fn(path="documents:/tree3", recursive=True)
    assert result["deleted"] is True
    assert not d.exists()
    # Only good.txt got snapshotted; bad.txt was silently skipped.
    assert result.get("snapshots_taken") == 1
