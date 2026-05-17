# Contributing to Dokumen-Pintar

> This is `AGENTS.md` - the canonical onboarding doc for human contributors and AI coding agents working on this codebase.
> If you only have time for one section, read [Quick Start](#quick-start) and [Hard Rules](#hard-rules).

---

## Quick Start

```bash
git clone https://github.com/firdausmntp/Dokumen-Pintar.git
cd Dokumen-Pintar
python -m venv .venv && .\.venv\Scripts\Activate.ps1   # PowerShell
# or:  source .venv/bin/activate                       # bash/zsh

pip install -e ".[dev]"
pytest                                                 # 1403 tests, ~50s
```

Ship a change in three steps:

1. Branch off `main`, write failing tests first.
2. Make the smallest correct change. Keep tests at 100% coverage.
3. Open a PR with a clear before/after description.

```bash
ruff check src/ tests/                                 # lint
mypy src/dokumen_pintar/                               # type check
pytest                                                 # full suite (parallel)
```

If `ruff`, `mypy`, or `pytest` fails locally, your PR will fail CI too. Don't push until they're all green.

---

## Hard Rules

These are non-negotiable. PRs that violate them get rejected.

1. **100% test coverage stays at 100%.** `pyproject.toml` enforces `fail_under = 100`. New code without tests = no merge. If a branch is genuinely unreachable, mark it with `# pragma: no cover` and explain why in the comment.
2. **No `# type: ignore` and no `Any` casts in handler code** unless the upstream library has untyped public API. When you must, scope it to the smallest possible expression and add a one-line justification.
3. **Every mutating tool snapshots first.** `ctx.versions.snapshot(..., action="<op>_pre")` before the write, `_post` after. This is the recovery contract users rely on.
4. **Every mutating tool emits an audit record.** `ctx.audit.log("<tool_name>", path=..., ...)` is the audit contract.
5. **Every path goes through `PathGuard`.** Use `resolve_for_read` / `resolve_for_write` from `tools/_common.py`. Never `Path(user_input).resolve()` directly - that bypasses the sandbox.
6. **Backward compatibility within a major version.** Removing or renaming a tool, changing a parameter name, or breaking a return shape requires a major bump (2.0). Within `1.x.y`, additions only.
7. **Never log secrets.** If a tool surfaces file content, audit log records the path and action - not the bytes.
8. **No git commits or pushes from automation.** Run tests and write code; commits are the maintainer's call.

---

## Repo Layout

```
src/dokumen_pintar/
├── server.py / cli.py / config.py    Entry + runtime wiring
├── context.py                        AppContext (guard + versions + audit + registry + cache)
├── pathguard.py                      Sandboxed path resolution
├── versioning.py                     Copy-on-write snapshots + SQLite index
├── audit.py                          JSONL audit log
├── extract_cache.py                  Mtime/size-keyed cache for extract_for_search
├── handlers/                         One file per format. Self-registers on import.
│   ├── base.py                       FormatHandler protocol + HandlerCapability flags
│   ├── text_handler.py               .txt, .md (overridden by markdown_handler)
│   ├── markdown_handler.py           .md / .markdown (richer than text_handler)
│   ├── latex_handler.py              .tex
│   ├── json_yaml_handler.py          .json, .jsonc, .json5, .yaml, .yml
│   ├── csv_handler.py                .csv, .tsv
│   ├── xml_handler.py                .xml, .svg
│   ├── docx_handler.py               .docx
│   ├── xlsx_handler.py               .xlsx, .xlsm
│   ├── pptx_handler.py               .pptx
│   ├── pdf_handler.py                .pdf (read-only structured edits)
│   └── image_handler.py              .jpg, .jpeg, .png, .tif, .tiff, .webp, .bmp, .gif
├── tools/                            One file per category. Each `register(mcp, ctx)`.
│   ├── workspace.py / file_crud.py / content_crud.py
│   ├── structured.py / metadata.py / authoring.py
│   ├── batch.py / batch_structured.py
│   ├── search.py / version.py
│   └── _common.py                    Shared helpers (resolve_for_*, refuse_binary_text_op, ...)
├── authoring/                        DOCX/PDF generation from JSON spec or Markdown
├── semantic/                         Optional vector search (sentence-transformers)
└── utils/                            encoding, locks, globbing, walking, mime
tests/                                Mirrors src/ layout, one test_*.py per module
docs/                                 USAGE / CONFIG / TOOLS / ARCHITECTURE / BENCHMARK
docs/profiles/                        Six pre-tuned config presets
```

Dependencies flow one direction: `tools/ → handlers/ → utils/`. Handlers never import tools.

---

## How a Request Flows

A tool call from an MCP client lands in this pipeline:

```
client (Claude/Cursor/...) -- MCP -- server.py
                                       |
                                       v
                                tools/<category>.py
                                       |
                                       v
                            tools/_common.resolve_for_*()  ── PathGuard
                                       |                       │
                                       v                       v
                                  ResolvedPath          (sandbox check)
                                       |
                                       v
                                ctx.registry.for_path() ── handler
                                       |
                                       v
                                 handler.read_*() / write_*() / structured_*()
                                       |
                                       v
                                ctx.versions.snapshot() (pre)
                                       |
                                       v
                                  (mutation happens)
                                       |
                                       v
                                ctx.versions.snapshot() (post)
                                       |
                                       v
                                ctx.audit.log()
                                       |
                                       v
                                summarize_resolved() -> JSON response
```

Every mutating tool follows that exact shape. Read [tools/content_crud.py](src/dokumen_pintar/tools/content_crud.py) for the canonical reference.

---

## Adding a New Tool

1. Pick the right module under `tools/`. If it's a brand-new category, add a new file and register it in `server.py`'s `_build_server`.
2. Wrap the function in `@mcp.tool(name="...", description="...")`. The description is what AI agents see - write it for them, not for humans.
3. Resolve paths via `_common.resolve_for_read(ctx, path)` (read) or `resolve_for_write(ctx, path)` (write).
4. For binary container formats (DOCX/XLSX/PPTX/PDF), call `refuse_binary_text_op(ctx, resolved, op_name)` if you do raw text mutation.
5. For mutating tools, snapshot pre and post via `ctx.versions.snapshot(...)` and emit an audit record.
6. Return a dict containing `summarize_resolved(resolved)` plus tool-specific fields.
7. Add tests covering: happy path, sandbox violation, sensitive file refusal, write to read-only root, file-too-large, unicode/CRLF, missing parent dir.

```python
# tools/example.py
from mcp.server.fastmcp import FastMCP
from ..context import AppContext
from ..utils.locks import file_lock
from ._common import resolve_for_write, summarize_resolved

def register(mcp: FastMCP, ctx: AppContext) -> None:
    @mcp.tool(
        name="example_op",
        description="One-line description that an AI agent will read."
    )
    def example_op(path: str, value: str) -> dict:
        resolved = resolve_for_write(ctx, path)
        with file_lock(resolved.absolute):
            ctx.versions.snapshot(
                root_name=resolved.root.name,
                rel_path=resolved.rel_to_root.as_posix(),
                source=resolved.absolute,
                action="example_op_pre",
            )
            # ... do the mutation ...
            snap = ctx.versions.snapshot(
                root_name=resolved.root.name,
                rel_path=resolved.rel_to_root.as_posix(),
                source=resolved.absolute,
                action="example_op_post",
            )
        ctx.audit.log("example_op", path=str(resolved.absolute), value_len=len(value))
        return {**summarize_resolved(resolved), "snapshot": snap}
```

---

## Adding a New Format Handler

1. Create `src/dokumen_pintar/handlers/<format>_handler.py`.
2. Implement the [`FormatHandler`](src/dokumen_pintar/handlers/base.py) protocol. The class needs:
   - `name: str` - lowercase format identifier.
   - `extensions: tuple[str, ...]` - lowercase extensions including the dot.
   - `capabilities: HandlerCapability` - flag bitmap.
   - `detect(path) -> bool` - by default, suffix match.
   - `read_meta`, `read_text`, `write_text`, `extract_for_search`, `structured_get`, `structured_set`, `structured_delete`. Raise `UnsupportedFormatError` for capabilities you don't claim.
3. At module bottom, register: `_handler: FormatHandler = MyHandler(); default_registry.register(_handler)`.
4. Import the new module in [`context.py`](src/dokumen_pintar/context.py) `build_context` so the registration side-effect runs.
5. Wrap parser exceptions in `HandlerError` with the original exception chained via `from`.
6. Add tests covering each capability, malformed input, encoding edge cases, and round-trip integrity.

| Capability | Meaning |
|:-----------|:--------|
| `READ_TEXT` | Handler can produce a string view of the file via `read_text` |
| `WRITE_TEXT` | Handler accepts `write_text` (use carefully for binary containers) |
| `STRUCTURED_GET` | Handler exposes `structured_get(expr)` with format-specific syntax |
| `STRUCTURED_SET` | Handler exposes `structured_set(expr, value)` |
| `STRUCTURED_DELETE` | Handler exposes `structured_delete(expr)` |
| `SEARCH_EXTRACTED` | `extract_for_search` returns useful plain text for indexing |
| `LIST_ITEMS` | Reserved (for future enumeration tools) |
| `BINARY_ONLY` | File is a binary container; raw text mutation must be refused |
| `WRITE_META` | Handler implements `write_meta` and `strip_meta` |

Use `&` for capability checks: `if HandlerCapability.WRITE_TEXT in handler.capabilities:`.

---

## Testing

We use `pytest` with `pytest-xdist` (parallel) and `pytest-cov` (branch coverage at 100%).

```bash
pytest                              # full suite
pytest -k "test_handler_pdf"        # match by name
pytest tests/test_handlers_pdf.py   # one file
pytest -x --no-header -q            # stop on first fail, quiet
pytest --cov-report=term-missing    # show uncovered lines per file
```

Test layout mirrors source layout. One file per module. Group related cases in classes only when state setup justifies it - prefer flat functions otherwise.

**What to test:**
- Happy path - the obvious thing works.
- Validation - bad input raises the expected error (use `pytest.raises`).
- Sandbox - paths outside roots, sensitive files, read-only roots all rejected.
- Round-trip - write then read returns equivalent data (especially for structured handlers).
- Edge cases - empty file, unicode, CRLF/LF, oversized file, missing parent dir, race conditions you can construct.

**What not to test:**
- Implementation details. Tests should describe behaviour, not internals.
- Things the language already guarantees (typing, Path semantics).

When tests fail in CI but pass locally, the cause is almost always: filesystem ordering (sort glob results), encoding (`open(..., "rb")` vs `"r"`), or hardcoded paths (use `tmp_path`).

---

## Coverage Strategy

- **100%** is the floor, not the ceiling. Coverage missing on a new line means a missing test.
- `# pragma: no cover` is allowed but rare. Each use needs a one-line justification.
- The `[tool.coverage.report]` section in `pyproject.toml` excludes `if TYPE_CHECKING`, `raise NotImplementedError`, `@overload`, and a handful of "always-disabled at runtime" branches. Don't add new exclusions without discussion.
- The `semantic/*` subtree is excluded entirely (`[tool.coverage.run] omit`) because it requires the optional `[semantic]` extras and pulls in heavyweight ML deps. Test it via integration only.

---

## Style

- **`ruff` configured in `pyproject.toml`** - `select = ["E", "F", "W", "I", "B", "UP", "N", "RUF"]`. Auto-fix what you can: `ruff check --fix`.
- **Line length 100**, but `E501` is ignored - readability wins over column count.
- **Imports** sorted by `ruff` (`I`) - stdlib, third-party, local with blank lines between.
- **Type hints required** on every public function. Use `from __future__ import annotations` so forward refs Just Work.
- **No trailing whitespace, LF endings on Unix paths, CRLF preserved on Windows files we read.** The text handler does this for us; if you write a new handler, do the same.
- **Comments explain why, not what.** If the code needs a comment to be readable, the code is the problem.
- **Errors descend from `DokumenPintarError`** so callers can catch the whole family.

---

## Commits & PRs

- **Branch from `main`.** Feature branches should be short-lived.
- **One concern per PR.** A bug fix and a refactor in the same PR is two PRs.
- **Title follows Conventional Commits** style: `fix(versioning): handle CRLF in snapshot diff`. Common prefixes: `feat`, `fix`, `perf`, `refactor`, `docs`, `test`, `build`, `ci`.
- **Description has three sections:**
  - **What** - the change in one paragraph.
  - **Why** - the user-visible problem or improvement.
  - **How** - non-obvious implementation choices.
- **Link the issue.** `Closes #N` or `Refs #N`.
- **Include test output.** Paste the relevant `pytest` snippet showing your new tests pass.

---

## Releasing

Maintainers only. The flow:

1. Bump `version` in [`pyproject.toml`](pyproject.toml) and `__version__` in [`src/dokumen_pintar/__init__.py`](src/dokumen_pintar/__init__.py).
2. Update [`CHANGELOG.md`](CHANGELOG.md) - move the unreleased section to the new version with today's date.
3. `pytest` must be green and coverage at 100%.
4. Tag: `git tag -a v1.x.y -m "v1.x.y"`.
5. The publish workflow under [`.github/`](.github/) handles PyPI upload from the tag.

We follow [Semantic Versioning](https://semver.org/):

- **Patch** (`x.y.Z`) - bug fixes, internal refactors with no user-visible API change.
- **Minor** (`x.Y.0`) - new tools, new optional config fields, new handler formats. Backward-compatible.
- **Major** (`X.0.0`) - removing tools, renaming parameters, changing return shapes. Migration notes required.

---

## AI Agent Notes

If you're an AI assistant working on this codebase, three rules above the others:

- **Read before editing.** Open the file, read the surrounding code, understand the conventions. Don't pattern-match from memory.
- **Run tests after every meaningful change.** `pytest` finishes in ~30s on a modern machine. There's no excuse for skipping it.
- **Stay in scope.** A bug fix is not a refactor. The user asked for one thing - do that thing well, then stop. Open a separate PR for the cleanup.

The handler protocol, snapshot contract, and audit contract are load-bearing. Bypassing them produces code that looks fine and silently breaks user workflows. When in doubt, mirror what an existing handler does.

---

## Getting Help

- **Bugs and feature requests** - [GitHub Issues](https://github.com/firdausmntp/Dokumen-Pintar/issues).
- **Architecture questions** - read [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), then open a discussion if it's still unclear.
- **Configuration confusion** - [docs/CONFIG.md](docs/CONFIG.md) and [docs/profiles/README.md](docs/profiles/README.md).
- **Performance questions** - [docs/BENCHMARK.md](docs/BENCHMARK.md) has the methodology and current baselines.

Welcome aboard. The codebase is small, the tests are honest, and the conventions are explicit. You'll be productive within a day.
