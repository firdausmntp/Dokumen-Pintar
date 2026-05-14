# <svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg> Usage Guide

<a href="../README.md">Home</a> · <a href="TOOLS.md">Tools</a> · <a href="CONFIG.md">Config</a> · <a href="ARCHITECTURE.md">Architecture</a>

This guide covers workspace URI syntax, every tool with a short description and JSON example, and practical recipes for common tasks.

For the full parameter reference, see [TOOLS.md](TOOLS.md). For config options, see [CONFIG.md](CONFIG.md).

<p>
  <svg width="100%" height="2" xmlns="http://www.w3.org/2000/svg" role="presentation"><defs><linearGradient id="du" x1="0" x2="1" y1="0" y2="0"><stop offset="0" stop-color="#1e3a5f" stop-opacity="0"/><stop offset=".5" stop-color="#1e3a5f"/><stop offset="1" stop-color="#1e3a5f" stop-opacity="0"/></linearGradient></defs><rect width="100%" height="2" fill="url(#du)"/></svg>
</p>

## Workspace URI syntax

Every path argument accepts either an absolute path or a **workspace URI**:

```
<root_name>:/relative/path/to/file.txt
```

Examples:

```
documents:/reports/q1.docx
projects:/src/main.py
reference:/specs/api.yaml
```

The root name must match a name defined in `roots` in your config. The relative part is joined to that root's absolute path and validated inside the sandbox.

### Precedence rules

1. If the string matches `<name>:/...` and `name` is a known root, it's treated as a workspace URI.
2. Otherwise the server tries to match the absolute path against all configured roots. The first root whose directory contains the path wins.
3. If no root matches, the request is rejected with a validation error.

Always prefer workspace URIs in agent prompts. They're unambiguous and portable across machines.

---

## Tool quick reference by category

### Workspace

#### `workspace_list_roots`

Call this first in any session to discover what roots are available and whether they're writable.

```json
// input
{}

// output
{
  "roots": [
    { "name": "documents", "path": "C:/Users/me/Documents", "writable": true, "exists": true },
    { "name": "reference", "path": "D:/Reference", "writable": false, "exists": true }
  ],
  "count": 2
}
```

#### `workspace_stat`

Get metadata about any path before reading or writing it.

```json
// input
{ "path": "documents:/reports/q1.docx" }

// output
{
  "uri": "documents:/reports/q1.docx",
  "exists": true,
  "is_file": true,
  "is_dir": false,
  "is_symlink": false,
  "size": 48320,
  "mtime": "2026-04-10T08:22:11+00:00",
  "format": "docx",
  "handler": "docx"
}
```

#### `workspace_tree`

Browse a directory. Use `depth` and `glob` to keep responses small.

```json
// input
{ "path": "documents:/reports", "depth": 2, "glob": "*.docx" }

// output
{
  "root": "documents",
  "path": "C:/Users/me/Documents/reports",
  "tree": [
    { "name": "q1.docx", "type": "file", "rel": "reports/q1.docx", "size": 48320, "format": "docx" },
    { "name": "q2.docx", "type": "file", "rel": "reports/q2.docx", "size": 51200, "format": "docx" }
  ]
}
```

---

### File operations

#### `file_create`

```json
// input
{ "path": "documents:/notes/todo.md", "content": "# Todo\n\n- [ ] First item\n" }

// output
{ "uri": "documents:/notes/todo.md", "created": true, "snapshot": null }
```

#### `file_delete`

```json
// input
{ "path": "documents:/drafts/old.txt" }

// output
{ "uri": "documents:/drafts/old.txt", "deleted": true, "snapshot": { "id": 12, ... } }
```

#### `file_rename`

```json
// input
{ "src": "documents:/notes/todo.md", "dst": "documents:/notes/tasks.md" }

// output
{ "src": { "uri": "documents:/notes/todo.md" }, "dst": { "uri": "documents:/notes/tasks.md" } }
```

#### `file_move`

```json
// input
{ "src": "documents:/drafts/report.docx", "dst": "documents:/reports/report.docx" }
```

