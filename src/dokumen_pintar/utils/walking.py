"""Workspace file walking helpers shared by search and batch tools.

Both :mod:`tools.search` and :mod:`tools.batch` need to enumerate files
across one or many roots, optionally filtered by a glob (which may carry
a ``<root>:/`` URI prefix) and optionally restricted to writable roots.
The two implementations diverged enough to drift, so they are unified
here behind one iterator.
"""

from __future__ import annotations

import fnmatch
from pathlib import Path
from typing import Iterator, TYPE_CHECKING

from .globbing import any_match, compile_globs, split_root_glob

if TYPE_CHECKING:  # pragma: no cover - import-time only
    from ..context import AppContext


def _expand_doublestar(pattern: str) -> tuple[str, ...]:
    """Expand a leading ``**/`` so it matches both top-level and nested files.

    ``fnmatch`` treats ``**/x`` as "exactly one path component before ``x``",
    so a pattern like ``**/*.txt`` will skip top-level ``.txt`` files - the
    most surprising default in v1.0.x. v1.1.0 expands the pattern into two
    siblings - top-level (no prefix) and nested (``**/`` prefix) - so a
    user typing ``**/*.txt`` gets both.

    Patterns that don't start with ``**/`` are returned unchanged. The
    returned tuple is always non-empty.
    """
    if pattern.startswith("**/"):
        rest = pattern[3:]
        return (rest, pattern) if rest else (pattern,)
    return (pattern,)


def iter_files(
    ctx: "AppContext",
    *,
    glob: str | None = None,
    root_filter: str | None = None,
    writable_only: bool = False,
) -> Iterator[tuple[str, Path, Path]]:
    """Yield ``(root_name, abs_path, root_abs)`` for each non-excluded file.

    Parameters
    ----------
    ctx:
        Active :class:`AppContext` (used for guard.roots, exclude_patterns).
    glob:
        Optional pattern. May carry a ``<root>:/`` URI prefix; the prefix
        is stripped and used as a root filter. ``None`` matches everything.
        ``""`` (empty string) yields nothing - mirrors batch's contract
        for "no pattern means no candidates".

        Patterns starting with ``**/`` are expanded so they match both
        top-level and nested files. ``**/*.txt`` therefore catches
        ``top.txt`` AND ``sub/nested.txt`` (was: nested only).
    root_filter:
        Restrict to a single root. Combines with the glob's URI prefix
        (if any) via ``AND`` - conflicting filters yield nothing.
    writable_only:
        When True, skip read-only roots. Used by batch operations.
    """
    if glob == "":
        return
    glob_root, bare_glob = split_root_glob(glob)
    if glob_root and root_filter and glob_root != root_filter:
        return
    effective_root = root_filter or glob_root
    excludes = compile_globs(ctx.config.exclude_patterns)
    bare_patterns = _expand_doublestar(bare_glob) if bare_glob else None

    for root_cfg, root_abs in ctx.guard.roots:
        if effective_root and root_cfg.name != effective_root:
            continue
        if writable_only and not root_cfg.writable:
            continue
        if not root_abs.exists():
            continue
        for p in root_abs.rglob("*"):
            if not p.is_file():
                continue
            try:
                rel = p.relative_to(root_abs).as_posix()
            except ValueError:
                continue
            if any_match(rel, excludes):
                continue
            if bare_patterns is not None and not any(
                fnmatch.fnmatch(rel, pat) or fnmatch.fnmatch(p.name, pat) for pat in bare_patterns
            ):
                continue
            yield root_cfg.name, p, root_abs
