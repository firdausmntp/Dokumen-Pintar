# <svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/></svg> Tool Reference

<a href="../README.md">Home</a> · <a href="USAGE.md">Usage</a> · <a href="CONFIG.md">Config</a> · <a href="ARCHITECTURE.md">Architecture</a>

All 30 tools exposed by Dokumen-Pintar, listed alphabetically. Tools marked with `*` are only registered when `semantic_search.enabled = true` in config.

For usage examples and recipes, see [USAGE.md](USAGE.md).

<p>
  <svg width="100%" height="2" xmlns="http://www.w3.org/2000/svg" role="presentation"><defs><linearGradient id="dt" x1="0" x2="1" y1="0" y2="0"><stop offset="0" stop-color="#1e3a5f" stop-opacity="0"/><stop offset=".5" stop-color="#1e3a5f"/><stop offset="1" stop-color="#1e3a5f" stop-opacity="0"/></linearGradient></defs><rect width="100%" height="2" fill="url(#dt)"/></svg>
</p>

## batch_delete

**Module:** `tools/batch.py`

Delete every file matching `glob` across all writable roots. Snapshots each file before deletion. Defaults to dry-run.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `glob` | `str` | required | Glob pattern matched against relative path and filename |
| `dry_run` | `bool` | `true` | Preview without deleting; set `false` to apply |

Returns `{ dry_run, count, files[] }` where each entry has `uri`, `absolute`, `size`.

---

## batch_rename

**Module:** `tools/batch.py`

Rename files matching `glob` by applying a regex substitution to the filename. Dry-run by default.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `glob` | `str` | required | Glob to select files |
| `pattern` | `str` | required | Python regex pattern matched against the filename |
| `replacement` | `str` | required | Replacement string (supports backreferences) |
| `dry_run` | `bool` | `true` | Preview plan without renaming |

Returns `{ dry_run, count, plan[] }` (dry-run) or `{ dry_run, count, applied[] }`.

---

## batch_replace_content

**Module:** `tools/batch.py`

Find/replace text inside every text-like file matching `glob`. Snapshots each modified file. Dry-run by default.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `glob` | `str` | required | Glob to select files |
| `old` | `str` | required | Text or regex pattern to find |
| `new` | `str` | required | Replacement text |
| `regex` | `bool` | `false` | Treat `old` as Python regex |
| `dry_run` | `bool` | `true` | Preview without writing |
| `case_sensitive` | `bool` | `true` | Case-sensitive matching |

Returns `{ dry_run, count, files[] }` with replacement counts per file.

---

## content_append

**Module:** `tools/content_crud.py`

Append text to the end of a text-like file. Snapshots before writing.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | `str` | required | Workspace URI or absolute path |
| `content` | `str` | required | Text to append |

Returns `{ snapshot, new_size, ... }`.

---

## content_delete_range

**Module:** `tools/content_crud.py`

Delete a range of lines (1-based, inclusive) from a text-like file. Snapshots before writing.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | `str` | required | Workspace URI or absolute path |
| `start_line` | `int` | required | First line to delete (1-based) |
| `end_line` | `int` | required | Last line to delete (1-based, inclusive) |

Returns `{ snapshot, ... }`.

---

## content_insert

**Module:** `tools/content_crud.py`

Insert text at a specific line number (1-based). Existing content from that line shifts down. Snapshots before writing.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | `str` | required | Workspace URI or absolute path |
| `line_number` | `int` | required | Line to insert at (1-based) |
| `content` | `str` | required | Text to insert; newline appended if missing |

Returns `{ snapshot, ... }`.

---

## content_patch

**Module:** `tools/content_crud.py`

Apply a unified diff to a file. Headers (`---`, `+++`) are tolerated and ignored. Snapshots before writing.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | `str` | required | Workspace URI or absolute path |
| `unified_diff` | `str` | required | Unified diff string |

Returns `{ snapshot, ... }`.

---

## content_read

**Module:** `tools/content_crud.py`

Read the textual content of a file. DOCX, PDF, and XLSX delegate to their handler's `read_text` view. Optional line slicing keeps responses small.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | `str` | required | Workspace URI or absolute path |
| `start_line` | `int\|null` | `null` | First line to return (1-based) |
| `end_line` | `int\|null` | `null` | Last line to return (1-based, inclusive) |
| `encoding` | `str\|null` | `null` | Override encoding hint |

Returns `{ content, encoding, line_count, ... }`.

---

## content_replace

**Module:** `tools/content_crud.py`