#### `file_copy`

```json
// input
{ "src": "reference:/templates/blank.docx", "dst": "documents:/reports/new.docx" }
```

---

### Content operations

#### `content_read`

Read a file's text. Use `start_line`/`end_line` to slice large files.

```json
// input
{ "path": "documents:/notes/tasks.md", "start_line": 1, "end_line": 20 }

// output
{
  "uri": "documents:/notes/tasks.md",
  "encoding": "utf-8",
  "line_count": 45,
  "content": "# Todo\n\n- [ ] First item\n..."
}
```

#### `content_write`

Replace the entire file content. Previous version is snapshotted automatically.

```json
// input
{ "path": "documents:/notes/tasks.md", "content": "# Tasks\n\n- [x] Done\n" }
```

#### `content_append`

```json
// input
{ "path": "documents:/logs/run.log", "content": "\n2026-05-13 session ended" }
```

#### `content_insert`

Insert text at line 5, shifting existing content down.

```json
// input
{ "path": "documents:/notes/tasks.md", "line_number": 5, "content": "- [ ] New item" }
```

#### `content_replace`

```json
// input
{ "path": "documents:/reports/q1.md", "old": "Q1 2025", "new": "Q1 2026", "count": -1 }

// output
{ "replacements": 3, "snapshot": { "id": 14, ... } }
```

#### `content_delete_range`

Delete lines 10 through 15 (inclusive).

```json
// input
{ "path": "documents:/notes/tasks.md", "start_line": 10, "end_line": 15 }
```

#### `content_patch`

Apply a unified diff.

```json
// input
{
  "path": "projects:/src/config.py",
  "unified_diff": "@@ -3,7 +3,7 @@\n HOST = 'localhost'\n-PORT = 8000\n+PORT = 9000\n DEBUG = False\n"
}
```

---

### Structured operations

These tools use format-aware handlers. Expression syntax varies by format.

#### `struct_get`

```json
// JSON: JSONPath
{ "path": "documents:/data/config.json", "expr": "$.database.host" }

// XLSX: cell reference
{ "path": "documents:/data/budget.xlsx", "expr": "cell:Sheet1!B2" }

// DOCX: paragraph by index
{ "path": "documents:/reports/q1.docx", "expr": "paragraph:0" }

// PDF: page text
{ "path": "reference:/specs/manual.pdf", "expr": "page:0" }

// Any format: metadata
{ "path": "documents:/reports/q1.docx", "expr": "metadata" }
```

#### `struct_set`

```json
// input
{ "path": "documents:/data/config.json", "expr": "$.database.port", "value": 5432 }
```

#### `struct_delete`

```json
// input
{ "path": "documents:/data/config.json", "expr": "$.deprecated_key" }
```

#### `struct_meta`

```json
// input
{ "path": "documents:/reports/q1.docx" }

// output
{ "handler": "docx", "meta": { "author": "Alice", "created": "2026-01-15T09:00:00", ... } }
```

---

### Search

#### `search_filename`

```json
// input
{ "glob_pattern": "*.pdf", "root": "reference" }

// output
{
  "glob": "*.pdf",
  "count": 4,
  "matches": [
    { "uri": "reference:/specs/api.pdf", "absolute": "D:/Reference/specs/api.pdf", "size": 204800 }
  ]
}
```

#### `search_content`

```json
// input
{ "query": "budget forecast", "glob": "*.docx", "case_sensitive": false }

// output
{
  "query": "budget forecast",
  "matches": [
    { "uri": "documents:/reports/q1.docx", "line": 14, "snippet": "...the budget forecast for 2026...", "match": "budget forecast" }
  ],
  "truncated": false
}
```

#### `search_in_format`

```json
// input
{ "query": "invoice", "format": "pdf", "root": "documents" }
```

#### `search_semantic` (optional)

Requires `semantic_search.enabled = true` and documents indexed via `semantic_index_path`.

```json
// input
{ "query": "quarterly revenue projections", "top_k": 5 }
```

---

### Batch operations

All batch tools default to `dry_run: true`. Always preview first, then re-run with `dry_run: false`.

