"""Tests for :mod:`dokumen_pintar.config`."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dokumen_pintar.config import AppConfig, find_config_file, load_config
from dokumen_pintar.errors import ConfigError


def _write_config(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_load_config_reads_valid_json(tmp_path: Path) -> None:
    cfg_path = tmp_path / "cfg.json"
    docs = tmp_path / "docs"
    docs.mkdir()
    _write_config(
        cfg_path,
        {
            "roots": [{"name": "docs", "path": str(docs), "writable": True}],
        },
    )

    cfg = load_config(cfg_path)
    assert isinstance(cfg, AppConfig)
    assert len(cfg.roots) == 1
    assert cfg.roots[0].name == "docs"


def test_load_config_raises_on_invalid_json(tmp_path: Path) -> None:
    cfg_path = tmp_path / "cfg.json"
    cfg_path.write_text("{not valid json", encoding="utf-8")
    with pytest.raises(ConfigError):
        load_config(cfg_path)


def test_duplicate_root_names_rejected(tmp_path: Path) -> None:
    cfg_path = tmp_path / "cfg.json"
    d1 = tmp_path / "d1"
    d2 = tmp_path / "d2"
    d1.mkdir()
    d2.mkdir()
    _write_config(
        cfg_path,
        {
            "roots": [
                {"name": "dup", "path": str(d1), "writable": True},
                {"name": "dup", "path": str(d2), "writable": False},
            ],
        },
    )

    with pytest.raises(ConfigError):
        load_config(cfg_path)


def test_find_config_file_honours_env_var(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg_path = tmp_path / "custom-config.json"
    docs = tmp_path / "docs"
    docs.mkdir()
    _write_config(
        cfg_path,
        {"roots": [{"name": "docs", "path": str(docs), "writable": True}]},
    )

    monkeypatch.setenv("DOKUMEN_PINTAR_CONFIG", str(cfg_path))

    # Run from a different directory so the default locations aren't hit.
    other_dir = tmp_path / "elsewhere"
    other_dir.mkdir()
    monkeypatch.chdir(other_dir)

    found = find_config_file()
    assert found is not None
    assert found.resolve() == cfg_path.resolve()


def test_find_config_file_returns_none_when_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("DOKUMEN_PINTAR_CONFIG", raising=False)
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    monkeypatch.chdir(empty_dir)
    assert find_config_file() is None


def test_load_config_missing_file_raises(tmp_path: Path) -> None:
    missing = tmp_path / "nope.json"
    with pytest.raises(ConfigError):
        load_config(missing)


def test_load_config_no_roots_rejected(tmp_path: Path) -> None:
    cfg_path = tmp_path / "cfg.json"
    _write_config(cfg_path, {"roots": []})
    with pytest.raises(ConfigError):
        load_config(cfg_path)


def test_load_config_strips_dollar_schema(tmp_path: Path) -> None:
    cfg_path = tmp_path / "cfg.json"
    docs = tmp_path / "docs"
    docs.mkdir()
    _write_config(
        cfg_path,
        {
            "$schema": "https://example.com/schema.json",
            "roots": [{"name": "docs", "path": str(docs), "writable": True}],
        },
    )
    cfg = load_config(cfg_path)
    assert cfg.roots[0].name == "docs"


def test_max_file_size_bytes_derives_from_mb(tmp_path: Path) -> None:
    cfg_path = tmp_path / "cfg.json"
    docs = tmp_path / "docs"
    docs.mkdir()
    _write_config(
        cfg_path,
        {
            "roots": [{"name": "docs", "path": str(docs), "writable": True}],
            "max_file_size_mb": 10,
        },
    )
    cfg = load_config(cfg_path)
    assert cfg.max_file_size_bytes == 10 * 1024 * 1024


def test_find_config_file_finds_default_in_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("DOKUMEN_PINTAR_CONFIG", raising=False)
    docs = tmp_path / "docs"
    docs.mkdir()
    default_cfg = tmp_path / "dokumen-pintar.config.json"
    _write_config(
        default_cfg,
        {"roots": [{"name": "docs", "path": str(docs), "writable": True}]},
    )

    monkeypatch.chdir(tmp_path)
    found = find_config_file()
    assert found is not None
    assert found.resolve() == default_cfg.resolve()


def test_root_name_invalid_chars_rejected(tmp_path: Path) -> None:
    from pydantic import ValidationError as PydanticValidationError
    from dokumen_pintar.config import RootConfig
    with pytest.raises(PydanticValidationError):
        RootConfig(name="bad name!", path=str(tmp_path), writable=True)


def test_load_config_none_no_config_found(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DOKUMEN_PINTAR_CONFIG", raising=False)
    with pytest.raises(ConfigError, match="[Nn]o configuration"):
        load_config(None)


def test_load_config_none_auto_discover(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import json
    cfg_content = {
        "roots": [{"name": "docs", "path": str(tmp_path / "docs")}]
    }
    (tmp_path / "docs").mkdir()
    cfg_file = tmp_path / "dokumen-pintar.config.json"
    cfg_file.write_text(json.dumps(cfg_content), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DOKUMEN_PINTAR_CONFIG", raising=False)
    cfg = load_config(None)
    assert cfg.roots[0].name == "docs"