Find/replace within a single file. Supports plain text or Python regex. Snapshots before writing.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | `str` | required | Workspace URI or absolute path |
| `old` | `str` | required | Text or regex to find |
| `new` | `str` | required | Replacement text |
| `count` | `int` | `-1` | Max replacements; `-1` means all |
| `regex` | `bool` | `false` | Treat `old` as Python regex |

Returns `{ replacements, snapshot, ... }`.

---

## content_write

**Module:** `tools/content_crud.py`

Replace the entire content of a file. Snapshots the previous version first. For text-like formats; DOCX/PDF delegate to their handler's `write_text`.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | `str` | required | Workspace URI or absolute path |
| `content` | `str` | required | New full content |
| `encoding` | `str` | `"utf-8"` | Target encoding |

Returns `{ snapshot, ... }`.

---

## file_copy

**Module:** `tools/file_crud.py`

Copy a file or directory to a new path within the workspace.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `src` | `str` | required | Source path |
| `dst` | `str` | required | Destination path |
| `overwrite` | `bool` | `false` | Replace destination if it exists |

Returns `{ src, dst }` summaries.

---

## file_create

**Module:** `tools/file_crud.py`

Create a new file with optional initial content. Snapshots before overwriting an existing file.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | `str` | required | Workspace URI or absolute path |
| `content` | `str` | `""` | Initial file content |
| `overwrite` | `bool` | `false` | Replace if file already exists |

Returns `{ created, snapshot, ... }`.

---

## file_delete

**Module:** `tools/file_crud.py`

Delete a file or directory. Snapshots the file before deletion. Requires `recursive=true` for directories.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | `str` | required | Workspace URI or absolute path |
| `recursive` | `bool` | `false` | Required to delete a directory |

Returns `{ deleted, snapshot, ... }`.

---

## file_move

**Module:** `tools/file_crud.py`

Move a file or directory across paths or roots within the workspace. Snapshots before moving.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `src` | `str` | required | Source path |
| `dst` | `str` | required | Destination path |
| `overwrite` | `bool` | `false` | Replace destination if it exists |

Returns `{ src, dst }` summaries.

---

## file_rename

**Module:** `tools/file_crud.py`

Rename a file or directory within the same parent directory. Snapshots before renaming.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `src` | `str` | required | Current path |
| `dst` | `str` | required | New path (must share same parent) |

Returns `{ src, dst }` summaries.

---

## search_content

**Module:** `tools/search.py`

Plain-text content search across the workspace. Files are read via their handler's `extract_for_search`, so DOCX, PDF, XLSX, etc. are all searchable.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `query` | `str` | required | Search string or regex |
| `glob` | `str\|null` | `null` | Filter by filename glob |
| `root` | `str\|null` | `null` | Restrict to a named root |
| `regex` | `bool` | `false` | Treat `query` as Python regex |
| `case_sensitive` | `bool` | `false` | Case-sensitive matching |
| `max_results` | `int` | `200` | Max match entries returned |
| `max_files` | `int` | `5000` | Max files scanned |

Returns `{ query, matches[], truncated }`. Each match has `uri`, `line`, `snippet`, `match`.

---

## search_filename

**Module:** `tools/search.py`

Search files by filename glob across the workspace or a specific root.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `glob_pattern` | `str` | required | Glob matched against filename |
| `root` | `str\|null` | `null` | Restrict to a named root |
| `limit` | `int` | `200` | Max results |

Returns `{ glob, count, matches[] }`. Each match has `uri`, `absolute`, `size`.

---

## search_in_format

**Module:** `tools/search.py`

Search inside files of a specific format only (e.g. only PDFs, only DOCX). Useful when you want to avoid scanning unrelated file types.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `query` | `str` | required | Search string or regex |
| `format` | `str` | required | Format name: `pdf`, `docx`, `xlsx`, `pptx`, `csv`, `xml`, `json`, `yaml`, `text` |
| `glob` | `str\|null` | `null` | Additional filename filter |
| `root` | `str\|null` | `null` | Restrict to a named root |
| `regex` | `bool` | `false` | Treat `query` as Python regex |
| `case_sensitive` | `bool` | `false` | Case-sensitive matching |
| `max_results` | `int` | `200` | Max match entries returned |

Returns `{ matches[], truncated }`.

---

## search_semantic *

**Module:** `tools/search.py` (requires `semantic_search.enabled = true`)

Semantic vector search using sentence-transformers. Documents must be indexed first via `semantic_index_path`.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `query` | `str` | required | Natural language query |
| `top_k` | `int` | `10` | Number of results to return |

Returns `{ query, hits[] }`.

---

## semantic_index_path *

