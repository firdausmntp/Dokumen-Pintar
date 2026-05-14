<p align="center">
  <img src="assets/icon.svg" width="140" height="140" alt="Dokumen-Pintar logo">
</p>

<h1 align="center">Dokumen-Pintar</h1>

<p align="center"><b>Universal MCP server for cross-format document CRUD</b></p>

<p align="center">
Read, write, search, and manage text, Office, and PDF files<br>
from any AI agent that supports the <a href="https://modelcontextprotocol.io/">Model Context Protocol</a>.
</p>

<p align="center">
  <a href="https://pypi.org/project/dokumen-pintar/"><img alt="PyPI" src="https://img.shields.io/pypi/v/dokumen-pintar?style=for-the-badge&logo=pypi&logoColor=white&labelColor=0b1020&color=1e3a5f"></a>&nbsp;
  <a href="https://python.org"><img alt="Python 3.10+" src="https://img.shields.io/badge/python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white&labelColor=0b1020"></a>&nbsp;
  <a href="LICENSE"><img alt="MIT License" src="https://img.shields.io/badge/license-MIT-1e3a5f?style=for-the-badge&labelColor=0b1020"></a>&nbsp;
  <a href="tests/"><img alt="730 tests passed" src="https://img.shields.io/badge/tests-730%20passed-10b981?style=for-the-badge&logo=pytest&logoColor=white&labelColor=0b1020"></a>&nbsp;
  <a href="htmlcov/"><img alt="100% coverage" src="https://img.shields.io/badge/coverage-100%25-10b981?style=for-the-badge&labelColor=0b1020"></a>
</p>

<p align="center">
  <a href="#features">Features</a>
  <span>&nbsp;&middot;&nbsp;</span>
  <a href="#supported-formats">Formats</a>
  <span>&nbsp;&middot;&nbsp;</span>
  <a href="#quick-start">Quick Start</a>
  <span>&nbsp;&middot;&nbsp;</span>
  <a href="#tools-overview">Tools</a>
  <span>&nbsp;&middot;&nbsp;</span>
  <a href="docs/">Docs</a>
  <span>&nbsp;&middot;&nbsp;</span>
  <a href="#contributing">Contributing</a>
</p>

<p align="center"><b><a href="README.id.md">Baca dalam Bahasa Indonesia</a></b></p>

<p align="center">
  <svg width="100%" height="2" xmlns="http://www.w3.org/2000/svg" role="presentation"><defs><linearGradient id="hd" x1="0" x2="1" y1="0" y2="0"><stop offset="0" stop-color="#1e3a5f" stop-opacity="0"/><stop offset=".5" stop-color="#1e3a5f"/><stop offset="1" stop-color="#1e3a5f" stop-opacity="0"/></linearGradient></defs><rect width="100%" height="2" fill="url(#hd)"/></svg>
</p>

## <svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9.937 15.5A2 2 0 0 0 8.5 14.063l-6.135-1.582a.5.5 0 0 1 0-.962L8.5 9.936A2 2 0 0 0 9.937 8.5l1.582-6.135a.5.5 0 0 1 .963 0L14.063 8.5A2 2 0 0 0 15.5 9.937l6.135 1.581a.5.5 0 0 1 0 .964L15.5 14.063a2 2 0 0 0-1.437 1.437l-1.582 6.135a.5.5 0 0 1-.963 0z"/><path d="M20 3v4"/><path d="M22 5h-4"/><path d="M4 17v2"/><path d="M5 18H3"/></svg> Features

<table>
<tr>
<td width="50%" valign="top">

**Multi-root Sandbox** — Define multiple workspace roots with per-root `writable` control. All paths outside the sandbox are rejected.

**10 Formats** — Plain text, Markdown, JSON, YAML, CSV/TSV, XML/SVG, DOCX, XLSX, PPTX, PDF.

**30 MCP Tools** — File & content CRUD, structured access, batch operations, search, versioning — all exposed as callable tools for AI agents.

**Automatic Versioning** — Copy-on-write snapshots on every write operation. Undo, diff, restore, and purge anytime.

</td>
<td width="50%" valign="top">

**Structured Access** — JSONPath for JSON/YAML, XPath for XML, cell/range/sheet for XLSX, paragraph/table for DOCX, slide for PPTX, page for PDF.

**Batch Operations** — Mass rename, find-and-replace, and delete with dry-run by default.

**Semantic Search** *(optional)* — Vector search powered by sentence-transformers; enable via config.

**Audit Trail** — Every mutation logged to JSONL with timestamp and operation details.

**2 Transports** — stdio (Claude Desktop, Cursor, VS Code, Windsurf) and HTTP/SSE.

</td>
</tr>
</table>

---

