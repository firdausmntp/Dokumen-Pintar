"""Path sandbox enforcement."""

from __future__ import annotations

import fnmatch
import os
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Iterable

from .config import AppConfig, RootConfig
from .errors import (
    FileTooLargeError,
    PathNotAllowedError,
    RootNotWritableError,
    ValidationError,
)


_SENSITIVE_NAMES = {
    ".env",
    ".env.local",
    ".env.production",
    "id_rsa",
    "id_ed25519",
    "id_ecdsa",
    ".netrc",
    ".pgpass",
    ".aws",
    ".ssh",
    "credentials",
    "credentials.json",
    "secret.json",
    "secrets.json",
}


@dataclass(frozen=True, slots=True)
class ResolvedPath:
    """Result of resolving a user-provided path against the workspace."""

    original: str
    absolute: Path
    root: RootConfig
    root_absolute: Path

    @property
    def rel_to_root(self) -> PurePosixPath:
        try:
            rel = self.absolute.relative_to(self.root_absolute)
        except ValueError:
            return PurePosixPath(self.absolute.as_posix())
        return PurePosixPath(rel.as_posix())

    @property
    def workspace_uri(self) -> str:
        return f"{self.root.name}:/{self.rel_to_root.as_posix().lstrip('/')}"


class PathGuard:
    """Validates + resolves every path before we touch the filesystem."""

    def __init__(self, config: AppConfig):
        self._config = config
        self._roots: list[tuple[RootConfig, Path]] = config.resolved_roots()
        self._excludes = tuple(config.exclude_patterns)

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------
    @property
    def roots(self) -> list[tuple[RootConfig, Path]]:
        return list(self._roots)

    def find_root_by_name(self, name: str) -> tuple[RootConfig, Path] | None:
        for r, p in self._roots:
            if r.name == name:
                return r, p
        return None

    # ------------------------------------------------------------------
    # Core resolution
    # ------------------------------------------------------------------
    def resolve(self, user_path: str, *, must_exist: bool = False) -> ResolvedPath:
        if not user_path or not isinstance(user_path, str):
            raise ValidationError("Path must be a non-empty string")

        # 1) Workspace URI: "<root>:/rel/path"
        if ":" in user_path and not user_path[1:3] == ":\\" and not user_path[1:3] == ":/":
            # Not a Windows drive letter — try workspace URI form.
            root_name, _, rel = user_path.partition(":")
            if rel.startswith("/") or rel.startswith("\\"):
                rel = rel.lstrip("/\\")
            match = self.find_root_by_name(root_name)
            if match is not None:
                root_cfg, root_abs = match
                candidate = (root_abs / rel).resolve() if rel else root_abs
                return self._finalize(user_path, candidate, root_cfg, root_abs, must_exist)

        # 2) Absolute / expanded path
        expanded = Path(os.path.expandvars(user_path)).expanduser()
        if expanded.is_absolute():
            resolved = expanded.resolve()
            for root_cfg, root_abs in self._roots:
                if resolved == root_abs or root_abs in resolved.parents:
                    return self._finalize(user_path, resolved, root_cfg, root_abs, must_exist)
            raise PathNotAllowedError(f"Path '{user_path}' is outside all configured roots")

        # 3) Relative: try each root; first match wins. Ambiguous if >1 match.
        matches: list[tuple[RootConfig, Path, Path]] = []
        for root_cfg, root_abs in self._roots:
            candidate = (root_abs / expanded).resolve()
            if candidate == root_abs or root_abs in candidate.parents:
                matches.append((root_cfg, root_abs, candidate))
        if not matches:
            raise PathNotAllowedError(
                f"Relative path '{user_path}' does not resolve inside any root"
            )
        if len(matches) > 1 and not any(m[2].exists() for m in matches):
            raise ValidationError(
                f"Relative path '{user_path}' is ambiguous between roots; "
                "use workspace URI form '<root>:/path'"
            )
        # Prefer an existing match if any.
        existing = [m for m in matches if m[2].exists()]
        chosen = existing[0] if existing else matches[0]
        root_cfg, root_abs, resolved = chosen
        return self._finalize(user_path, resolved, root_cfg, root_abs, must_exist)

    # ------------------------------------------------------------------
    # Finalization / checks
    # ------------------------------------------------------------------
    def _finalize(
        self,
        original: str,
        resolved: Path,
        root_cfg: RootConfig,
        root_abs: Path,
        must_exist: bool,
    ) -> ResolvedPath:
        # Symlink policy
        if not self._config.safety.follow_symlinks and resolved.is_symlink():
            raise PathNotAllowedError(
                f"Symlinks are disabled by safety.follow_symlinks: {resolved}"
            )

        # Excluded patterns
        rel_posix = self._relative_posix(resolved, root_abs)
        for pat in self._excludes:
            if fnmatch.fnmatch(rel_posix, pat) or fnmatch.fnmatch(resolved.as_posix(), pat):
                raise PathNotAllowedError(f"Path matches exclude pattern '{pat}': {resolved}")

        # Sensitive file gate
        if not self._config.safety.allow_sensitive and self._looks_sensitive(resolved):
            raise PathNotAllowedError(
                f"Sensitive path blocked (set safety.allow_sensitive=true to override): {resolved}"
            )

        if must_exist and not resolved.exists():
            raise PathNotAllowedError(f"Path does not exist: {resolved}")

        return ResolvedPath(
            original=original,
            absolute=resolved,
            root=root_cfg,
            root_absolute=root_abs,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def ensure_writable(self, resolved: ResolvedPath) -> None:
        if not resolved.root.writable:
            raise RootNotWritableError(
                f"Root '{resolved.root.name}' is read-only: cannot modify {resolved.absolute}"
            )

    def ensure_within_size_limit(self, path: Path) -> None:
        if not path.exists() or path.is_dir():
            return
        size = path.stat().st_size
        if size > self._config.max_file_size_bytes:
            raise FileTooLargeError(
                f"File {path} is {size} bytes, exceeds max {self._config.max_file_size_bytes}"
            )

    def iter_root_entries(self) -> Iterable[tuple[RootConfig, Path]]:
        yield from self._roots

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    @staticmethod
    def _relative_posix(p: Path, root: Path) -> str:
        try:
            return p.relative_to(root).as_posix()
        except ValueError:
            return p.as_posix()

    def _looks_sensitive(self, p: Path) -> bool:
        name = p.name.lower()
        if name in _SENSITIVE_NAMES:
            return True
        if name.startswith(".env"):
            return True
        for part in p.parts:
            if part.lower() in _SENSITIVE_NAMES:
                return True
        return False
