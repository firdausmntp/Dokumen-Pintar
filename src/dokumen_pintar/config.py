"""Configuration loading & data models."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from .errors import ConfigError


class RootConfig(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    path: str
    writable: bool = True

    @field_validator("name")
    @classmethod
    def _validate_name(cls, v: str) -> str:
        if not v.replace("-", "").replace("_", "").isalnum():
            raise ValueError("root name must be alphanumeric / dash / underscore")
        return v


class VersioningConfig(BaseModel):
    enabled: bool = True
    # "per_root"   -> snapshots go to <root>/.mcpdocs/versions/
    # "global"     -> snapshots go to global_storage_path (shared for all roots)
    # "flexible"   -> try per-root, fall back to global if root is read-only
    storage_mode: Literal["per_root", "global", "flexible"] = "flexible"
    global_storage_path: str | None = None
    retention_days: int = Field(default=30, ge=0)
    max_versions_per_file: int = Field(default=50, ge=1)


class AuditConfig(BaseModel):
    enabled: bool = True
    log_path: str | None = None  # null -> .mcpdocs/audit.jsonl (per first writable root or global)


class HTTPTransport(BaseModel):
    enabled: bool = False
    host: str = "127.0.0.1"
    port: int = Field(default=7878, ge=1, le=65535)
    auth_token: str | None = None


class TransportConfig(BaseModel):
    stdio: bool = True
    http: HTTPTransport = Field(default_factory=HTTPTransport)


class SemanticSearchConfig(BaseModel):
    enabled: bool = False
    model: str = "sentence-transformers/all-MiniLM-L6-v2"
    index_path: str | None = None
    auto_index_globs: list[str] = Field(default_factory=lambda: ["**/*.txt", "**/*.md"])
    chunk_size: int = 512
    chunk_overlap: int = 64


class SafetyConfig(BaseModel):
    allow_sensitive: bool = False
    follow_symlinks: bool = False
    validate_roundtrip_writes: bool = True


class AppConfig(BaseModel):
    roots: list[RootConfig]
    exclude_patterns: list[str] = Field(
        default_factory=lambda: [
            "**/node_modules/**",
            "**/.git/**",
            "**/.venv/**",
            "**/__pycache__/**",
            "**/.mcpdocs/**",
        ]
    )
    max_file_size_mb: int = Field(default=100, ge=1)
    default_encoding: str = "utf-8"
    auto_detect_encoding: bool = True
    versioning: VersioningConfig = Field(default_factory=VersioningConfig)
    audit: AuditConfig = Field(default_factory=AuditConfig)
    transport: TransportConfig = Field(default_factory=TransportConfig)
    semantic_search: SemanticSearchConfig = Field(default_factory=SemanticSearchConfig)
    safety: SafetyConfig = Field(default_factory=SafetyConfig)

    @model_validator(mode="after")
    def _validate_roots(self) -> "AppConfig":
        if not self.roots:
            raise ValueError("At least one root must be configured")
        names = [r.name for r in self.roots]
        if len(set(names)) != len(names):
            raise ValueError("Root names must be unique")
        return self

    @property
    def max_file_size_bytes(self) -> int:
        return self.max_file_size_mb * 1024 * 1024

    def resolved_roots(self) -> list[tuple[RootConfig, Path]]:
        out: list[tuple[RootConfig, Path]] = []
        for r in self.roots:
            p = Path(os.path.expandvars(r.path)).expanduser().resolve()
            out.append((r, p))
        return out


_DEFAULT_LOCATIONS = (
    "dokumen-pintar.config.json",
    ".dokumen-pintar.json",
)


def find_config_file(start: Path | None = None) -> Path | None:
    start = (start or Path.cwd()).resolve()
    candidates: list[Path] = []
    for name in _DEFAULT_LOCATIONS:
        candidates.append(start / name)
    env_path = os.environ.get("DOKUMEN_PINTAR_CONFIG")
    if env_path:
        candidates.insert(0, Path(env_path).expanduser().resolve())
    for c in candidates:
        if c.is_file():
            return c
    return None


def load_config(path: Path | str | None = None) -> AppConfig:
    """Load and validate an :class:`AppConfig`.

    If *path* is None we search the current working directory and the
    ``DOKUMEN_PINTAR_CONFIG`` environment variable.
    """
    if path is None:
        found = find_config_file()
        if found is None:
            raise ConfigError(
                "No configuration file found. "
                "Set DOKUMEN_PINTAR_CONFIG or create dokumen-pintar.config.json"
            )
        path = found
    path = Path(path)
    try:
        raw: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ConfigError(f"Unable to read config {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Invalid JSON in {path}: {exc}") from exc
    raw.pop("$schema", None)
    try:
        return AppConfig.model_validate(raw)
    except Exception as exc:  # pragma: no cover - pydantic gives nice msg
        raise ConfigError(f"Configuration validation failed: {exc}") from exc
