"""Tests for :mod:`dokumen_pintar.server`."""

from __future__ import annotations

from typing import Callable
from unittest.mock import patch

from dokumen_pintar.config import AppConfig
from dokumen_pintar.context import AppContext
from dokumen_pintar.server import _build_server, _configure_logging, main


def test_build_server_returns_mcp_and_context(make_config: Callable[..., AppConfig]) -> None:
    cfg = make_config()
    mcp, ctx = _build_server(cfg)
    assert mcp is not None
    assert isinstance(ctx, AppContext)


def test_configure_logging_verbose() -> None:
    _configure_logging(verbose=True)


def test_configure_logging_non_verbose() -> None:
    _configure_logging(verbose=False)


def test_main_missing_config(tmp_path) -> None:
    missing = tmp_path / "nonexistent.json"
    rc = main(["--config", str(missing)])
    assert rc == 2


def test_main_version(capsys) -> None:
    import pytest

    with pytest.raises(SystemExit) as exc_info:
        main(["--version"])
    assert exc_info.value.code == 0


# ── Additional server coverage ──

import json
import pytest


def test_main_stdio_transport(tmp_path, make_config: Callable[..., AppConfig]) -> None:
    cfg = make_config()
    cfg_path = tmp_path / "server_cfg.json"
    cfg_path.write_text(json.dumps(cfg.model_dump(), default=str), encoding="utf-8")

    with patch("dokumen_pintar.server.FastMCP") as MockMCP:
        mock_mcp = MockMCP.return_value
        mock_mcp._tool_manager = type("T", (), {"_tools": {}})()
        mock_mcp.run = lambda transport: None  # no-op
        rc = main(["--config", str(cfg_path), "--transport", "stdio"])
        assert rc == 0


def test_main_sse_transport(tmp_path, make_config: Callable[..., AppConfig]) -> None:
    cfg = make_config()
    cfg_path = tmp_path / "server_cfg2.json"
    cfg_path.write_text(json.dumps(cfg.model_dump(), default=str), encoding="utf-8")

    with patch("dokumen_pintar.server.FastMCP") as MockMCP, \
         patch("uvicorn.run") as mock_uvicorn:
        mock_mcp = MockMCP.return_value
        mock_mcp._tool_manager = type("T", (), {"_tools": {}})()
        mock_mcp.settings = type("S", (), {"host": "0.0.0.0", "port": 8000})()
        mock_mcp.sse_app = lambda: "sse_app"
        rc = main(["--config", str(cfg_path), "--transport", "sse"])
        assert rc == 0
        mock_uvicorn.assert_called_once()


def test_main_http_transport(tmp_path, make_config: Callable[..., AppConfig]) -> None:
    cfg = make_config()
    cfg_path = tmp_path / "server_cfg3.json"
    cfg_path.write_text(json.dumps(cfg.model_dump(), default=str), encoding="utf-8")

    with patch("dokumen_pintar.server.FastMCP") as MockMCP, \
         patch("uvicorn.run") as mock_uvicorn:
        mock_mcp = MockMCP.return_value
        mock_mcp._tool_manager = type("T", (), {"_tools": {}})()
        mock_mcp.settings = type("S", (), {"host": "0.0.0.0", "port": 8000})()
        mock_mcp.streamable_http_app = lambda: "http_app"
        rc = main(["--config", str(cfg_path), "--transport", "http"])
        assert rc == 0


def test_main_auto_transport_sse(tmp_path, make_config: Callable[..., AppConfig]) -> None:
    cfg = make_config()
    cfg.transport.http.enabled = True
    cfg_path = tmp_path / "server_auto.json"
    cfg_path.write_text(json.dumps(cfg.model_dump(), default=str), encoding="utf-8")

    with patch("dokumen_pintar.server.FastMCP") as MockMCP, \
         patch("uvicorn.run"):
        mock_mcp = MockMCP.return_value
        mock_mcp._tool_manager = type("T", (), {"_tools": {}})()
        mock_mcp.settings = type("S", (), {"host": "0.0.0.0", "port": 8000})()
        mock_mcp.sse_app = lambda: "sse_app"
        rc = main(["--config", str(cfg_path)])
        assert rc == 0