## <svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m12.83 2.18a2 2 0 0 0-1.66 0L2.6 6.08a1 1 0 0 0 0 1.83l8.58 3.91a2 2 0 0 0 1.66 0l8.58-3.91a1 1 0 0 0 0-1.83Z"/><path d="m6.08 9.5-3.5 1.6a1 1 0 0 0 0 1.81l8.6 3.91a2 2 0 0 0 1.65 0l8.58-3.9a1 1 0 0 0 0-1.83l-3.5-1.59"/><path d="m6.08 14.5-3.5 1.6a1 1 0 0 0 0 1.81l8.6 3.91a2 2 0 0 0 1.65 0l8.58-3.9a1 1 0 0 0 0-1.83l-3.5-1.59"/></svg> Supported Formats

| Format | Read | Write | Structured Query | Search |
|:-------|:----:|:-----:|:-----------------|:------:|
| **Plain text / Markdown** | <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg> | <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg> | — | <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg> |
| **JSON** | <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg> | <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg> | JSONPath `$.key` | <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg> |
| **YAML** | <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg> | <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg> | JSONPath `$.key` | <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg> |
| **CSV / TSV** | <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg> | <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg> | `row:N` · `col:N` · `cell:R,C` | <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg> |
| **XML / SVG** | <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg> | <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg> | XPath `//node` | <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg> |
| **DOCX** | <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg> | <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg> | `paragraph:N` · `table:N` | <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg> |
| **XLSX** | <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg> | <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg> | `cell:Sheet!A1` · `range:` · `sheet:` | <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg> |
| **PPTX** | <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg> | <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg> | `slide:N` · `slide_title:N` | <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg> |
| **PDF** | <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg> | <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#6b7280" stroke-width="3" stroke-linecap="round"><line x1="5" y1="12" x2="19" y2="12"/></svg> | `page:N` · `outline` · `metadata` | <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg> |

---

## <svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09z"/><path d="M12 15l-3-3a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 0 1-4 2z"/><path d="M9 12H4s.55-3.03 2-4c1.62-1.08 5 0 5 0"/><path d="M12 15v5s3.03-.55 4-2c1.08-1.62 0-5 0-5"/></svg> Quick Start

### 1. Install

```bash
pip install dokumen-pintar
```

<details>
<summary><b>From source (development)</b></summary>

```bash
git clone https://github.com/firdausmntp/Dokumen-Pintar.git
cd Dokumen-Pintar
pip install -e ".[dev]"
```

</details>

<details>
<summary><b>With semantic search</b></summary>

```bash
pip install dokumen-pintar[semantic]
```

</details>

### 2. Create a Config

```bash
dokumen-pintar-init
```

Or create one manually:

```jsonc
{
  "roots": [
    { "name": "documents", "path": "~/Documents", "writable": true },
    { "name": "projects",  "path": "~/Projects",  "writable": true }
  ]
}
```

> All other fields are optional with sensible defaults. See **[docs/CONFIG.md](docs/CONFIG.md)**.

### 3. Run

```bash
dokumen-pintar --config dokumen-pintar.config.json
```

### 4. Connect to an AI Client

<details>
<summary><b>Claude Desktop</b></summary>

Add to your `claude_desktop_config.json`:

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

</details>

<details>
<summary><b>Cursor / VS Code / Windsurf</b></summary>

Use the same stdio transport. Point your IDE's MCP settings to the `dokumen-pintar` command and config path.

</details>

<details>
<summary><b>HTTP/SSE (remote or multi-client)</b></summary>

```jsonc
{
  "transport": {
    "stdio": false,
    "http": { "enabled": true, "port": 7878 }
  }
}
```

Start the server and connect your client to `http://127.0.0.1:7878`.

</details>

---

## <svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 14c.2-1 .7-1.7 1.5-2.5 1-.9 1.5-2.2 1.5-3.5A6 6 0 0 0 6 8c0 1 .2 2.2 1.5 3.5.7.7 1.3 1.5 1.5 2.5"/><path d="M9 18h6"/><path d="M10 22h4"/></svg> Usage Examples

```python
# List available workspace roots
workspace_list_roots()

# Read a Word document
content_read(path="documents:/reports/q1.docx")

# Create a new file
file_create(path="documents:/notes/todo.txt", content="Hello World")

# Find & replace inside a file
content_replace(path="documents:/notes/todo.txt", old="World", new="Everyone")

# Full-text search across all PDFs
search_content(query="budget 2024", format="pdf")

# Read an Excel cell
structured_get(path="documents:/data.xlsx", expr="cell:Sheet1!B2")

# Update a JSON key
structured_set(path="documents:/config.json", expr="$.database.port", value=5432)

# Delete an XML node
structured_delete(path="documents:/data.xml", expr="//item[@id='old']")

# Batch rename (dry-run first)
batch_rename(glob="*.txt", pattern="draft_", replacement="final_", dry_run=true)

# Undo last change
version_undo(path="documents:/reports/q1.docx")
```

