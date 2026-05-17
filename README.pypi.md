# Dokumen-Pintar

**Universal MCP server for cross-format document CRUD, lint, and template authoring**

Read, write, search, lint, and author text, Office, and PDF files
from any AI agent that supports the [Model Context Protocol](https://modelcontextprotocol.io/).

[![PyPI](https://img.shields.io/pypi/v/dokumen-pintar)](https://pypi.org/project/dokumen-pintar/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![License: MIT](https://img.shields.io/badge/license-MIT-1e3a5f)](LICENSE)
[![Tests: 1403 passed](https://img.shields.io/badge/tests-1403%20passed-10b981?logo=pytest&logoColor=white)](tests/)
[![Coverage: 100%](https://img.shields.io/badge/coverage-100%25-10b981)](htmlcov/)

---

## Features

- **Multi-root Sandbox** — Define multiple workspace roots with per-root `writable` control. All paths outside the sandbox are rejected.
- **10 Formats** — Plain text, Markdown, LaTeX, JSON / YAML, CSV / TSV, XML / SVG, DOCX, XLSX, PPTX, PDF, plus image EXIF.
- **62 MCP Tools** — File & content CRUD, structured access, batch operations, search, versioning, metadata, authoring, image extraction, sections, templates, TOC, bibliography, document compare, lint — all exposed as callable tools.
- **Automatic Versioning** — Copy-on-write snapshots on every write operation. Undo, diff, restore, and purge anytime.
- **Structured Access** — JSONPath for JSON / YAML (incl. list indices), XPath for XML, cell / range / sheet for XLSX, paragraph / paragraph_runs / table cells for DOCX, slide for PPTX, page for PDF.
- **Authoring** — Generate DOCX or PDF from a JSON spec or Markdown, render Jinja2-style DOCX templates, convert DOCX → Markdown.
- **Document Lint** — Pluggable rule registry with built-in presets (`default`, `academic_id`, `academic_id_kp`, `academic_id_skripsi`) for Indonesian academic documents.
- **Indonesian Stemming** *(optional)* — Sastrawi-based morphological matching so `mengatakan`, `berkata`, `perkataan` collapse during search.
- **Semantic Search** *(optional)* — Vector search powered by sentence-transformers; enable via config.
- **Audit Trail** — Every mutation logged to JSONL with timestamp and operation details.
- **2 Transports** — stdio (Claude Desktop, Cursor, VS Code, Windsurf) and HTTP / SSE.

---

## Supported Formats

| Format | Read | Write | Structured Query | Search |
|:-------|:----:|:-----:|:-----------------|:------:|
| Plain text / Markdown / LaTeX | Y | Y | - | Y |
| JSON / JSONC / JSON5 | Y | Y | JSONPath `$.key`, `$.array[N]` | Y |
| YAML | Y | Y | JSONPath `$.key` | Y |
| CSV / TSV | Y | Y | `row:N` `col:NAME` `cell:row:N,col:NAME` | Y |
| XML / SVG | Y | Y | XPath `//node` | Y |
| DOCX | Y | Y | `paragraph:N` `paragraph_runs:N` `table:N!A1` | Y |
| XLSX | Y | Y | `cell:Sheet!A1` `range:` `sheet:` | Y |
| PPTX | Y | Y | `slide:N` `slide_title:N` | Y |
| PDF | Y | - | `page:N` `outline` `metadata` | Y |
| Images (JPG / PNG / TIFF / WEBP) | Y | Y meta | EXIF tags | - |

---

## Quick Start

### 1. Install

```bash
pip install dokumen-pintar
```

With Indonesian stemming:

```bash
pip install dokumen-pintar[indonesian]
```

With semantic search:

```bash
pip install dokumen-pintar[semantic]
```

### 2. Create a Config

```bash
dokumen-pintar-init
```

Or create one manually:

```json
{
  "roots": [
    { "name": "documents", "path": "~/Documents", "writable": true },
    { "name": "projects",  "path": "~/Projects",  "writable": true }
  ]
}
```

Six pre-tuned profiles ship in `docs/profiles/` — copy `personal.json` for daily desktop use, `research.json` for thesis libraries, or `team-server.json` for HTTP deployment.

### 3. Run

```bash
dokumen-pintar --config dokumen-pintar.config.json
```

### 4. Connect to an AI Client

**Claude Desktop** — Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "dokumen-pintar": {
      "command": "dokumen-pintar",
      "args": ["--config", "/path/to/dokumen-pintar.config.json"]
    }
  }
}
```

**Cursor / VS Code / Windsurf** — Use the same stdio transport. Point your IDE's MCP settings to the `dokumen-pintar` command and config path.

---

## Tools Overview

**62 MCP tools** organised by category:

| Category | Tools |
|:---------|:------|
| Workspace | `workspace_list_roots` · `workspace_stat` · `workspace_tree` · `workspace_diagnose` |
| File CRUD | `file_create` · `file_delete` · `file_rename` · `file_copy` · `file_move` |
| Content | `content_read` · `content_write` · `content_append` · `content_insert` · `content_replace` · `content_delete_range` · `content_patch` · `content_diff` |
| Structured | `struct_get` · `struct_set` · `struct_delete` · `struct_meta` |
| Metadata | `metadata_read` · `metadata_write` · `metadata_delete` · `metadata_strip` · `metadata_read_batch` |
| Authoring | `validate_spec` · `compose_docx` · `compose_pdf` · `compose_from_markdown` · `compose_to_markdown` |
| Sections | `section_extract` · `section_merge` |
| Images | `image_list` · `image_extract` · `image_extract_all` · `image_replace` |
| Templates | `template_list` · `template_install` · `template_render` · `template_render_named` |
| TOC & Bibliography | `toc_generate` · `bibliography_check` · `bibliography_format` |
| Compare & Lint | `document_compare` · `document_lint` · `document_lint_fix` |
| Batch | `batch_rename` · `batch_replace_content` · `batch_replace_structured` · `batch_delete` |
| Search | `search_filename` · `search_content` · `search_in_format` |
| Versioning | `version_list` · `version_diff` · `version_restore` · `version_undo` · `version_purge` |
| Semantic\* | `search_semantic` · `semantic_index_path` · `semantic_stats` |

\*Only registered when `semantic_search.enabled = true` and `[semantic]` extras are installed.

### Bundled templates

- `academic_id/kp_basic` — generic Indonesian Kerja Praktik report skeleton (cover, lembar pengesahan, kata pengantar, BAB I/II, log book, daftar pustaka).

---

## Documentation

Full docs on GitHub: [github.com/firdausmntp/Dokumen-Pintar](https://github.com/firdausmntp/Dokumen-Pintar)

- **USAGE.md** — Workspace URIs, every tool with JSON examples, recipes
- **CONFIG.md** — All config fields with types, defaults, and notes
- **TOOLS.md** — Full reference for all 62 tools
- **ARCHITECTURE.md** — Module map, request flow, versioning, safety
- **BENCHMARK.md** — Performance baselines and methodology
- **profiles/** — Six pre-tuned config presets
- **AGENTS.md** — Contributor guide

---

## License

[MIT](https://github.com/firdausmntp/Dokumen-Pintar/blob/main/LICENSE) — 2026 [firdausmntp](https://github.com/firdausmntp)
