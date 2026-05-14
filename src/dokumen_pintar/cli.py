"""CLI helper: bootstrap a configuration file and probe roots."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .config import find_config_file


_TEMPLATE: dict[str, Any] = {
    "$schema": "./docs/config.schema.json",
    "roots": [
        {"name": "documents", "path": "~/Documents", "writable": True},
    ],
    "exclude_patterns": [
        "**/node_modules/**",
        "**/.git/**",
        "**/.venv/**",
        "**/__pycache__/**",
        "**/.mcpdocs/**",
    ],
    "max_file_size_mb": 100,
    "default_encoding": "utf-8",
    "auto_detect_encoding": True,
    "versioning": {
        "enabled": True,
        "storage_mode": "flexible",
        "global_storage_path": None,
        "retention_days": 30,
        "max_versions_per_file": 50,
    },
    "audit": {"enabled": True, "log_path": None},
    "transport": {
        "stdio": True,
        "http": {"enabled": False, "host": "127.0.0.1", "port": 7878, "auth_token": None},
    },
    "semantic_search": {
        "enabled": False,
        "model": "sentence-transformers/all-MiniLM-L6-v2",
        "index_path": None,
        "auto_index_globs": ["**/*.txt", "**/*.md"],
        "chunk_size": 512,
        "chunk_overlap": 64,
    },
    "safety": {
        "allow_sensitive": False,
        "follow_symlinks": False,
        "validate_roundtrip_writes": True,
    },
}


def _write_config(path: Path, force: bool) -> int:
    if path.exists() and not force:
        print(f"refusing to overwrite existing {path}; pass --force to replace", file=sys.stderr)
        return 2
    path.write_text(json.dumps(_TEMPLATE, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {path}")
    return 0


def init_config(argv: list[str] | None = None) -> int:
    """Entrypoint for the ``dokumen-pintar-init`` script."""
    parser = argparse.ArgumentParser(prog="dokumen-pintar-init")
    parser.add_argument(
        "--path",
        default="dokumen-pintar.config.json",
        help="Output path for the config (default: ./dokumen-pintar.config.json)",
    )
    parser.add_argument("--force", action="store_true", help="Overwrite if it exists")
    args = parser.parse_args(argv)
    return _write_config(Path(args.path).expanduser().resolve(), args.force)


def doctor(argv: list[str] | None = None) -> int:
    """Quick smoke check: locate config, print resolved roots."""
    parser = argparse.ArgumentParser(prog="dokumen-pintar doctor")
    parser.add_argument("--config", default=None)
    args = parser.parse_args(argv)
    from .config import load_config

    cfg_path = Path(args.config).resolve() if args.config else find_config_file()
    if cfg_path is None:
        print("no config found", file=sys.stderr)
        return 2
    cfg = load_config(cfg_path)
    print(f"config: {cfg_path}")
    for r, abs_path in cfg.resolved_roots():
        marker = "rw" if r.writable else "ro"
        exists = "exists" if abs_path.exists() else "MISSING"
        print(f"  - [{marker}] {r.name:<20} -> {abs_path} ({exists})")
    return 0