#### `batch_rename`

```json
// dry-run first
{ "glob": "*.txt", "pattern": "^report_(\\d+)", "replacement": "rpt_\\1", "dry_run": true }

// apply
{ "glob": "*.txt", "pattern": "^report_(\\d+)", "replacement": "rpt_\\1", "dry_run": false }
```

#### `batch_replace_content`

```json
// dry-run
{ "glob": "**/*.md", "old": "http://", "new": "https://", "dry_run": true }

// apply
{ "glob": "**/*.md", "old": "http://", "new": "https://", "dry_run": false }
```

#### `batch_delete`

```json
// dry-run
{ "glob": "**/*.tmp", "dry_run": true }

// apply
{ "glob": "**/*.tmp", "dry_run": false }
```

---

### Version history

#### `version_list`

```json
// input
{ "path": "documents:/reports/q1.docx" }

// output
{
  "count": 3,
  "versions": [
    { "id": 14, "action": "content_write_post", "timestamp": "2026-05-13T10:00:00Z", ... },
    { "id": 13, "action": "content_write_pre",  "timestamp": "2026-05-13T10:00:00Z", ... },
    { "id": 7,  "action": "create",             "timestamp": "2026-04-10T08:22:00Z", ... }
  ]
}
```

#### `version_diff`

```json
// input
{ "path": "documents:/reports/q1.docx", "version_id": 7 }

// output
{ "diff": "--- version:7\n+++ current\n@@ -1,3 +1,4 @@\n ..." }
```

#### `version_restore`

```json
// input
{ "path": "documents:/reports/q1.docx", "version_id": 7 }
```

#### `version_undo`

One-step undo. No version ID needed.

```json
// input
{ "path": "documents:/reports/q1.docx" }
```

#### `version_purge`

```json
// input
{ "older_than_days": 7 }

// output
{ "removed": 42 }
```

---

### Semantic indexing (optional)

#### `semantic_index_path`

```json
// input
{ "path": "documents:/reports/q1.docx" }

// output
{ "path": "C:/Users/me/Documents/reports/q1.docx", "chunks": 8 }
```

#### `semantic_stats`

```json
// input
{}
```

---

## Recipes

### Edit a DOCX paragraph

1. Find the paragraph index with `struct_get` using `metadata` or `paragraph:0`, `paragraph:1`, etc.
2. Read the target paragraph: `struct_get` with `paragraph:2`.
3. Write the new text: `struct_set` with `paragraph:2` and the new string value.
4. Verify with another `struct_get`.

```json
// step 2
{ "path": "documents:/reports/q1.docx", "expr": "paragraph:2" }

// step 3
{ "path": "documents:/reports/q1.docx", "expr": "paragraph:2", "value": "Updated paragraph text." }
```

---

### Replace text across all .md files (dry-run first)

```json
// 1. preview
{
  "glob": "**/*.md",
  "old": "Dokumen Pintar",
  "new": "Dokumen-Pintar",
  "dry_run": true
}

// 2. check the returned files[] list, then apply
{
  "glob": "**/*.md",
  "old": "Dokumen Pintar",
  "new": "Dokumen-Pintar",
  "dry_run": false
}
```

---

### Search inside PDFs

```json
{
  "query": "payment terms",
  "format": "pdf",
  "root": "reference",
  "case_sensitive": false
}
```

Each match returns the URI, line number within the extracted text, and a 240-character snippet.

---

### Restore an accidental delete

If you deleted a file with `file_delete` or `batch_delete`, the snapshot was taken before deletion. Restore it:

```json
// 1. list history (path may no longer exist on disk, but history is in the index)
{ "path": "documents:/reports/q1.docx" }

// 2. pick the snapshot id from the "delete" action entry, then restore
{ "path": "documents:/reports/q1.docx", "version_id": 12 }
```

The file is recreated at its original path from the snapshot bytes.

---

### Undo the last edit quickly

```json
{ "path": "documents:/notes/tasks.md" }
```

`version_undo` picks the most recent snapshot automatically. No need to look up a version ID.
