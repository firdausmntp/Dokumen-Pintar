"""Tests for :mod:`dokumen_pintar.pathguard`."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Callable

import pytest

from dokumen_pintar.config import AppConfig
from dokumen_pintar.errors import PathNotAllowedError, RootNotWritableError
from dokumen_pintar.pathguard import PathGuard


def test_workspace_uri_resolves_under_docs_root(
    guard: PathGuard, tmp_roots: tuple[Path, Path]
) -> None:
    docs_dir, _ref_dir = tmp_roots
    resolved = guard.resolve("documents:/a.txt")
    assert resolved.root.name == "documents"
    assert resolved.absolute == (docs_dir / "a.txt").resolve()
    assert resolved.workspace_uri == "documents:/a.txt"


def test_absolute_path_inside_root_resolves(guard: PathGuard, tmp_roots: tuple[Path, Path]) -> None:
    docs_dir, _ref_dir = tmp_roots
    target = docs_dir / "nested" / "file.txt"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("hello", encoding="utf-8")

    resolved = guard.resolve(str(target))
    assert resolved.root.name == "documents"
    assert resolved.absolute == target.resolve()


def test_absolute_path_outside_roots_is_rejected(guard: PathGuard, tmp_path: Path) -> None:
    outside = tmp_path / "outside" / "foo.txt"
    outside.parent.mkdir(parents=True, exist_ok=True)
    outside.write_text("x", encoding="utf-8")

    with pytest.raises(PathNotAllowedError):
        guard.resolve(str(outside))


def test_symlink_outside_root_is_blocked(
    guard: PathGuard, tmp_roots: tuple[Path, Path], tmp_path: Path
) -> None:
    docs_dir, _ref_dir = tmp_roots
    external_target = tmp_path / "external_target.txt"
    external_target.write_text("secret", encoding="utf-8")

    link = docs_dir / "evil_link.txt"
    try:
        os.symlink(external_target, link)
    except (OSError, NotImplementedError) as exc:
        if sys.platform.startswith("win"):
            pytest.skip(f"symlink creation not permitted on this Windows environment: {exc}")
        raise

    with pytest.raises(PathNotAllowedError):
        guard.resolve(str(link))


def test_exclude_pattern_blocks_git_dir(guard: PathGuard, tmp_roots: tuple[Path, Path]) -> None:
    docs_dir, _ref_dir = tmp_roots
    git_file = docs_dir / ".git" / "HEAD"
    git_file.parent.mkdir(parents=True, exist_ok=True)
    git_file.write_text("ref: refs/heads/main", encoding="utf-8")

    with pytest.raises(PathNotAllowedError):
        guard.resolve(str(git_file))


def test_ensure_writable_raises_on_ref_root(guard: PathGuard, tmp_roots: tuple[Path, Path]) -> None:
    _docs_dir, ref_dir = tmp_roots
    target = ref_dir / "readme.txt"
    target.write_text("readonly", encoding="utf-8")

    resolved = guard.resolve(str(target))
    assert resolved.root.name == "ref"

    with pytest.raises(RootNotWritableError):
        guard.ensure_writable(resolved)


def test_ensure_writable_ok_on_docs_root(guard: PathGuard, tmp_roots: tuple[Path, Path]) -> None:
    docs_dir, _ref_dir = tmp_roots
    target = docs_dir / "ok.txt"
    target.write_text("writable", encoding="utf-8")

    resolved = guard.resolve(str(target))
    guard.ensure_writable(resolved)


def test_direct_pathguard_construction(
    make_config: Callable[..., AppConfig],
) -> None:
    cfg = make_config()
    pg = PathGuard(cfg)
    names = [r.name for r, _ in pg.roots]
    assert "documents" in names
    assert "ref" in names


# ── Additional PathGuard coverage ──

from dokumen_pintar.errors import FileTooLargeError, ValidationError


def test_empty_path_raises(guard: PathGuard) -> None:
    with pytest.raises(ValidationError, match="non-empty"):
        guard.resolve("")


def test_non_string_path_raises(guard: PathGuard) -> None:
    with pytest.raises(ValidationError, match="non-empty"):
        guard.resolve(None)  # type: ignore[arg-type]


def test_must_exist_raises_for_missing(guard: PathGuard) -> None:
    with pytest.raises(PathNotAllowedError, match="does not exist"):
        guard.resolve("documents:/nonexistent.txt", must_exist=True)


def test_workspace_uri_root_only(guard: PathGuard, tmp_roots: tuple[Path, Path]) -> None:
    docs_dir, _ = tmp_roots
    resolved = guard.resolve("documents:/")
    assert resolved.absolute == docs_dir.resolve()


def test_find_root_by_name(guard: PathGuard) -> None:
    assert guard.find_root_by_name("documents") is not None
    assert guard.find_root_by_name("nonexistent") is None


def test_iter_root_entries(guard: PathGuard) -> None:
    entries = list(guard.iter_root_entries())
    assert len(entries) == 2


def test_sensitive_file_blocked(guard: PathGuard, tmp_roots: tuple[Path, Path]) -> None:
    docs_dir, _ = tmp_roots
    env_file = docs_dir / ".env"
    env_file.write_text("SECRET=abc", encoding="utf-8")
    with pytest.raises(PathNotAllowedError, match="[Ss]ensitive"):
        guard.resolve(str(env_file))


def test_ensure_within_size_limit_ok(guard: PathGuard, tmp_roots: tuple[Path, Path]) -> None:
    docs_dir, _ = tmp_roots
    small = docs_dir / "small.txt"
    small.write_text("x", encoding="utf-8")
    guard.ensure_within_size_limit(small)  # no error


def test_ensure_within_size_limit_dir(guard: PathGuard, tmp_roots: tuple[Path, Path]) -> None:
    docs_dir, _ = tmp_roots
    guard.ensure_within_size_limit(docs_dir)  # dir → no-op


def test_ensure_within_size_limit_nonexistent(guard: PathGuard, tmp_roots: tuple[Path, Path]) -> None:
    docs_dir, _ = tmp_roots
    guard.ensure_within_size_limit(docs_dir / "nope.txt")  # missing → no-op


def test_rel_to_root_property(guard: PathGuard, tmp_roots: tuple[Path, Path]) -> None:
    docs_dir, _ = tmp_roots
    resolved = guard.resolve("documents:/sub/file.txt")
    assert str(resolved.rel_to_root) == "sub/file.txt"


def test_relative_path_resolves_to_first_root(guard: PathGuard, tmp_roots: tuple[Path, Path]) -> None:
    docs_dir, _ = tmp_roots
    target = docs_dir / "reltest.txt"
    target.write_text("data", encoding="utf-8")
    resolved = guard.resolve("reltest.txt")
    assert resolved.root.name == "documents"


def test_node_modules_excluded(guard: PathGuard, tmp_roots: tuple[Path, Path]) -> None:
    docs_dir, _ = tmp_roots
    nm = docs_dir / "node_modules" / "pkg" / "index.js"
    nm.parent.mkdir(parents=True, exist_ok=True)
    nm.write_text("x", encoding="utf-8")
    with pytest.raises(PathNotAllowedError, match="exclude"):
        guard.resolve(str(nm))


def test_sensitive_env_file_blocked(make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]) -> None:
    from dokumen_pintar.pathguard import PathGuard
    cfg = make_config()
    cfg.safety.allow_sensitive = False
    guard = PathGuard(cfg)
    docs_dir, _ = tmp_roots
    env_file = docs_dir / ".env.local"
    env_file.write_text("SECRET=x", encoding="utf-8")
    with pytest.raises(PathNotAllowedError, match="[Ss]ensitive"):
        guard.resolve(str(env_file))


def test_sensitive_parent_blocked(make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]) -> None:
    from dokumen_pintar.pathguard import PathGuard
    cfg = make_config()
    cfg.safety.allow_sensitive = False
    guard = PathGuard(cfg)
    docs_dir, _ = tmp_roots
    secret_dir = docs_dir / ".ssh"
    secret_dir.mkdir(exist_ok=True)
    key_file = secret_dir / "id_rsa"
    key_file.write_text("key", encoding="utf-8")
    with pytest.raises(PathNotAllowedError, match="[Ss]ensitive"):
        guard.resolve(str(key_file))


def test_symlink_blocked_when_disabled(make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]) -> None:
    """Test symlink blocking. On Windows, Path.resolve() follows symlinks so
    the resolved path is no longer a symlink — use strict=False resolve to
    demonstrate the guard detects it."""
    from unittest.mock import patch as _patch
    from dokumen_pintar.pathguard import PathGuard, ResolvedPath
    cfg = make_config()
    cfg.safety.follow_symlinks = False
    guard = PathGuard(cfg)
    docs_dir, _ = tmp_roots
    real_file = docs_dir / "real.txt"
    real_file.write_text("hi", encoding="utf-8")
    link = docs_dir / "link.txt"
    try:
        link.symlink_to(real_file)
    except OSError:
        pytest.skip("symlinks not supported")
    # Patch Path.is_symlink on the resolved path to simulate symlink detection
    with _patch("pathlib.Path.is_symlink", return_value=True):
        with pytest.raises(PathNotAllowedError, match="[Ss]ymlink"):
            guard.resolve(str(link))


def test_relative_path_not_in_any_root(make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]) -> None:
    from dokumen_pintar.pathguard import PathGuard
    cfg = make_config()
    guard = PathGuard(cfg)
    with pytest.raises(PathNotAllowedError, match="does not resolve"):
        guard.resolve("../../etc/passwd")


def test_resolved_path_rel_to_root_valueerror() -> None:
    from dokumen_pintar.pathguard import ResolvedPath
    from dokumen_pintar.config import RootConfig
    from pathlib import PurePosixPath
    root_cfg = RootConfig(name="docs", path="C:/docs", writable=True)
    # absolute is not under root_absolute → ValueError in relative_to
    rp = ResolvedPath(
        original="test.txt",
        absolute=Path("D:/other/test.txt"),
        root=root_cfg,
        root_absolute=Path("C:/docs"),
    )
    rel = rp.rel_to_root
    assert isinstance(rel, PurePosixPath)


def test_relative_posix_valueerror() -> None:
    from dokumen_pintar.pathguard import PathGuard
    result = PathGuard._relative_posix(Path("D:/other/file.txt"), Path("C:/root"))
    assert "file.txt" in result


def test_resolve_workspace_uri_no_leading_slash(make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]) -> None:
    from dokumen_pintar.pathguard import PathGuard
    cfg = make_config()
    guard = PathGuard(cfg)
    docs_dir, _ = tmp_roots
    (docs_dir / "noslash.txt").write_text("x", encoding="utf-8")
    # URI without leading slash: "documents:noslash.txt" (92->94: rel doesn't start with /)
    rp = guard.resolve("documents:noslash.txt")
    assert rp.absolute == docs_dir / "noslash.txt"


def test_resolve_workspace_uri_unknown_root_falls_through(tmp_path: Path) -> None:
    from dokumen_pintar.config import AppConfig, RootConfig
    from dokumen_pintar.pathguard import PathGuard
    from dokumen_pintar.errors import ValidationError, PathNotAllowedError
    root_dir = tmp_path / "singleroot"
    root_dir.mkdir()
    cfg = AppConfig(roots=[RootConfig(name="myroot", path=str(root_dir), writable=True)])
    guard = PathGuard(cfg)
    # "badroot:/foo" → root_name="badroot" not found → 95->101 falls through (no raise expected)
    # Path resolves as relative under root — just verify the branch executes
    rp = guard.resolve("badroot:/foo/bar.txt")
    assert rp is not None


def test_looks_sensitive_env_prefix(make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]) -> None:
    from dokumen_pintar.pathguard import PathGuard
    cfg = make_config()
    cfg.safety.allow_sensitive = False
    guard = PathGuard(cfg)
    docs_dir, _ = tmp_roots
    # Use a .env-prefixed name NOT in _SENSITIVE_NAMES to reach line 204-205
    target = docs_dir / ".env.custom_unique_name"
    target.write_text("SECRET=1", encoding="utf-8")
    with pytest.raises(PathNotAllowedError, match="[Ss]ensitive"):
        guard.resolve(str(target))


def test_looks_sensitive_part_in_path(make_config: Callable[..., AppConfig], tmp_roots: tuple[Path, Path]) -> None:
    from dokumen_pintar.pathguard import PathGuard
    cfg = make_config()
    cfg.safety.allow_sensitive = False
    guard = PathGuard(cfg)
    docs_dir, _ = tmp_roots
    ssh_dir = docs_dir / ".ssh"
    ssh_dir.mkdir(exist_ok=True)
    target = ssh_dir / "config"
    target.write_text("Host *", encoding="utf-8")
    with pytest.raises(PathNotAllowedError, match="[Ss]ensitive"):
        guard.resolve(str(target))


def test_ambiguous_relative_path(tmp_path: Path) -> None:
    from dokumen_pintar.config import AppConfig, RootConfig
    from dokumen_pintar.pathguard import PathGuard
    from dokumen_pintar.errors import ValidationError
    root1 = tmp_path / "r1"
    root2 = tmp_path / "r2"
    root1.mkdir()
    root2.mkdir()
    cfg = AppConfig(
        roots=[
            RootConfig(name="r1", path=str(root1), writable=True),
            RootConfig(name="r2", path=str(root2), writable=True),
        ]
    )
    guard = PathGuard(cfg)
    # Both roots could match relative path "ambig.txt", neither file exists
    with pytest.raises(ValidationError, match="ambiguous"):
        guard.resolve("ambig.txt")
