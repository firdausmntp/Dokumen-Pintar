"""FastMCP server entry point."""

from __future__ import annotations

import argparse
import logging
import re
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from . import __version__
from .config import AppConfig, RootConfig, load_config
from .context import AppContext, build_context
from .errors import ConfigError, DokumenPintarError


logger = logging.getLogger("dokumen_pintar")


_ROOT_NAME_RX = re.compile(r"^[A-Za-z0-9_-]+$")


def _parse_root_spec(spec: str) -> RootConfig:
    """Parse a --root flag value.

    Accepted forms:
      * ``NAME:PATH``                writable=True
      * ``NAME:PATH:rw`` / ``...:ro``
      * ``PATH``                     auto-named after the directory basename
    """
    if not spec:
        raise ConfigError("--root spec must not be empty")

    # Detect whether the leading token is a name (no slashes, no drive colon)
    head, sep, tail = spec.partition(":")
    if sep and _ROOT_NAME_RX.match(head) and not (len(head) == 1 and head.isalpha()):
        # head is a valid root name, tail is "PATH" or "PATH:ro"/"PATH:rw"
        path_part, _, mode = tail.rpartition(":")
        if mode in {"rw", "ro"} and path_part:
            path_value = path_part
            writable = mode == "rw"
        else:
            path_value = tail
            writable = True
        name = head
    else:
        # Path-only form; derive a name from the basename.
        path_value = spec
        path_obj = Path(path_value).expanduser()
        name = path_obj.name or "root"
        if not _ROOT_NAME_RX.match(name):
            name = re.sub(r"[^A-Za-z0-9_-]", "_", name) or "root"
        writable = True

    if not path_value.strip():
        raise ConfigError(f"--root spec missing path: {spec!r}")

    return RootConfig(name=name, path=path_value, writable=writable)


def _apply_cli_roots(cfg: AppConfig, root_specs: list[str], read_only: bool) -> AppConfig:
    """Override / mutate config based on CLI flags."""
    if root_specs:
        new_roots: list[RootConfig] = []
        seen: set[str] = set()
        for spec in root_specs:
            r = _parse_root_spec(spec)
            if r.name in seen:
                raise ConfigError(f"duplicate --root name: {r.name!r}")
            seen.add(r.name)
            new_roots.append(r)
        cfg.roots = new_roots
    if read_only:
        cfg.roots = [r.model_copy(update={"writable": False}) for r in cfg.roots]
    return cfg


def _load_or_synthesize_config(config_path: str | None, root_specs: list[str]) -> AppConfig:
    """Load config from disk; if absent and --root given, build a minimal config."""
    if config_path:
        return load_config(Path(config_path).resolve())
    try:
        return load_config(None)
    except ConfigError:
        if not root_specs:
            raise
        # No config file but at least one --root provided: synthesize a defaults
        # config and let _apply_cli_roots populate the roots list.
        # Use a placeholder root so AppConfig validation passes; it is replaced
        # immediately afterwards by _apply_cli_roots.
        placeholder = RootConfig(name="placeholder", path=str(Path.cwd()), writable=False)
        return AppConfig(roots=[placeholder])


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
        authoring,
        batch,
        batch_structured,
        bibliography,
        compare,
        content_crud,
        file_crud,
        images,
        lint,
        metadata,
        search,
        sections,
        structured,
        templates,
        toc,
        version,
        workspace,
    )

    workspace.register(mcp, ctx)
    workspace.register_diagnose(mcp, ctx)
    file_crud.register(mcp, ctx)
    content_crud.register(mcp, ctx)
    structured.register(mcp, ctx)
    search.register(mcp, ctx)
    batch.register(mcp, ctx)
    batch_structured.register(mcp, ctx)
    version.register(mcp, ctx)
    authoring.register(mcp, ctx)
    metadata.register(mcp, ctx)
    metadata.register_batch(mcp, ctx)
    images.register(mcp, ctx)
    sections.register(mcp, ctx)
    templates.register(mcp, ctx)
    toc.register(mcp, ctx)
    bibliography.register(mcp, ctx)
    compare.register(mcp, ctx)
    lint.register(mcp, ctx)

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
        "--root",
        action="append",
        default=[],
        metavar="NAME:PATH[:rw|ro]",
        help=(
            "Override workspace roots (repeatable). Replaces any roots from "
            "the config. Forms: 'NAME:PATH', 'NAME:PATH:ro', or just 'PATH' "
            "(name derived from basename)."
        ),
    )
    parser.add_argument(
        "--read-only",
        action="store_true",
        help="Force every root to writable=false (overrides config + --root spec).",
    )
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
        cfg = _load_or_synthesize_config(args.config, args.root)
        cfg = _apply_cli_roots(cfg, args.root, args.read_only)
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
