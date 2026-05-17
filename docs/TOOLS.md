# <svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/></svg> Tool Reference

<a href="../README.md">Home</a> · <a href="USAGE.md">Usage</a> · <a href="CONFIG.md">Config</a> · <a href="ARCHITECTURE.md">Architecture</a>

All **62 tools** exposed by Dokumen-Pintar v1.1.0, organised by category. Tools marked with `*` are only registered when `semantic_search.enabled = true`.

For usage examples and recipes, see [USAGE.md](USAGE.md).

<p>
  <svg width="100%" height="2" xmlns="http://www.w3.org/2000/svg" role="presentation"><defs><linearGradient id="dt" x1="0" x2="1" y1="0" y2="0"><stop offset="0" stop-color="#1e3a5f" stop-opacity="0"/><stop offset=".5" stop-color="#1e3a5f"/><stop offset="1" stop-color="#1e3a5f" stop-opacity="0"/></linearGradient></defs><rect width="100%" height="2" fill="url(#dt)"/></svg>
</p>

## Table of contents

- [Workspace](#workspace) (4)
- [File CRUD](#file-crud) (5)
- [Content](#content) (8)
- [Structured access](#structured-access) (4)
- [Metadata](#metadata) (5)
- [Authoring](#authoring) (5)
- [Sections](#sections) (2)
- [Images](#images) (4)
- [Templates](#templates) (4)
- [TOC & Bibliography](#toc--bibliography) (3)
- [Compare & Lint](#compare--lint) (3)
- [Batch operations](#batch-operations) (4)
- [Search](#search) (3)
- [Versioning](#versioning) (5)
- [Semantic *](#semantic) (3)

🆕 marks v1.1.0 additions or behaviour changes.

---

## Workspace

### `workspace_list_roots`

List every configured workspace root with name, absolute path, and writable flag. Use this first to discover what the agent may touch.

Returns `{ roots: [{ name, path, writable }] }`.

### `workspace_stat`

Rich metadata about a path: existence, type, size, mtime, detected format, workspace URI.

### `workspace_tree`

Recursive directory listing with optional filename glob filter and depth limit.

### `workspace_diagnose` 🆕

Read-only health check across config, snapshot store, audit log, extract cache, semantic index, and per-root disk usage. Surfaces warnings for oversized stores, missing roots, stale caches.

Returns `{ config, roots[], snapshot_store, audit_log, extract_cache, semantic_search, warnings[] }`.

---

## File CRUD

| Tool | Description |
|------|-------------|
| `file_create` | Create a new file. `overwrite=true` snapshots and replaces. |
| `file_delete` | Delete a file or directory (`recursive=true`). Snapshots first. |
| `file_rename` | Rename within the same parent directory. |
| `file_copy` | Copy a file or directory. |
| `file_move` | Move or relocate across roots. |

---

## Content

### `content_read`

Read text. Optional line slicing keeps responses small. Works on text-like formats; DOCX/PDF/XLSX delegate to handler `read_text`.

### `content_write`

Replace the entire textual content of a file. Snapshot taken first.

### `content_append`

Append to the end of a text file. v1.1.0 preserves the file's predominant line ending.

### `content_insert`

Insert text at `line_number` (1-based). Existing text shifts down.

### `content_replace`

Find/replace within text. `regex=true` enables Python regex. `count=-1` replaces all.

### `content_delete_range`

Delete lines in `[start_line, end_line]` (1-based, inclusive).

### `content_patch`

Apply a unified diff to a file. Headers (`---`, `+++`) tolerated.

### `content_diff` 🆕

Unified diff between any two files. Text formats diff raw content; DOCX/XLSX/PPTX/PDF diff via `extract_for_search` (lossy for formatting, useful for prose).

| Param | Type | Default |
|-------|------|---------|
| `path_a` | `str` | required |
| `path_b` | `str` | required |
| `context_lines` | `int` | `3` |
| `ignore_whitespace` | `bool` | `false` |

Returns `{ identical, diff, stats: { additions, deletions, changes }, format_a, format_b }`.

---

## Structured access

Format-aware get/set/delete. Expression syntax depends on format:

- **JSON / YAML / JSON5**: JSONPath (`$.config.items[2]`) — 🆕 list indices `$.array[N]` now supported
- **XML / SVG**: XPath
- **XLSX**: `cell:Sheet1!A1`, `range:Sheet1!A1:B10`, `sheet:Sheet1`
- **DOCX**: `paragraph:N`, `paragraph_runs:N` 🆕, `table:N`, `table:N!A1` 🆕, `table:N!row:M` 🆕, `table:N!col:M` 🆕, `core_props`
- **PPTX**: `slide:N`
- **PDF**: `page:N`, `metadata`

| Tool | Description |
|------|-------------|
| `struct_get` | Format-aware read |
| `struct_set` | Format-aware write. For DOCX `paragraph_runs:N`, value is `[{text, bold?, italic?, underline?}, ...]` — preserves inline formatting |
| `struct_delete` | Format-aware delete (now supports list-index deletion) |
| `struct_meta` | Format-aware metadata (delegates to `handler.read_meta`) |

---

## Metadata

| Tool | Description |
|------|-------------|
| `metadata_read` | Read all metadata (EXIF, OOXML core properties, PDF docinfo) |
| `metadata_write` | Merge `updates` into the file's metadata. Snapshot pre+post |
| `metadata_delete` | Delete specific keys. Equivalent to `metadata_write` with `null` values |
| `metadata_strip` | Remove all writable metadata. Useful for privacy-sanitising |
| `metadata_read_batch` 🆕 | Read metadata for every file matching `glob`. `fields` filter, `max_files` cap. Returns `{ count, files[], skipped[], skipped_summary }` |

---

## Authoring

### `validate_spec`

Validate a document JSON spec without writing. Returns `{ valid, normalized }` or `{ valid: false, error }`.

### `compose_docx`

Render a JSON spec to `.docx`. Block types: heading, paragraph, list, table, image, page_break, code, math, hr, blockquote.

| Param | Type | Default |
|-------|------|---------|
| `path` | `str` | required |
| `spec` | `dict\|str` | required |
| `overwrite` | `bool` | `false` |
| `template` 🆕 | `str?` | `null` |

When `template` is provided, blocks are appended to a copy of that template — inherits styles, headers, footers, page setup.

### `compose_pdf`

Same block schema as `compose_docx`, renders via reportlab.

### `compose_from_markdown`

Convert Markdown source to `.docx` or `.pdf` (selected by extension or `format` arg).

### `compose_to_markdown` 🆕

Convert a DOCX to Markdown via mammoth + html2text. Tables, code blocks, lists, headings, links preserved.

| Param | Type | Default |
|-------|------|---------|
| `src` | `str` | required (`.docx`) |
| `dst` | `str` | required (`.md`) |
| `overwrite` | `bool` | `false` |
| `extract_images` | `bool` | `true` |
| `style_map` | `str` | `""` |
| `body_width` | `int` | `0` |

When `extract_images=true`, embedded images write to `<dst_dir>/images/` and the markdown references them with relative paths.

---

## Sections

### `section_extract` 🆕

Carve a section out of a DOCX into a standalone file.

| Param | Type | Default |
|-------|------|---------|
| `src` | `str` | required (`.docx`) |
| `dst` | `str` | required (`.docx`) |
| `heading_pattern` | `str?` | one of |
| `paragraph_range` | `[int, int]?` | one of |
| `overwrite` | `bool` | `false` |

`heading_pattern` extracts from matching heading inclusive to next equal/higher heading exclusive. `paragraph_range` extracts a 0-based slice. Provide exactly one.

### `section_merge` 🆕

Merge multiple DOCX files via `docxcompose`.

| Param | Type | Default |
|-------|------|---------|
| `sources` | `str[]` | required (≥2) |
| `dst` | `str` | required |
| `preserve_styles` | `bool` | `false` |
| `page_break_between` | `bool` | `true` |
| `overwrite` | `bool` | `false` |

First source becomes master (its styles/headers/footers/page setup win). With `preserve_styles=true`, conflicting style IDs are renamed (`MyStyle_1`).

---

## Images

Embedded image tools for DOCX/PPTX (read+write) and PDF (read-only).

### `image_list` 🆕

List embedded images. Returns `{ count, images: [{ index, internal_name, size, ext, page? }] }`. PDF entries also carry `page`.

### `image_extract` 🆕

Extract one image to a destination file. Forces destination extension to match the source image's actual ext.

### `image_extract_all` 🆕

Extract every image into a directory.

| Param | Type | Default |
|-------|------|---------|
| `path` | `str` | required |
| `dst_dir` | `str` | required |
| `naming_pattern` | `str` | `"image_{index:03d}{ext}"` |

### `image_replace` 🆕

Replace an embedded image at `index` with bytes from `src`. DOCX/PPTX only. Preserves `internal_name` so existing references keep working.

---

## Templates

Jinja2-style DOCX templating via `docxtpl`. Built-in registry under `templates/<category>/<name>/`. v1.1.0 ships with `academic_id/kp_basic`.

### `template_render` 🆕

Render an arbitrary DOCX template path.

| Param | Type | Default |
|-------|------|---------|
| `template` | `str` | required (`.docx`) |
| `dst` | `str` | required (`.docx`) |
| `vars` | `dict?` | `null` |
| `loops` | `dict?` | `null` |
| `conditionals` | `dict?` | `null` |
| `inline_images` | `dict?` | `null` |
| `overwrite` | `bool` | `false` |

`inline_images={var: 'kp:/img.png'}` injects a path. `{var: {path: ..., width_mm: 60}}` sizes it.

### `template_list` 🆕

List built-in templates. Optional `category` filter. Returns `{ count, templates: [{ id, category, name, template_path, manifest? }] }`.

### `template_install` 🆕

Copy a built-in template into the workspace by `template_id` (`category/name`).

### `template_render_named` 🆕

Render a built-in template directly without copying. Same vars/loops/conditionals/inline_images shape as `template_render`.

---

## TOC & Bibliography

### `toc_generate` 🆕

Generate a static table of contents from heading paragraphs.

| Param | Type | Default |
|-------|------|---------|
| `path` | `str` | required (`.docx`) |
| `insert_at` | `str?` | `null` (top of body) |
| `style` | `str` | `"dotted_leader"` |
| `max_depth` | `int` | `3` |
| `exclude_patterns` | `str[]?` | `null` |
| `page_numbers` | `bool` | `false` |

`insert_at` accepts `paragraph:N` or `after:HEADING_TEXT`. Style is `dotted_leader` or `indented`.

### `bibliography_check` 🆕

Validate citations against the bibliography section. Detects missing entries (cited but not listed), unused entries (listed but never cited), duplicates, and style mismatches (APA / IEEE).

| Param | Type | Default |
|-------|------|---------|
| `path` | `str` | required (`.docx`) |
| `style` | `str` | `"APA"` |
| `auto_detect_section` | `bool` | `true` |
| `bib_section_pattern` | `str?` | `null` |

Returns `{ citations_found, bibliography_entries, issues[] }`.

### `bibliography_format` 🆕

Reformat the bibliography section. `sort=true` (default) sorts alphabetically. `auto_fix=false` (default) reports without writing; `auto_fix=true` applies + snapshots.

---

## Compare & Lint

### `document_compare` 🆕

Generate a comparison DOCX from two documents.

| Param | Type | Default |
|-------|------|---------|
| `src_a` | `str` | required |
| `src_b` | `str` | required |
| `dst` | `str` | required (`.docx`) |
| `style` | `str` | `"track_changes"` |
| `overwrite` | `bool` | `false` |

Styles:
- `track_changes` — inline `[+ inserted +]` / `[- deleted -]` markers
- `side_by_side` — two-column table, A on the left, B on the right
- `diff_doc` — colored unified diff

### `document_lint` 🆕

Run quality checks against a DOCX. `rules` accepts a preset name or list of rule IDs / preset names.

| Param | Type | Default |
|-------|------|---------|
| `path` | `str` | required (`.docx`) |
| `rules` | `str\|str[]` | `"default"` |
| `severity_filter` | `str?` | `null` |

**Built-in presets:**

| Preset | Extends | Rules added |
|--------|---------|-------------|
| `default` | — | trailing_whitespace, empty_heading, duplicate_heading, heading_hierarchy_skip |
| `academic_id` | default | title_case_id |
| `academic_id_kp` | academic_id | required_section_lembar_pengesahan, kata_pengantar, daftar_isi, pendahuluan, daftar_pustaka, lampiran, log_book |
| `academic_id_skripsi` | academic_id | abstrak, daftar_gambar/tabel, tinjauan_pustaka, metodologi, hasil_pembahasan, kesimpulan_saran, plus full KP set |

Returns `{ rules_evaluated, issues[], summary: { errors, warnings, info, auto_fixable } }`.

### `document_lint_fix` 🆕

Apply auto-fixes for lint issues.

| Param | Type | Default |
|-------|------|---------|
| `path` | `str` | required (`.docx`) |
| `rules` | `str\|str[]` | `"default"` |
| `dry_run` | `bool` | `true` |
| `only_severities` | `str[]?` | `null` |

Pass `dry_run=false` to apply. `only_severities` restricts fixes to listed severities (`error`, `warn`, `info`).

---

## Batch operations

### `batch_rename`

Rename files matching `glob` by regex `pattern` → `replacement`. Snapshots each modified file. `dry_run=true` by default.

### `batch_replace_content`

Find/replace inside text-like files matching `glob`. `regex=false` and `case_sensitive=true` by default.

### `batch_replace_structured`

Format-aware find/replace inside DOCX/XLSX/PPTX. Walks paragraphs, table cells, spreadsheet cells, slide text frames via the native writer (no raw bytes).

| Param | Type | Default |
|-------|------|---------|
| `glob` | `str` | required |
| `old` | `str` | required |
| `new` | `str` | required |
| `regex` | `bool` | `false` |
| `dry_run` | `bool` | `true` |
| `case_sensitive` | `bool` | `true` |
| `scope` 🆕 | `dict?` | `null` |

`scope` keys per format:

- **DOCX**: `headings_only`, `tables_only`, `paragraph_range`, `heading_section`, `exclude_styles`, `include_styles`
- **XLSX**: `sheets`, `cell_range`
- **PPTX**: `slides`

### `batch_delete`

Delete files matching `glob`. Always snapshots before deletion. `dry_run=true` by default.

---

## Search

### `search_filename`

Search files by filename glob across the workspace.

### `search_content`

Plain-text content search across the workspace. Files read via handler `extract_for_search` (cached on `(mtime, size)` in v1.1.0).

| Param | Type | Default |
|-------|------|---------|
| `query` | `str` | required |
| `glob` | `str?` | `null` |
| `root` | `str?` | `null` |
| `regex` | `bool` | `false` |
| `case_sensitive` | `bool` | `false` |
| `max_results` | `int` | `200` |
| `max_files` | `int` | `5000` |
| `include_context` 🆕 | `bool` | `false` |
| `language` 🆕 | `str?` | `null` |
| `stem` 🆕 | `bool` | `false` |

`include_context=true` adds DOCX `heading_path` + `paragraph_index` per hit. `language="id"` + `stem=true` enables Sastrawi-based Indonesian morphological matching (requires `[indonesian]` extra) — `mengatakan` matches `berkata`, `perkataan`, etc.

### `search_in_format`

Search inside a specific format (pdf, docx, xlsx, pptx, csv, xml, json, yaml, text). Useful when you only want to scan e.g. PDFs.

---

## Versioning

| Tool | Description |
|------|-------------|
| `version_list` | List the snapshot history for a file (newest first) |
| `version_diff` | Unified diff between current file and a snapshot version |
| `version_restore` | Replace the current file with a specific snapshot |
| `version_undo` | Revert to the most recent snapshot |
| `version_purge` | See below |

### `version_purge` 🆕 (changed semantics)

| Param | Type | Default |
|-------|------|---------|
| `older_than_days` | `int?` | `null` |

- `None` → use `versioning.retention_days`
- `0` → 🆕 explicitly purges ALL snapshots (was: silent no-op in v1.0.x)
- `>0` → keep only snapshots from last N days
- Negative values rejected with `ValueError`

---

## Semantic

### `search_semantic` *

Vector semantic search via sentence-transformers. Requires `semantic_search.enabled = true` and the `[semantic]` extra.

### `semantic_index_path` *

Index or re-index a file/directory in the semantic store.

### `semantic_stats` *

Return current index stats (chunks, documents, model).

---

## See also

- **[USAGE.md](USAGE.md)** — practical workflows and common recipes
- **[CONFIG.md](CONFIG.md)** — full configuration reference
- **[ARCHITECTURE.md](ARCHITECTURE.md)** — module structure and request flow
- **[BENCHMARK.md](BENCHMARK.md)** — performance baselines
- **[profiles/README.md](profiles/README.md)** — six pre-tuned configurations
- **[../templates/academic_id/kp_basic/README.md](../templates/academic_id/kp_basic/README.md)** — bundled KP report template