def test_main_with_host_port(tmp_path, make_config: Callable[..., AppConfig]) -> None:
    cfg = make_config()
    cfg_path = tmp_path / "server_cfg4.json"
    cfg_path.write_text(json.dumps(cfg.model_dump(), default=str), encoding="utf-8")

    with patch("dokumen_pintar.server.FastMCP") as MockMCP, \
         patch("uvicorn.run"):
        mock_mcp = MockMCP.return_value
        mock_mcp._tool_manager = type("T", (), {"_tools": {}})()
        mock_mcp.settings = type("S", (), {"host": "0.0.0.0", "port": 8000})()
        mock_mcp.sse_app = lambda: "sse_app"
        rc = main(["--config", str(cfg_path), "--transport", "sse",
                    "--host", "127.0.0.1", "--port", "9999"])
        assert rc == 0


def test_main_no_transport_enabled(tmp_path, make_config: Callable[..., AppConfig]) -> None:
    cfg = make_config()
    cfg.transport.http.enabled = False
    cfg.transport.stdio = False
    cfg_path = tmp_path / "server_notr.json"
    cfg_path.write_text(json.dumps(cfg.model_dump(), default=str), encoding="utf-8")

    with patch("dokumen_pintar.server.FastMCP") as MockMCP:
        mock_mcp = MockMCP.return_value
        mock_mcp._tool_manager = type("T", (), {"_tools": {}})()
        rc = main(["--config", str(cfg_path)])
        assert rc == 2


def test_main_auto_select_stdio_transport(tmp_path, make_config: Callable[..., AppConfig]) -> None:
    cfg = make_config()
    cfg.transport.http.enabled = False
    cfg.transport.stdio = True
    cfg_path = tmp_path / "server_stdio.json"
    cfg_path.write_text(json.dumps(cfg.model_dump(), default=str), encoding="utf-8")

    with patch("dokumen_pintar.server.FastMCP") as MockMCP:
        mock_mcp = MockMCP.return_value
        mock_mcp._tool_manager = type("T", (), {"_tools": {}})()
        mock_mcp.run.return_value = None
        rc = main(["--config", str(cfg_path)])
        assert rc == 0
        mock_mcp.run.assert_called_once_with("stdio")


# ── --root / --read-only flag tests ──


def test_parse_root_spec_name_path(tmp_path) -> None:
    from dokumen_pintar.server import _parse_root_spec

    r = _parse_root_spec(f"docs:{tmp_path}")
    assert r.name == "docs"
    assert r.path == str(tmp_path)
    assert r.writable is True


def test_parse_root_spec_name_path_ro(tmp_path) -> None:
    from dokumen_pintar.server import _parse_root_spec

    r = _parse_root_spec(f"refs:{tmp_path}:ro")
    assert r.name == "refs"
    assert r.path == str(tmp_path)
    assert r.writable is False


def test_parse_root_spec_name_path_rw(tmp_path) -> None:
    from dokumen_pintar.server import _parse_root_spec

    r = _parse_root_spec(f"work:{tmp_path}:rw")
    assert r.writable is True


def test_parse_root_spec_path_only(tmp_path) -> None:
    from dokumen_pintar.server import _parse_root_spec

    folder = tmp_path / "MyDocs"
    folder.mkdir()
    r = _parse_root_spec(str(folder))
    # Name derived from basename, sanitized to allowed chars.
    assert r.name == "MyDocs"
    assert r.path == str(folder)
    assert r.writable is True


def test_parse_root_spec_windows_drive_path_only(tmp_path) -> None:
    from dokumen_pintar.server import _parse_root_spec

    # A bare Windows-style "C:\..." path must not be parsed as NAME:PATH
    # (single-letter alpha head is treated as a drive letter).
    r = _parse_root_spec(r"C:\Users\Lenovo\Documents")
    assert r.name != "C"  # drive letter not used as name
    assert r.writable is True


