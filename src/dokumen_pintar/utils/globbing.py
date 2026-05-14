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
