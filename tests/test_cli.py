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

    rc = doctor(["--config", str(tmp_path / "nope.json")])
    assert rc == 2


def test_doctor_reports_missing_root(tmp_path: Path, capsys) -> None:
    from dokumen_pintar.cli import doctor

    cfg_data = {
        "roots": [{"name": "docs", "path": str(tmp_path / "missing"), "writable": True}],
    }
    cfg_file = tmp_path / "dokumen-pintar.config.json"
    cfg_file.write_text(json.dumps(cfg_data), encoding="utf-8")

    rc = doctor(["--config", str(cfg_file)])
    assert rc == 1  # one issue reported
    out = capsys.readouterr().out
    assert "MISSING" in out


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


def test_doctor_semantic_enabled_module_present(tmp_path: Path) -> None:
    """Cover the semantic_search-enabled branch when the dependency imports cleanly."""
    from dokumen_pintar.cli import doctor

    docs = tmp_path / "docs"
    docs.mkdir()
    cfg_data = {
        "roots": [{"name": "docs", "path": str(docs), "writable": True}],
        "semantic_search": {"enabled": True},
    }
    cfg_file = tmp_path / "dokumen-pintar.config.json"
    cfg_file.write_text(json.dumps(cfg_data), encoding="utf-8")

    # Inject a fake sentence_transformers so the import succeeds.
    import sys

    fake = type(sys)("sentence_transformers")
    sys.modules["sentence_transformers"] = fake
    try:
        rc = doctor(["--config", str(cfg_file)])
    finally:
        sys.modules.pop("sentence_transformers", None)
    assert rc == 0


def test_doctor_semantic_enabled_module_missing(tmp_path: Path, monkeypatch) -> None:
    """Cover the failure branch when sentence_transformers is not importable."""
    from dokumen_pintar.cli import doctor

    docs = tmp_path / "docs"
    docs.mkdir()
    cfg_data = {
        "roots": [{"name": "docs", "path": str(docs), "writable": True}],
        "semantic_search": {"enabled": True},
    }
    cfg_file = tmp_path / "dokumen-pintar.config.json"
    cfg_file.write_text(json.dumps(cfg_data), encoding="utf-8")

    import builtins

    real_import = builtins.__import__

    def _blocked_import(name, *args, **kwargs):
        if name == "sentence_transformers":
            raise ImportError("blocked for test")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _blocked_import)
    rc = doctor(["--config", str(cfg_file)])
    assert rc == 1


def test_doctor_invalid_config(tmp_path: Path) -> None:
    from dokumen_pintar.cli import doctor

    cfg_file = tmp_path / "broken.json"
    cfg_file.write_text("{not valid json", encoding="utf-8")
    rc = doctor(["--config", str(cfg_file)])
    assert rc == 2


def test_doctor_with_readonly_root(tmp_path: Path, capsys) -> None:
    from dokumen_pintar.cli import doctor

    docs = tmp_path / "docs"
    docs.mkdir()
    refs = tmp_path / "refs"
    refs.mkdir()
    cfg_data = {
        "roots": [
            {"name": "docs", "path": str(docs), "writable": True},
            {"name": "refs", "path": str(refs), "writable": False},
        ],
    }
    cfg_file = tmp_path / "dokumen-pintar.config.json"
    cfg_file.write_text(json.dumps(cfg_data), encoding="utf-8")

    rc = doctor(["--config", str(cfg_file)])
    assert rc == 0
    out = capsys.readouterr().out
    # Both roots should appear, with the read-only one tagged [ro].
    assert "[ro] refs" in out
    assert "[rw] docs" in out


def test_doctor_mcpdocs_not_writable(tmp_path: Path, monkeypatch, capsys) -> None:
    """Trigger the OSError branch when .mcpdocs cannot be created."""
    from dokumen_pintar.cli import doctor

    docs = tmp_path / "docs"
    docs.mkdir()
    cfg_data = {
        "roots": [{"name": "docs", "path": str(docs), "writable": True}],
    }
    cfg_file = tmp_path / "dokumen-pintar.config.json"
    cfg_file.write_text(json.dumps(cfg_data), encoding="utf-8")

    # Force any .mcpdocs mkdir attempt to raise OSError.
    real_mkdir = Path.mkdir

    def _failing_mkdir(self, *args, **kwargs):
        if self.name == ".mcpdocs":
            raise OSError("simulated permission denied")
        return real_mkdir(self, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", _failing_mkdir)
    rc = doctor(["--config", str(cfg_file)])
    assert rc == 1
    out = capsys.readouterr().out
    assert "WARN" in out and ".mcpdocs not writable" in out
