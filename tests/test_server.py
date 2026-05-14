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
