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


---

## v1.1.0 workflows

The recipes below cover the new tools shipped in v1.1.0. They assume the same workspace URI conventions as the rest of this guide.

### Diff two documents

`content_diff` works on any two files. Text files diff their raw bytes; DOCX/XLSX/PPTX/PDF diff via the format's extracted text view.

```json
// input
{
  "path_a": "documents:/laporan_v1.docx",
  "path_b": "documents:/laporan_v2.docx",
  "context_lines": 5,
  "ignore_whitespace": false
}

// output
{
  "identical": false,
  "diff": "--- documents:/laporan_v1.docx\n+++ documents:/laporan_v2.docx\n@@ -3,6 +3,7 @@\n ...",
  "stats": { "additions": 12, "deletions": 5, "changes": 17 },
  "format_a": "docx",
  "format_b": "docx"
}
```

For a richer side-by-side or track-changes export, use [`document_compare`](#compare-two-docxs-with-track-changes-output).

---

### Bulk-read metadata across many files

```json
// input
{ "glob": "documents:/papers/*.pdf" }

// output
{
  "count": 12,
  "files": [
    { "uri": "documents:/papers/01.pdf", "format": "pdf", "meta": { "title": "...", "author": "..." } }
  ],
  "skipped": [
    { "uri": "documents:/papers/note.txt", "reason": "no_handler" }
  ]
}
```

Pass `fields=["author", "title"]` to restrict the returned meta dict per file.

---

### Convert DOCX to Markdown

`compose_to_markdown` round-trips DOCX → Markdown via mammoth + html2text. Tables, code blocks, lists, headings, links survive.

```json
// input
{
  "src": "documents:/laporan.docx",
  "dst": "documents:/laporan.md",
  "extract_images": true
}

// output
{
  "src": { "uri": "documents:/laporan.docx", ... },
  "dst": { "uri": "documents:/laporan.md", ... },
  "size": 18432,
  "warnings": []
}
```

When `extract_images=true` (default), embedded images write to `documents:/images/<uuid>.png` and the Markdown references them with relative paths. Set `extract_images=false` to inline images as base64 data URIs.

---

### Compose a DOCX from a template

Use an existing DOCX as a layout shell — its styles, headers, footers, page setup, and any cover content are preserved; the generated body is appended.

```json
// input
{
  "path": "documents:/laporan_baru.docx",
  "template": "templates:/cover_untirta.docx",
  "spec": {
    "blocks": [
      { "type": "heading", "text": "BAB I PENDAHULUAN", "level": 1 },
      { "type": "paragraph", "runs": [{ "text": "Latar belakang penelitian..." }] }
    ]
  }
}
```

The template path is resolved through PathGuard like every other path argument.

---

### Extract a section out of a long DOCX

Pull `BAB IV` (and everything beneath it, until the next `BAB`) into a standalone file:

```json
// input
{
  "src": "documents:/laporan_lengkap.docx",
  "dst": "documents:/bab4_only.docx",
  "heading_pattern": "^BAB IV"
}

// output
{
  "src": { ... },
  "dst": { "uri": "documents:/bab4_only.docx" },
  "elements_copied": 24,
  "snapshot": { ... }
}
```

For a paragraph-index slice instead of a heading match, pass `paragraph_range: [start, end]`. Provide exactly one of `heading_pattern` or `paragraph_range`.

---

### Merge multiple DOCX files

```json
// input
{
  "sources": [
    "documents:/bab1.docx",
    "documents:/bab2.docx",
    "documents:/bab3.docx"
  ],
  "dst": "documents:/laporan_gabungan.docx",
  "preserve_styles": false,
  "page_break_between": true
}
```

The first source becomes the master — its styles, headers, footers, and page setup win. With `preserve_styles=true`, conflicting style IDs from later sources are renamed (`MyStyle` → `MyStyle_1`) instead of being discarded.

---

### Extract embedded images

```json
// 1. discover what's in there
{ "path": "documents:/laporan.docx" }

// →
{
  "format": "docx",
  "count": 4,
  "images": [
    { "index": 0, "internal_name": "word/media/image1.png", "size": 14820, "ext": ".png" },
    ...
  ]
}

// 2. dump them all
{
  "path": "documents:/laporan.docx",
  "dst_dir": "documents:/images_out",
  "naming_pattern": "fig_{index:02d}{ext}"
}
```

Replace one in place (DOCX/PPTX only — PDF is read-only):

```json
{
  "path": "documents:/laporan.docx",
  "index": 0,
  "src": "documents:/new_logo.png"
}
```

The replacement keeps the original `internal_name`, so existing references inside the document continue to point at the new image.

---

### Render a Jinja-style DOCX template

```json
{
  "template": "templates:/kp_uni.docx",
  "dst": "documents:/laporan_firdaus.docx",
  "vars": {
    "judul": "Sistem Monitoring SAP",
    "nama": "Firdaus Satrio Utomo",
    "nim": "3337230039",
    "jurusan": "Teknik Informatika",
    "universitas": "Universitas Sultan Ageng Tirtayasa",
    "tahun": "2026"
  },
  "loops": {
    "entries": [
      { "tanggal": "2 Mei 2026", "kegiatan": "Setup environment" },
      { "tanggal": "3 Mei 2026", "kegiatan": "Implementasi API" }
    ]
  },
  "conditionals": { "show_lampiran": true },
  "inline_images": {
    "logo": { "path": "documents:/logo.png", "width_mm": 30 }
  }
}
```

Template syntax follows [`docxtpl`](https://github.com/elapouya/python-docx-template):

- `{{ variable }}` — substitution
- `{% for x in xs %} ... {% endfor %}` — loop
- `{% if cond %} ... {% endif %}` — conditional
- `{%tr for x in xs %}` / `{%tr endfor %}` — repeat a table row

For repeating cells / table fragments, use the `{% tr %}`, `{% tbl %}`, and `{% cell %}` macros provided by docxtpl.

---

### Use the bundled academic_id template

The wheel ships with `academic_id/kp_basic` — a generic Indonesian KP report skeleton.

```json
// 1. browse the registry
{ "category": "academic_id" }

// →
{
  "count": 1,
  "templates": [
    { "id": "academic_id/kp_basic", "manifest": { "language": "id", "license": "MIT", ... } }
  ]
}

// 2. render directly without copying
{
  "template_id": "academic_id/kp_basic",
  "dst": "documents:/laporan_firdaus.docx",
  "vars": {
    "judul": "Sistem Monitoring SAP",
    "nama": "Firdaus Satrio Utomo",
    "nim": "3337230039",
    "jurusan": "Teknik Informatika",
    "universitas": "Universitas Sultan Ageng Tirtayasa",
    "tahun": "2026"
  }
}

// 3. or copy it for editing first
{
  "template_id": "academic_id/kp_basic",
  "dst": "documents:/templates/my_kp.docx"
}
```

---

### Generate a static table of contents

```json
{
  "path": "documents:/laporan.docx",
  "insert_at": "after:DAFTAR ISI",
  "style": "dotted_leader",
  "max_depth": 3,
  "exclude_patterns": ["DAFTAR ISI", "LAMPIRAN"]
}
```

`insert_at` accepts:
- `paragraph:N` — insert just after the Nth body paragraph
- `after:HEADING_TEXT` — insert just after the first heading whose text contains `HEADING_TEXT`
- omitted — insert at the top of the body

---

### Validate citations against bibliography

```json
// input
{
  "path": "documents:/laporan.docx",
  "style": "APA"
}

// output
{
  "citations_found": [
    { "kind": "author_year", "raw": "(Smith, 2020)", "key": "Smith 2020", "paragraph_index": 65 }
  ],
  "bibliography_entries": [
    { "kind": "author_year", "key": "Smith 2020", "raw": "Smith, J. (2020). ..." }
  ],
  "issues": [
    { "type": "unused_bib_entry", "key": "Jones 2019" },
    { "type": "missing_bib_entry", "citation": "(Doe, 2021)", "key": "Doe 2021" }
  ]
}
```

Sort and reformat the bibliography section in place:

```json
{
  "path": "documents:/laporan.docx",
  "style": "APA",
  "sort": true,
  "auto_fix": true
}
```

---

### Compare two DOCXs with track-changes output

```json
{
  "src_a": "documents:/laporan_v1.docx",
  "src_b": "documents:/laporan_v2.docx",
  "dst": "documents:/comparison.docx",
  "style": "track_changes"
}
```

Three output styles:
- `track_changes` — inline `[+ inserted +]` / `[- deleted -]` markers (default)
- `side_by_side` — two-column table, A on the left, B on the right
- `diff_doc` — colored unified diff

---

### Lint a document

```json
// 1. run with the academic_id_kp preset
{
  "path": "documents:/laporan.docx",
  "rules": "academic_id_kp"
}

// →
{
  "rules_evaluated": [
    "trailing_whitespace", "empty_heading", "duplicate_heading",
    "heading_hierarchy_skip", "title_case_id",
    "required_section_lembar_pengesahan",
    "required_section_kata_pengantar",
    "required_section_daftar_isi",
    "required_section_pendahuluan",
    "required_section_daftar_pustaka",
    "required_section_lampiran",
    "required_section_log_book"
  ],
  "issues": [
    {
      "rule": "trailing_whitespace",
      "severity": "warn",
      "location": { "paragraph": 12 },
      "current": "BAB I ",
      "suggested": "BAB I",
      "auto_fixable": true,
      "message": "Paragraph has trailing whitespace"
    },
    {
      "rule": "required_section_log_book",
      "severity": "error",
      "location": { "section": "LOG BOOK" },
      "auto_fixable": false,
      "message": "Required section not found: 'LOG BOOK'"
    }
  ],
  "summary": { "errors": 1, "warnings": 1, "info": 0, "auto_fixable": 1 }
}

// 2. apply auto-fixes (dry-run first by default)
{
  "path": "documents:/laporan.docx",
  "rules": "academic_id_kp"
}

// 3. confirm and write
{
  "path": "documents:/laporan.docx",
  "rules": "academic_id_kp",
  "dry_run": false
}
```

**Built-in presets:**

| Preset | Use case |
|--------|----------|
| `default` | Generic structure & whitespace checks |
| `academic_id` | Indonesian academic paper standards |
| `academic_id_kp` | Kerja Praktik report rules |
| `academic_id_skripsi` | Undergraduate thesis rules |

You can also pass a list of rule IDs / preset names:

```json
{ "rules": ["default", "title_case_id", "required_section_log_book"] }
```

---

### Indonesian morphological search (Sastrawi)

Stem the query and the document text before matching, so morphological variants collapse:

```json
{
  "query": "mengatakan",
  "language": "id",
  "stem": true
}
```

`mengatakan`, `berkata`, `perkataan`, `kata-kata` all stem to `kata`, so they all match.

Requires the optional `[indonesian]` extra:

```bash
pip install dokumen-pintar[indonesian]
```

Acronyms (≤ 5 uppercase characters, e.g. `SAP`, `KP`) are preserved verbatim during stemming so they survive the round-trip.

---

### Workspace health check

`workspace_diagnose` is read-only and free of side effects. Use it to spot oversized stores or stale caches:

```json
// input
{}

// output
{
  "config": { "max_file_size_mb": 100, "auto_detect_encoding": true, ... },
  "roots": [
    { "name": "documents", "path": "C:/...", "writable": true, "exists": true, "disk_usage_bytes": 248301552 }
  ],
  "snapshot_store": {
    "enabled": true,
    "storage_mode": "flexible",
    "snapshot_count": 142,
    "index_db_size_bytes": 524288
  },
  "audit_log": { "size_bytes": 4096, "entries": 87 },
  "extract_cache": { "enabled": true, "size_bytes": 1048576 },
  "warnings": []
}
```

Warnings appear when:
- Snapshot index DB > 100 MB → consider `version_purge`
- Audit log > 50 MB → consider rotating
- Extract cache > 200 MB → consider `extract_cache.clear()`
- A configured root path doesn't exist on disk

---

### Search content with structural context

`include_context=true` enriches DOCX hits with the heading breadcrumb the match lives under:

```json
// input
{
  "query": "integrasi sistem",
  "glob": "*.docx",
  "include_context": true
}

// output
{
  "matches": [
    {
      "uri": "documents:/laporan.docx",
      "line": 65,
      "snippet": "...integrasi sistem SAP ke aplikasi internal...",
      "match": "integrasi sistem",
      "context": {
        "format": "docx",
        "paragraph_index": 64,
        "heading_path": "BAB II PEMBAHASAN > 2.1 Integrasi"
      }
    }
  ]
}
```

The breadcrumb walks every preceding heading in the document, popping deeper levels off as new top-level sections appear.

---

### Edit a paragraph while preserving formatting

`paragraph_runs:N` reads and writes the paragraph as a list of structured runs. Use it instead of `paragraph:N` when you need to keep bold/italic/underline state intact:

```json
// 1. read
{ "path": "documents:/laporan.docx", "expr": "paragraph_runs:42" }

// →
{
  "index": 42,
  "text": "Sistem ini menggunakan SAP yang terintegrasi.",
  "runs": [
    { "text": "Sistem ini menggunakan ", "bold": false, "italic": false, "underline": false },
    { "text": "SAP", "bold": true, "italic": false, "underline": false },
    { "text": " yang terintegrasi.", "bold": false, "italic": false, "underline": false }
  ]
}

// 2. write replacements as runs
{
  "path": "documents:/laporan.docx",
  "expr": "paragraph_runs:42",
  "value": [
    { "text": "Sistem ini memanfaatkan " },
    { "text": "SAP", "bold": true },
    { "text": " sebagai integrasi utamanya." }
  ]
}
```

---

### Read a single cell from a DOCX table

`table:N!A1` returns one cell. `table:N!row:M` returns a row, `table:N!col:M` a column:

```json
// cell B2
{ "path": "documents:/laporan.docx", "expr": "table:0!B2" }
// → "POST"

// row 1
{ "path": "documents:/laporan.docx", "expr": "table:0!row:1" }
// → ["/api/sap", "POST", "Trigger sync"]

// column 0
{ "path": "documents:/laporan.docx", "expr": "table:0!col:0" }
// → ["Endpoint", "/api/sap", "/api/log"]
```

---

### Scoped find/replace inside a DOCX

Restrict `batch_replace_structured` to a subsection:

```json
{
  "glob": "documents:/laporan.docx",
  "old": "kerjapraktik",
  "new": "Kerja Praktik",
  "scope": {
    "headings_only": true
  }
}
```

DOCX scope keys:
- `headings_only` — touch only paragraphs styled as headings
- `tables_only` — touch only table cells
- `paragraph_range` — `[start, end]` body paragraph slice
- `heading_section` — restrict to paragraphs under a heading whose text matches the regex
- `include_styles` / `exclude_styles` — filter by paragraph style name

XLSX scope keys: `sheets`, `cell_range`. PPTX: `slides`.

---

### Purge old snapshots

```json
// keep only last 7 days
{ "older_than_days": 7 }

// purge ALL snapshots (v1.1.0 behaviour change — was a no-op in 1.0.x)
{ "older_than_days": 0 }

// use the configured retention setting
{ }
```

Negative values are rejected with `ValueError`.

---

## See also

- **[TOOLS.md](TOOLS.md)** — full parameter reference for every tool
- **[CONFIG.md](CONFIG.md)** — configuration options
- **[ARCHITECTURE.md](ARCHITECTURE.md)** — module map and request flow
- **[BENCHMARK.md](BENCHMARK.md)** — performance baselines
- **[profiles/README.md](profiles/README.md)** — six pre-tuned profiles for common scenarios