> Full guide with recipes: **[docs/USAGE.md](docs/USAGE.md)**

---

## <svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/></svg> Tools Overview

**30 MCP tools** organized by category:

| Category | Tools |
|:---------|:------|
| **Workspace** | `workspace_list_roots` · `workspace_stat` · `workspace_tree` |
| **File CRUD** | `file_create` · `file_delete` · `file_rename` · `file_copy` · `file_move` |
| **Content** | `content_read` · `content_write` · `content_append` · `content_insert` · `content_replace` · `content_patch` |
| **Structured** | `structured_get` · `structured_set` · `structured_delete` · `structured_meta` |
| **Batch** | `batch_rename` · `batch_replace_content` · `batch_delete` |
| **Search** | `search_filename` · `search_content` · `search_in_format` |
| **Versioning** | `version_list` · `version_diff` · `version_restore` · `version_undo` · `version_purge` |
| **Semantic** * | `semantic_index` · `semantic_search` |

<sub>* Only available when <code>semantic_search.enabled = true</code> and <code>[semantic]</code> extras are installed.</sub>

> Full parameter reference: **[docs/TOOLS.md](docs/TOOLS.md)**

---

## <svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="16" y="16" width="6" height="6" rx="1"/><rect x="2" y="16" width="6" height="6" rx="1"/><rect x="9" y="2" width="6" height="6" rx="1"/><path d="M5 16v-3a1 1 0 0 1 1-1h12a1 1 0 0 1 1 1v3"/><path d="M12 12V8"/></svg> Architecture

```mermaid
flowchart TD
    Client["AI Client\n(Claude, Cursor, VS Code, ...)"]
    Client -->|"MCP protocol\n(stdio or HTTP/SSE)"| Server

    subgraph Server["dokumen-pintar server"]
        PG["PathGuard\nsandboxed multi-root"]
        H["Handlers\n9 format parsers"]
        V["Versions\ncopy-on-write snapshots"]
        A["AuditLog\nJSONL mutation log"]
        S["Search\nfilename + content"]
        SE["Semantic\nvector index (optional)"]
    end

    Server --> FS["Filesystem\n(sandboxed workspace roots)"]
```

> Full details: **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)**

---

## <svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14.5 2v17.5c0 1.4-1.1 2.5-2.5 2.5c-1.4 0-2.5-1.1-2.5-2.5V2"/><path d="M8.5 2h7"/><path d="M14.5 16h-5"/></svg> Testing

```bash
pip install -e ".[dev]"
pytest
```

<table align="center">
<tr>
  <td align="center" width="25%">
    <h2>730</h2>
    <sub>Tests passed</sub>
  </td>
  <td align="center" width="25%">
    <h2>100%</h2>
    <sub>Line + branch coverage</sub>
  </td>
  <td align="center" width="25%">
    <h2>80%</h2>
    <sub>Minimum threshold</sub>
  </td>
  <td align="center" width="25%">
    <h2>-n auto</h2>
    <sub>Parallel via xdist</sub>
  </td>
</tr>
</table>

HTML coverage report: `htmlcov/index.html`

---

## <svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1 0-5H20"/></svg> Documentation

| Document | Contents |
|:---------|:---------|
| **[USAGE.md](docs/USAGE.md)** | Workspace URIs, tool examples, practical recipes |
| **[CONFIG.md](docs/CONFIG.md)** | All config fields with types, defaults, and notes |
| **[TOOLS.md](docs/TOOLS.md)** | Full reference for all 30 tools |
| **[ARCHITECTURE.md](docs/ARCHITECTURE.md)** | Module map, request flow, versioning, safety |

---

## <svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4.05 3 5.5l7 7Z"/></svg> Contributing

```bash
git clone https://github.com/firdausmntp/Dokumen-Pintar.git
cd Dokumen-Pintar
pip install -e ".[dev]"

ruff check src/             # lint
mypy src/dokumen_pintar/    # type check
pytest                      # test + coverage
```

PRs welcome. All tests must pass and coverage must not decrease.

---

## <svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/></svg> License

[MIT](LICENSE) — 2026 [firdausmntp](https://github.com/firdausmntp/Dokumen-Pintar)

<p align="center">
  <svg width="100%" height="2" xmlns="http://www.w3.org/2000/svg" role="presentation"><defs><linearGradient id="fd" x1="0" x2="1" y1="0" y2="0"><stop offset="0" stop-color="#1e3a5f" stop-opacity="0"/><stop offset=".5" stop-color="#1e3a5f"/><stop offset="1" stop-color="#1e3a5f" stop-opacity="0"/></linearGradient></defs><rect width="100%" height="2" fill="url(#fd)"/></svg>
</p>

<p align="center">
  <sub>Built by <a href="https://github.com/firdausmntp">firdausmntp</a></sub>
</p>