def test_main_with_root_flag(tmp_path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    # Ensure no config can be auto-discovered in the cwd / env.
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DOKUMEN_PINTAR_CONFIG", raising=False)

    with patch("dokumen_pintar.server.FastMCP") as MockMCP:
        mock_mcp = MockMCP.return_value
        mock_mcp._tool_manager = type("T", (), {"_tools": {}})()
        mock_mcp.run = lambda transport: None
        # No --config; --root should let server start without config file.
        rc = main([
            "--root", f"docs:{workspace}",
            "--transport", "stdio",
        ])
        assert rc == 0


def test_main_with_root_flag_replaces_config_roots(tmp_path, make_config) -> None:
    # Existing config has its own roots; --root should fully replace them.
    cfg = make_config()
    cfg_path = tmp_path / "cfg.json"
    cfg_path.write_text(json.dumps(cfg.model_dump(), default=str), encoding="utf-8")

    extra = tmp_path / "extra"
    extra.mkdir()

    with patch("dokumen_pintar.server.build_context") as mock_build, \
         patch("dokumen_pintar.server.FastMCP") as MockMCP:
        mock_mcp = MockMCP.return_value
        mock_mcp._tool_manager = type("T", (), {"_tools": {}})()
        mock_mcp.run = lambda transport: None
        # Capture cfg passed to build_context.
        captured: dict = {}
        from dokumen_pintar.context import build_context as real_build
        def _capture(cfg):
            captured["cfg"] = cfg
            return real_build(cfg)
        mock_build.side_effect = _capture
        rc = main([
            "--config", str(cfg_path),
            "--root", f"only:{extra}",
            "--transport", "stdio",
        ])
        assert rc == 0
        assert [r.name for r in captured["cfg"].roots] == ["only"]


def test_main_read_only_flag(tmp_path, make_config) -> None:
    cfg = make_config()
    # Sanity: at least one writable root in baseline config.
    assert any(r.writable for r in cfg.roots)
    cfg_path = tmp_path / "cfg.json"
    cfg_path.write_text(json.dumps(cfg.model_dump(), default=str), encoding="utf-8")

    with patch("dokumen_pintar.server.build_context") as mock_build, \
         patch("dokumen_pintar.server.FastMCP") as MockMCP:
        mock_mcp = MockMCP.return_value
        mock_mcp._tool_manager = type("T", (), {"_tools": {}})()
        mock_mcp.run = lambda transport: None
        captured: dict = {}
        from dokumen_pintar.context import build_context as real_build
        def _capture(cfg):
            captured["cfg"] = cfg
            return real_build(cfg)
        mock_build.side_effect = _capture
        rc = main([
            "--config", str(cfg_path),
            "--read-only",
            "--transport", "stdio",
        ])
        assert rc == 0
        assert all(not r.writable for r in captured["cfg"].roots)


def test_parse_root_spec_empty_raises() -> None:
    from dokumen_pintar.errors import ConfigError
    from dokumen_pintar.server import _parse_root_spec

    with pytest.raises(ConfigError):
        _parse_root_spec("")


def test_parse_root_spec_empty_path_after_name_raises() -> None:
    from dokumen_pintar.errors import ConfigError
    from dokumen_pintar.server import _parse_root_spec

    # "docs:" — valid name, empty path → must raise.
    with pytest.raises(ConfigError):
        _parse_root_spec("docs:")


def test_parse_root_spec_path_only_sanitizes_basename(tmp_path) -> None:
    from dokumen_pintar.server import _parse_root_spec

    # Force a basename with characters outside [A-Za-z0-9_-].
    weird = tmp_path / "weird name (v2)"
    weird.mkdir()
    r = _parse_root_spec(str(weird))
    # Sanitization replaces disallowed chars with underscores.
    assert r.name and all(ch.isalnum() or ch in {"_", "-"} for ch in r.name)


def test_main_no_config_no_roots_returns_2(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DOKUMEN_PINTAR_CONFIG", raising=False)
    rc = main(["--transport", "stdio"])
    assert rc == 2


def test_main_duplicate_root_names_rejected(tmp_path) -> None:
    a = tmp_path / "a"
    a.mkdir()
    b = tmp_path / "b"
    b.mkdir()
    rc = main([
        "--root", f"work:{a}",
        "--root", f"work:{b}",
        "--transport", "stdio",
    ])
    assert rc == 2
