"""Tests for :mod:`dokumen_pintar.cli`."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dokumen_pintar.cli import _TEMPLATE, init_config


def test_init_config_creates_file(tmp_path: Path) -> None:
    out = tmp_path / "cfg.json"
    rc = init_config(["--path", str(out)])
    assert rc == 0
    assert out.exists()

    data = json.loads(out.read_text(encoding="utf-8"))
    assert "roots" in data
    assert data["roots"][0]["name"] == "documents"


def test_init_config_refuses_overwrite(tmp_path: Path) -> None:
    out = tmp_path / "cfg.json"
    out.write_text("{}", encoding="utf-8")
    rc = init_config(["--path", str(out)])
    assert rc == 2


def test_init_config_force_overwrites(tmp_path: Path) -> None:
    out = tmp_path / "cfg.json"
    out.write_text("{}", encoding="utf-8")
    rc = init_config(["--path", str(out), "--force"])
    assert rc == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert "roots" in data


def test_template_has_expected_keys() -> None:
    assert "roots" in _TEMPLATE
    assert "versioning" in _TEMPLATE
    assert "audit" in _TEMPLATE
    assert "transport" in _TEMPLATE
    assert "semantic_search" in _TEMPLATE
    assert "safety" in _TEMPLATE
    assert "exclude_patterns" in _TEMPLATE


def test_doctor_with_valid_config(tmp_path: Path) -> None:
    from dokumen_pintar.cli import doctor

    docs = tmp_path / "docs"
    docs.mkdir()
    cfg_data = {
        "roots": [{"name": "docs", "path": str(docs), "writable": True}],
    }
    cfg_file = tmp_path / "dokumen-pintar.config.json"
    cfg_file.write_text(json.dumps(cfg_data), encoding="utf-8")

    rc = doctor(["--config", str(cfg_file)])
    assert rc == 0


def test_doctor_missing_config(tmp_path: Path) -> None:
    from dokumen_pintar.cli import doctor
    from dokumen_pintar.errors import DokumenPintarError

    with pytest.raises((FileNotFoundError, OSError, DokumenPintarError)):
        doctor(["--config", str(tmp_path / "nope.json")])


def test_init_config_default_path(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    rc = init_config([])
    out = tmp_path / "dokumen-pintar.config.json"
    assert rc == 0
    assert out.exists()


def test_doctor_no_config_found(tmp_path: Path, monkeypatch) -> None:
    from dokumen_pintar.cli import doctor
    # Change to a dir with no config, no --config arg, and no env var
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DOKUMEN_PINTAR_CONFIG", raising=False)
    rc = doctor([])
    assert rc == 2