**Module:** `tools/search.py` (requires `semantic_search.enabled = true`)

Index a single file's extracted text into the semantic store.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | `str` | required | Workspace URI or absolute path |

Returns `{ path, chunks }`.

---

## semantic_stats *

**Module:** `tools/search.py` (requires `semantic_search.enabled = true`)

Return statistics for the semantic index (chunk count, document count).

No parameters.

Returns `{ ... }` (stats dict from the index).

---

## struct_delete

**Module:** `tools/structured.py`

Format-aware delete of a structural element (paragraph, row, sheet, slide, JSON key, XML attribute). Snapshots before mutating.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | `str` | required | Workspace URI or absolute path |
| `expr` | `str` | required | Format-specific selector (see `struct_get`) |

Returns `{ snapshot, ... }`.

---

## struct_get

**Module:** `tools/structured.py`

Format-aware read using the file's handler. Expression syntax depends on format:

- JSON / YAML: JSONPath (e.g. `$.store.book[0].title`)
- XML: XPath (e.g. `//item/@id`)
- XLSX: `cell:Sheet1!A1`
- DOCX: `paragraph:3`
- PPTX: `slide:0`
- PDF: `page:0`
- Any: `metadata`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | `str` | required | Workspace URI or absolute path |
| `expr` | `str` | required | Format-specific selector |

Returns `{ handler, expr, result, ... }`.

---

## struct_meta

**Module:** `tools/structured.py`

Read format-aware metadata for a file (delegates to `handler.read_meta`).

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | `str` | required | Workspace URI or absolute path |

Returns `{ handler, meta, ... }`.

---

## struct_set

**Module:** `tools/structured.py`

Format-aware write to a structural element. Snapshots before mutating. See `struct_get` for expression syntax per format.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | `str` | required | Workspace URI or absolute path |
| `expr` | `str` | required | Format-specific selector |
| `value` | `any` | required | New value to write |

Returns `{ snapshot, ... }`.

---

## version_diff

**Module:** `tools/version.py`

Compute a unified diff between the current file and a specific snapshot. Text formats return a diff string; binary formats return a size/sha summary.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | `str` | required | Workspace URI or absolute path |
| `version_id` | `int` | required | Snapshot ID from `version_list` |

Returns `{ version, diff, ... }` or `{ version, binary: true, ... }`.

---

## version_list

**Module:** `tools/version.py`

List the snapshot history for a file, newest first.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | `str` | required | Workspace URI or absolute path |

Returns `{ count, versions[], ... }`.

---

## version_purge

**Module:** `tools/version.py`

Delete snapshots older than `older_than_days`. Defaults to the configured `retention_days` if not specified.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `older_than_days` | `int\|null` | `null` | Age threshold; `null` uses config default |

Returns `{ removed }`.

---

## version_restore

**Module:** `tools/version.py`

Replace the current file with the contents of a specific snapshot. Snapshots the current state first.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | `str` | required | Workspace URI or absolute path |
| `version_id` | `int` | required | Snapshot ID from `version_list` |

Returns `{ restored_from, ... }`.

---

## version_undo

**Module:** `tools/version.py`

Revert the file to its most recent snapshot (one step back). If the head snapshot matches the current state, reverts to the second-most-recent.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | `str` | required | Workspace URI or absolute path |

Returns `{ restored_from, ... }`.

---

## workspace_list_roots

**Module:** `tools/workspace.py`

List every configured workspace root with its absolute path and writable flag. Call this first to discover what the agent may access.

No parameters.

Returns `{ roots[], count }`. Each root has `name`, `path`, `writable`, `exists`.

---

## workspace_stat

**Module:** `tools/workspace.py`

Return rich metadata about a path: existence, type, size, mtime, detected format, and workspace URI.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | `str` | required | Workspace URI or absolute path |

Returns `{ exists, is_dir, is_file, is_symlink, size, mtime, format, handler, uri, ... }`.

---

## workspace_tree

**Module:** `tools/workspace.py`

Recursive directory listing. Respects `exclude_patterns` from config. Hidden files (dot-prefixed) are skipped unless `include_hidden=true`.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | `str` | required | Workspace URI or absolute path to a directory |
| `depth` | `int` | `3` | Max recursion depth; `-1` for unlimited |
| `glob` | `str\|null` | `null` | Filter files by filename glob |
| `include_hidden` | `bool` | `false` | Include dot-prefixed files/dirs |

Returns `{ root, path, tree[] }`. Each node has `name`, `type`, `rel`, and optionally `children` (dirs) or `size`, `format` (files).
