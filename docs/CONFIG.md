# <svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/><circle cx="12" cy="12" r="3"/></svg> Configuration Reference

<a href="../README.md">Home</a> · <a href="USAGE.md">Usage</a> · <a href="TOOLS.md">Tools</a> · <a href="ARCHITECTURE.md">Architecture</a>

Dokumen-Pintar loads its configuration from a JSON file validated against a Pydantic model. This page documents every field, its type, default value, and any gotchas worth knowing.

For the environment variable that controls config discovery, see [Environment Variable](#environment-variable) below.

<p>
  <svg width="100%" height="2" xmlns="http://www.w3.org/2000/svg" role="presentation"><defs><linearGradient id="dc" x1="0" x2="1" y1="0" y2="0"><stop offset="0" stop-color="#1e3a5f" stop-opacity="0"/><stop offset=".5" stop-color="#1e3a5f"/><stop offset="1" stop-color="#1e3a5f" stop-opacity="0"/></linearGradient></defs><rect width="100%" height="2" fill="url(#dc)"/></svg>
</p>

## Config file discovery order

When you don't pass `--config` on the CLI, the server searches in this order:

1. Path in `DOKUMEN_PINTAR_CONFIG` environment variable (if set)
2. `dokumen-pintar.config.json` in the current working directory
3. `.dokumen-pintar.json` in the current working directory

The first file found wins. If none exist, the server exits with an error.

---

## Environment variable

### `DOKUMEN_PINTAR_CONFIG`

Set this to an absolute path to point the server at a config file outside the working directory.

```
DOKUMEN_PINTAR_CONFIG=C:\Users\me\configs\work.json
```

Useful when running the server from a launcher (Claude Desktop, IDE extension) that doesn't set the working directory to your project folder.

---

## Top-level fields

### `roots`

**Type:** `array of RootConfig` | **Required** (at least one entry)

Defines the workspace roots the server may access. Root names must be unique and alphanumeric (dashes and underscores allowed). The server refuses to resolve any path that escapes all configured roots.

See [RootConfig](#rootconfig) below.

---

### `exclude_patterns`

**Type:** `array of string` | **Default:**
```json
[
  "**/node_modules/**",
  "**/.git/**",
  "**/.venv/**",
  "**/__pycache__/**",
  "**/.mcpdocs/**"
]
```

Glob patterns (matched against the relative path within a root) that the server skips during tree walks, searches, and batch operations. The `.mcpdocs/**` entry protects the internal version/audit store from being exposed as regular files.

Gotcha: patterns are matched against the relative posix path, not just the filename. Use `**/node_modules/**` rather than `node_modules` to exclude nested occurrences.

---

### `max_file_size_mb`

**Type:** `int` (>= 1) | **Default:** `100`

Files larger than this limit are rejected by `content_read`, `content_write`, `search_content`, and any other tool that reads file bytes. The limit applies per-file, not per-request.

Gotcha: DOCX/XLSX/PPTX are ZIP archives internally. The limit applies to the compressed file size on disk, not the extracted text size.

---

### `default_encoding`

**Type:** `string` | **Default:** `"utf-8"`

Fallback encoding used when writing new files and when `auto_detect_encoding` fails or is disabled.

---

### `auto_detect_encoding`

**Type:** `bool` | **Default:** `true`

When `true`, the server attempts to detect the encoding of text files before reading. Falls back to `default_encoding` if detection is inconclusive.

---

## `versioning`

Controls the copy-on-write snapshot store.

### `versioning.enabled`

**Type:** `bool` | **Default:** `true`

When `false`, no snapshots are taken and all `version_*` tools return empty results. Destructive operations still work but are unrecoverable.

---

### `versioning.storage_mode`

**Type:** `"per_root" | "global" | "flexible"` | **Default:** `"flexible"`

Controls where snapshot files are stored:

| Mode | Behavior |
|------|----------|
| `per_root` | Snapshots go to `<root>/.mcpdocs/versions/` inside each root |
| `global` | All snapshots go to `global_storage_path` |
| `flexible` | Tries `per_root` first; falls back to `global` if the root is read-only |

Gotcha: `per_root` will fail silently for read-only roots unless you switch to `flexible` or `global`.

---

### `versioning.global_storage_path`

**Type:** `string | null` | **Default:** `null`

Absolute path to the shared snapshot directory. Required when `storage_mode` is `"global"`. When `null` and mode is `"flexible"`, the server uses a platform-appropriate user data directory.

---

### `versioning.retention_days`

**Type:** `int` (>= 0) | **Default:** `30`

Snapshots older than this many days are removed by `version_purge`. Set to `0` to disable automatic age-based pruning (manual purge still works).

---

### `versioning.max_versions_per_file`

**Type:** `int` (>= 1) | **Default:** `50`

Maximum number of snapshots kept per file. Oldest entries are pruned when the limit is exceeded.

---

## `audit`

### `audit.enabled`

**Type:** `bool` | **Default:** `true`

When `true`, every mutating tool call is appended to a JSONL audit log.

---

### `audit.log_path`

**Type:** `string | null` | **Default:** `null`

Absolute path to the audit log file. When `null`, the log is written to `.mcpdocs/audit.jsonl` inside the first writable root (or the global storage path if no writable root exists).

---

## `transport`

### `transport.stdio`

**Type:** `bool` | **Default:** `true`

Enable the stdio transport (used by Claude Desktop and most MCP-compatible IDEs). This is the standard transport for local use.

---

### `transport.http.enabled`

**Type:** `bool` | **Default:** `false`

Enable the HTTP/SSE transport. When `true`, the server starts a uvicorn process on `host:port`.

---

### `transport.http.host`

**Type:** `string` | **Default:** `"127.0.0.1"`

Bind address for the HTTP transport. Keep this as `127.0.0.1` unless you intentionally want to expose the server on the network.

---

### `transport.http.port`

**Type:** `int` (1-65535) | **Default:** `7878`

Port for the HTTP transport.

---

### `transport.http.auth_token`

**Type:** `string | null` | **Default:** `null`

Bearer token required on HTTP requests. When `null`, no authentication is enforced. Only relevant when `http.enabled = true`.

Gotcha: leaving this `null` with `host` set to anything other than `127.0.0.1` exposes the server without authentication.

---

## `semantic_search`

Semantic search is disabled by default. Enabling it requires `sentence-transformers` and `torch` to be installed.

### `semantic_search.enabled`

**Type:** `bool` | **Default:** `false`

When `true`, registers three additional tools: `search_semantic`, `semantic_index_path`, and `semantic_stats`.

---

### `semantic_search.model`

**Type:** `string` | **Default:** `"sentence-transformers/all-MiniLM-L6-v2"`

HuggingFace model ID used for embedding. The model is downloaded on first use and cached locally by the `sentence-transformers` library.

---

### `semantic_search.index_path`

**Type:** `string | null` | **Default:** `null`

Path to the SQLite file used as the vector index. When `null`, defaults to a platform user-data directory (`dokumen-pintar/semantic.sqlite`).

---

### `semantic_search.auto_index_globs`

**Type:** `array of string` | **Default:** `["**/*.txt", "**/*.md"]`

Globs for files that are automatically indexed on startup (if auto-indexing is implemented). Currently used as a hint; manual indexing via `semantic_index_path` is always available.

---

### `semantic_search.chunk_size`

**Type:** `int` | **Default:** `512`

Number of tokens per chunk when splitting documents for embedding.

---

### `semantic_search.chunk_overlap`

**Type:** `int` | **Default:** `64`

Token overlap between consecutive chunks. Helps preserve context at chunk boundaries.

---

## `safety`

### `safety.allow_sensitive`

**Type:** `bool` | **Default:** `false`

When `false`, the path guard blocks access to files commonly considered sensitive (e.g. `.env`, credential stores, private keys). Set to `true` only if you intentionally need to read/write such files.

---

### `safety.follow_symlinks`

**Type:** `bool` | **Default:** `false`

When `false`, symlinks are not followed during path resolution. This prevents symlink-based sandbox escapes. Enable only if your workspace legitimately uses symlinks that must be traversed.

---

### `safety.validate_roundtrip_writes`

**Type:** `bool` | **Default:** `true`

When `true`, structured writes (DOCX, XLSX, etc.) verify that the file can be re-read after writing. Adds a small overhead but catches handler bugs early.

---

## Minimal config example

```json
{
  "roots": [
    {
      "name": "docs",
      "path": "C:/Users/me/Documents",
      "writable": true
    }
  ]
}
```

All other fields take their defaults.

---

## Full annotated example

See `dokumen-pintar.config.example.json` in the project root for a complete example with all sections populated.
