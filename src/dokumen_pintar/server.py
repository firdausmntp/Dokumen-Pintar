"""FastMCP server entry point."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from . import __version__
from .config import AppConfig, load_config
from .context import AppContext, build_context
from .errors import DokumenPintarError


logger = logging.getLogger("dokumen_pintar")


def _build_server(cfg: AppConfig) -> tuple[FastMCP, AppContext]:
    ctx = build_context(cfg)
    mcp = FastMCP(
        name="dokumen-pintar",
        instructions=(
            "Dokumen-Pintar — universal document CRUD across text, JSON, YAML, "
            "CSV, XML, DOCX, XLSX, PPTX, and PDF. Always start by calling "
            "`workspace_list_roots`. Use workspace URIs like `<root>:/relative/path`. "
            "Destructive operations (file_delete, struct_delete, batch_*) always "
            "take a snapshot first; recover via `version_list` + `version_restore`."
        ),
    )

    from .tools import (
        batch,
        content_crud,
        file_crud,
        search,
        structured,
        version,
        workspace,
    )

    workspace.register(mcp, ctx)
    file_crud.register(mcp, ctx)
    content_crud.register(mcp, ctx)
    structured.register(mcp, ctx)
    search.register(mcp, ctx)
    batch.register(mcp, ctx)
    version.register(mcp, ctx)

    return mcp, ctx


def _configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-5s %(name)s: %(message)s",
        stream=sys.stderr,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="dokumen-pintar", description=__doc__)
    parser.add_argument("--config", help="Path to configuration JSON", default=None)
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "http"],
        default=None,
        help="Override transport (default: follow config)",
    )
    parser.add_argument("--host", default=None, help="HTTP/SSE host override")
    parser.add_argument("--port", type=int, default=None, help="HTTP/SSE port override")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("--version", action="version", version=f"dokumen-pintar {__version__}")
    args = parser.parse_args(argv)

    _configure_logging(args.verbose)

    try:
        cfg = load_config(Path(args.config).resolve() if args.config else None)
    except DokumenPintarError as exc:
        logger.error("Configuration error: %s", exc)
        return 2

    mcp, ctx = _build_server(cfg)

    transport = args.transport
    if transport is None:
        if cfg.transport.http.enabled:
            transport = "sse"
        elif cfg.transport.stdio:
            transport = "stdio"
        else:
            logger.error("No transport enabled in config")
            return 2

    host = args.host or cfg.transport.http.host
    port = args.port or cfg.transport.http.port

    logger.info("starting dokumen-pintar v%s on %s", __version__, transport)
    logger.info("roots: %s", [r[0].name for r in ctx.guard.roots])

    if transport == "stdio":
        mcp.run("stdio")
    elif transport in {"sse", "http"}:
        # FastMCP uses uvicorn under the hood for streamable transports.
        import uvicorn

        mcp.settings.host = host
        mcp.settings.port = port
        app = mcp.sse_app() if transport == "sse" else mcp.streamable_http_app()
        uvicorn.run(app, host=host, port=port, log_level="info" if args.verbose else "warning")
    else:  # pragma: no cover
        logger.error("Unknown transport: %s", transport)
        return 2

    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
