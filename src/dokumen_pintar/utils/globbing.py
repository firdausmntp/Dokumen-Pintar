"""Glob matching helpers."""

from __future__ import annotations

import fnmatch
import re
from pathlib import PurePosixPath


def compile_globs(patterns: list[str]) -> list[re.Pattern[str]]:
    return [re.compile(fnmatch.translate(p)) for p in patterns]


def any_match(text: str, compiled: list[re.Pattern[str]]) -> bool:
    # Try both the raw text and a leading-slash variant so patterns of the
    # form ``**/X/**`` also catch paths that start with ``X/``.
    prefixed = "/" + text
    return any(p.match(text) or p.match(prefixed) for p in compiled)


def posix_of(rel: str) -> str:
    return PurePosixPath(rel).as_posix()


_ROOT_URI_RX = re.compile(r"^([A-Za-z0-9_-]+):/+(.*)$")


def split_root_glob(glob: str | None) -> tuple[str | None, str | None]:
    """Split a glob like ``<root>:/sub/*.docx`` into (root_name, bare_pattern).

    Returns ``(None, glob)`` when the input has no ``<root>:/`` prefix.
    Returns ``(None, None)`` when the input is None or empty.

    The bare pattern is stripped of the URI prefix so it can be passed to
    ``fnmatch`` directly against ``rel`` (path relative to the root) or
    ``p.name``.

    Examples:
        >>> split_root_glob(None)
        (None, None)
        >>> split_root_glob("*.docx")
        (None, "*.docx")
        >>> split_root_glob("kp:/*.docx")
        ("kp", "*.docx")
        >>> split_root_glob("kp:/sub/**/*.txt")
        ("kp", "sub/**/*.txt")
    """
    if glob is None:
        return None, None
    if glob == "":
        return None, ""
    m = _ROOT_URI_RX.match(glob)
    if not m:
        return None, glob
    root = m.group(1)
    bare = m.group(2) or "*"
    return root, bare
