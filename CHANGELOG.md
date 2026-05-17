# Changelog

All notable changes to **Dokumen-Pintar** are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.1.0] - 2026-05-17

> **Major themes:** new authoring & analysis tooling (15 new tools), an
> extensible lint subsystem with Indonesian academic presets, scoped
> structured search/replace, Indonesian morphological search, structured
> errors with hints + docs URLs, and a bundled template registry.

### Added

#### New MCP tools

- **`content_diff`** - unified diff between any two files. Text formats
  diff raw content; DOCX/XLSX/PPTX/PDF diff via `extract_for_search`.
  Returns diff + line stats. Supports `context_lines` and
  `ignore_whitespace`.
- **`metadata_read_batch`** - bulk metadata reader walking a glob.
  Returns format/meta per file with `fields` filter and a
  `skipped_summary`.
- **`workspace_diagnose`** - read-only health check covering config,
  snapshot store, audit log, extract cache, semantic index, and
  per-root disk usage. Surfaces oversized-store warnings.
- **`compose_to_markdown`** - DOCX → Markdown via mammoth + html2text.
  Tables, code blocks, lists, and headings preserved. `extract_images`
  writes embedded images to `<dst_dir>/images/`.
- **`compose_docx(template=...)`** - render a JSON spec into a copy of
  an existing DOCX template, inheriting styles, headers, footers,
  page setup, and cover pages. Useful for university templates.
- **`section_extract`** - carve a section out of a DOCX into a
  standalone file. Selection by heading-text regex (extracts from
  matching heading inclusive to next equal/higher heading exclusive)
  or by paragraph-index range.
- **`section_merge`** - merge multiple DOCX files into one via
  `docxcompose`. First source becomes master; conflicting style IDs
  are renamed (`MyStyle_1`) when `preserve_styles=True`. Optional
  page break between sources.
- **`image_list` / `image_extract` / `image_extract_all` / `image_replace`** -
  embedded image tools for DOCX/PPTX (full read+write) and PDF (read-only).
  ZIP rebuild keeps `internal_name` stable so existing references
  continue to point at the new image bytes.
- **`template_render`** - Jinja2-style DOCX rendering via `docxtpl`.
  Supports `{{ var }}` substitution, `{% for %}` loops, `{% if %}`
  conditionals, and inline image injection (`{var: 'kp:/img.png'}`
  or `{var: {path: ..., width_mm: 60}}`). Snapshots pre+post.
- **`template_list` / `template_install` / `template_render_named`** -
  built-in template registry under `templates/<category>/<name>/`.
  Each entry ships with `template.docx`, `manifest.json`, and a
  `README.md`. v1.1.0 ships with `academic_id/kp_basic` (a generic
  Indonesian Kerja Praktik report skeleton).
- **`toc_generate`** - static table of contents from heading
  paragraphs. Walks Title + Heading 1..N up to `max_depth`,
  inserts a `DAFTAR ISI` block. `insert_at` accepts `paragraph:N`
  or `after:HEADING_TEXT`. `exclude_patterns` regex list skips
  matching headings. Two layout styles: `dotted_leader`, `indented`.
- **`bibliography_check`** - validate citations against the
  bibliography section. Detects missing entries, unused entries,
  duplicates, and style mismatches (APA / IEEE). Auto-detects
  DAFTAR PUSTAKA / REFERENCES / Bibliography headings; override
  via `bib_section_pattern`.
- **`bibliography_format`** - reformat the bibliography section
  alphabetically. `auto_fix=False` reports what would change;
  `auto_fix=True` applies + snapshots.
- **`document_compare`** - generate a comparison DOCX from two
  source documents. Three styles: `track_changes` (inline
  insertion/deletion markers), `side_by_side` (two-column table),
  `diff_doc` (colored unified diff).
- **`document_lint`** - run quality checks against a DOCX with a
  pluggable rule registry. Built-in rules: `trailing_whitespace`,
  `empty_heading`, `duplicate_heading`, `heading_hierarchy_skip`,
  `title_case_id`, plus 13 `required_section_*` rules. Presets:
  `default`, `academic_id`, `academic_id_kp` (KP report),
  `academic_id_skripsi` (undergraduate thesis).
- **`document_lint_fix`** - auto-fix lint issues. Defaults to
  dry-run; `dry_run=False` applies + snapshots. `only_severities`
  restricts which severities get fixed.
- **DOCX `struct_get` `paragraph_runs:N`** - return per-run text
  with bold/italic/underline flags. Companion `struct_set` accepts
  a list of run dicts so callers can replace paragraph content
  while preserving formatting.

#### Indonesian language support

- **Sastrawi morphological stemmer** integrated into `search_content`
  via `language="id"` + `stem=True`. Query and document text both
  get stemmed before matching, so `mengatakan` matches `berkata`,
  `perkataan`, `kata-kata`, etc. Acronyms (≤5 uppercase chars) are
  preserved verbatim. Available via the optional `[indonesian]` extra.
- **Indonesian rule presets** (`academic_id`, `academic_id_kp`,
  `academic_id_skripsi`) check structural conventions of Indonesian
  academic documents - LEMBAR PENGESAHAN, KATA PENGANTAR, DAFTAR
  ISI, BAB I PENDAHULUAN, LOG BOOK, etc.
- **Bundled `academic_id/kp_basic` template** - generic Indonesian
  KP report skeleton with cover page, lembar pengesahan, kata
  pengantar, daftar isi, BAB I/II, log book table, lampiran, and
  daftar pustaka. Ships with the wheel under
  `share/dokumen-pintar/templates/`.

#### Internal building blocks

- **`lint/` subsystem** - `LintRule` base class, `Issue` dataclass,
  `default_registry` with rule + preset management. Rules register
  via `@register_rule`; presets via `add_preset(name, rules=...,
  extends=...)`. Cycle detection on `extends` chains.
- **`utils/stemming_id.py`** - thread-safe Sastrawi wrapper with
  process-wide stemmer cache.
- **`tools/_common.py`** - new helpers `resolve_for_read` /
  `resolve_for_write` shared across all new tools.

### Changed

- **`version_purge(older_than_days=0)` now explicitly purges ALL
  snapshots** (was: silent no-op). Negative values raise
  `ValueError`. Pass `None` and configure `retention_days = 0`
  for the old behaviour.
- **Glob `**/*` matches both top-level and nested files**
  (was: nested only). `**/*.txt` catches `top.txt` AND
  `sub/nested.txt`.
- **Line endings (CRLF / LF / CR) preserved** across
  `content_replace`, `content_insert`, `content_delete_range`,
  `content_append`, and `content_patch`. Eliminates spurious
  git-diff churn on Windows files.
- **`extract_for_search` for PDF prefers pypdf over pdfplumber.**
  pypdf handles the vast majority of search workloads adequately
  while costing ~5-10x less parser time. pdfplumber stays as a
  fallback for PDFs pypdf can't extract.
- **XLSX read paths use `read_only=True`** (`read_meta`,
  `read_text`, `extract_for_search`). 5-20x faster on large
  workbooks, fraction of the memory.
- **`search_content` accepts `include_context=True`** to enrich
  DOCX hits with `paragraph_index` + `heading_path`. Default
  `False` keeps the v1.0.x response shape.
- **`struct_get` for DOCX accepts `table:N!A1`, `table:N!row:M`,
  `table:N!col:M`** sub-expressions for cell/row/column-level
  access without parsing the whole table response.
- **`batch_replace_structured` accepts a `scope` dict** to restrict
  replacements:
  - DOCX: `{headings_only, tables_only, paragraph_range,
    heading_section, exclude_styles, include_styles}`
  - XLSX: `{sheets, cell_range}`
  - PPTX: `{slides}`
- **`DokumenPintarError` now carries `hint`, `docs_url`, and `code`
  fields.** Backward-compatible: existing single-arg call sites
  unchanged. The new fields render in `str(exc)` and serialise
  via `exc.to_dict()`.
- **`VersionStore` SQLite uses thread-local connection pool.**
- **`extract_cache.sqlite`** caches `extract_for_search` results
  keyed on `(mtime, size)`. Repeat searches across the same
  workspace skip parsing entirely.

### Fixed

- **`struct_delete` now supports JSONPath list indices**
  (`$.array[N]`). v1.0.x raised on `Index(...)` segments because
  the dispatcher only checked the legacy `index` attribute; newer
  `jsonpath_ng` releases expose `indices` (a tuple). Fix accepts
  both, deletes from highest index first so list slices stay
  consistent.
- **Repository hygiene**: `htmlcov/`, `.coverage`, `rawr/`,
  `tests_e2e_rawr.py`, `dokumen-pintar.config.json` properly
  gitignored.

### Performance

- `extract_for_search` cache hit ~80 ms vs ~8 s cold call on
  a 1 GB mixed-format workspace.
- PDF extraction ~5-10x faster on the typical path
  (50-page PDFs: ~600 ms → ~110 ms).
- XLSX query ops 5-20x faster on workbooks > 1 MB.

### Documentation

- **`AGENTS.md`** - contributor guide (hard rules, repo layout,
  request flow, how to add a tool / handler / preset, PR process).
- **`docs/BENCHMARK.md`** - performance baselines and methodology.
- **`docs/profiles/`** - six pre-tuned config profiles (minimal,
  personal, developer, research, read-only, team-server).
- **`docs/config.schema.json`** - JSON Schema for editor autocomplete.
- **README polish** - accurate tool count, killer-feature section,
  links to BENCHMARK and AGENTS.

### Dependencies

Added (core):
- `mammoth>=1.12` - DOCX → HTML for markdown conversion
- `html2text>=2024.2` - HTML → Markdown post-processor
- `docxcompose>=2.1` - DOCX merge with style preservation
- `docxtpl>=0.20` - Jinja2-style DOCX templating

Added optional extras:
- `[indonesian]`: `Sastrawi>=1.0.1` for morphological stemming.


## [1.0.2] - 2026-05-15

### Added

- **Authoring API** — produce DOCX/PDF dari deklaratif JSON spec atau
  Markdown source, semua pure-Python.
  - `validate_spec` — validasi spec tanpa side-effect.
  - `compose_docx(path, spec)` — render JSON spec ke `.docx` via
    python-docx (heading, paragraph dengan bold/italic/underline/code/
    font_size/color, list ordered/unordered, table dengan header,
    image dengan width_cm + caption, page_break, code block, math
    placeholder, hr, blockquote). Tolak overwrite kecuali
    `overwrite=True`. Pre+post snapshot otomatis.
  - `compose_pdf(path, spec)` — sama untuk `.pdf` via reportlab.
  - `compose_from_markdown(path, markdown, format=...)` — shortcut yang
    parse Markdown → spec → render. Format diturunkan dari ekstensi
    target atau di-pass eksplisit.
- **`batch_replace_structured` tool** — find/replace aman untuk
  `.docx`/`.xlsx`/`.pptx` lewat handler structured (paragraph, table
  cell, spreadsheet cell, slide text frame). ZIP container tetap utuh,
  tidak mengandalkan raw byte mutation. Dry-run default, `regex` &
  `case_sensitive` dukung, snapshot pre+post saat apply, kegagalan
  apply di-demote ke `skipped` dengan `reason: "apply_failed"`.
- **`MarkdownHandler`** — handler khusus untuk `.md` / `.markdown`
  (override TextHandler untuk dua ekstensi tsb). Capabilities:
  READ_TEXT, WRITE_TEXT, STRUCTURED_GET, SEARCH_EXTRACTED.
  Struct expressions: `outline` / `headings`, `heading:N` (return
  section termasuk semua sub-heading sampai heading sejajar/lebih
  tinggi berikutnya), `wordcount`. Bukan binary container, sehingga
  `batch_replace_content` tetap bekerja normal untuk Markdown.
- **`LatexHandler`** — handler `.tex` via pylatexenc parser. Read meta
  (documentclass, packages, environment_counts, outline), `outline` /
  `sections` / `packages` / `documentclass` / `environments` /
  `section:N` lewat `struct_get`. Tidak compile ke PDF (pure-Python
  scope); gunakan `compose_pdf` untuk authoring PDF baru.
- **Metadata edit layer** — empat tool MCP baru yang seragam di semua
  handler yang advertise `HandlerCapability.WRITE_META`. Semua operasi
  snapshot pre+post sehingga bisa di-rollback via `version_restore`.
  - `metadata_read(path)` — kembalikan `read_meta()` handler-native
    untuk path apa pun (image, docx, xlsx, pptx, pdf, ...).
  - `metadata_write(path, updates)` — merge dict ke metadata file;
    unknown key ditolak, value `null` menghapus field.
  - `metadata_delete(path, keys)` — gula sintaks untuk
    `metadata_write` dengan tiap key di-set ke `null`.
  - `metadata_strip(path)` — hapus semua metadata writable
    (privacy-sanitize sebelum sharing).
- **`ImageHandler` baru** untuk `.jpg/.jpeg/.png/.tif/.tiff/.webp/.bmp/`
  `.gif` dengan EXIF read/write/strip via Pillow + piexif.
  - `read_meta` mengekstrak EXIF tags + GPS sub-IFD (resolved via
    `getexif().get_ifd(0x8825)`), IPTC, PNG text chunks, dimensi,
    color mode.
  - `structured_get` expressions: `exif`, `metadata` (alias),
    `dimensions` / `size`, `gps`, `exif:<TagName>`.
  - `write_meta` writable tags: `artist`, `copyright`,
    `image_description`, `software`, `make`, `model`, `orientation`,
    `date_time`, `date_time_original`, `date_time_digitized`,
    `user_comment`, `lens_make`, `lens_model`. Set value ke `null`
    untuk delete tag. JPEG/TIFF/WebP didukung penuh; PNG read-only.
  - `strip_meta` membersihkan seluruh EXIF block.
- **`write_meta` / `strip_meta` di handler Office & PDF**:
  - **DOCX** — core_properties (`author`, `title`, `subject`,
    `keywords`, `category`, `comments`, `language`,
    `last_modified_by`, `version`, `content_status`, `identifier`,
    `created`, `modified`, `last_printed`, `revision`).
  - **XLSX** — workbook properties dengan nama openpyxl asli
    (`creator`, `lastModifiedBy`, `contentStatus`, dst.).
    `strip_meta` hanya membersihkan field string (datetime field
    di-skip karena openpyxl tidak bisa serialisasi `None` timestamp).
  - **PPTX** — core_properties identik dengan DOCX.
  - **PDF** — docinfo dict (`title`, `author`, `subject`, `creator`,
    `producer`, `keywords`, `creation_date`, `modification_date`)
    via pikepdf. `strip_meta` juga clear XMP packet via
    `open_metadata().clear()`. Encrypted PDF ditolak dengan
    `HandlerError`.

### Changed

- **Glob URI prefix dinormalisasi** di `batch_*` & `search_*` tools.
  Pola `<root>:/sub/*.ext` sekarang otomatis di-strip menjadi root
  filter + bare pattern, bukan lagi di-fnmatch literal terhadap path
  relatif (yang menyebabkan zero-match diam-diam). Helper baru
  `dokumen_pintar.utils.globbing.split_root_glob`.
- **`batch_replace_content` skipped summary** — response sekarang
  menyertakan `skipped_summary: {reason: count}` untuk membantu LLM
  mengenali alasan dominan tanpa scan list lengkap.

### Fixed

- DOCX file dengan glob ber-prefix root (mis. `kp:/*.docx`) sebelumnya
  return `count: 0` tanpa key `skipped` karena pattern dibandingkan
  literal terhadap nama file. Sekarang prefix di-strip dan iterasi
  benar-benar masuk ke handler check (skipped dengan
  `binary_format`).

---

## [1.0.1] - 2026-05-14

### Added

- **CLI flag `--root NAME:PATH[:rw|ro]`** on `dokumen-pintar` (repeatable).
  Replaces config roots so you can run the server against ad-hoc folders
  without editing a config file. Supports a path-only shorthand
  (`--root /some/folder`) where the root name is derived from the basename.
- **CLI flag `--read-only`** on `dokumen-pintar` to force every root to
  `writable=false`, regardless of config or `--root` settings.
- **Optional config file**: when at least one `--root` is provided, the server
  no longer requires a config file on disk.
- **`dokumen-pintar-doctor` console script** (was only an internal function).
  The health check now also verifies `.mcpdocs` writability per writable root,
  lists registered format handlers, and reports whether optional
  semantic-search dependencies are importable. Returns non-zero exit on issues.
- **`batch_replace_content`** now reports skipped files in a `skipped` array
  with explicit reasons (`binary_format`, `binary_content`, `no_handler`,
  `exceeds_max_file_size`, `read_failed`, `stat_failed`).

### Security

- **Path-traversal containment in workspace URIs.** `<root>:/<rel>` now
  rejects paths that resolve outside the named root, including escapes via
  `..` segments and via symlinks that point outside the root. Previously a
  URI like `documents:/../../etc/passwd` could be silently accepted.
- **Refuse to mutate the workspace root.** `file_delete`, `file_rename`,
  `file_move`, and `file_copy` now reject the workspace root itself as a
  target (`documents:/`). In particular, `file_delete(recursive=True)` on
  a root previously wiped the entire mounted folder, and
  `file_copy(overwrite=True)` onto a root would `rmtree` it before copying.

### Fixed

- **`search_filename` / `search_content` glob filter** now matches both the
  file basename *and* the path relative to the root. Previously only the
  basename was checked, so patterns like `**/notes.txt` or `subdir/*.md`
  silently returned no results.
- **`batch_replace_content` corruption guard**: refuses to perform raw
  text find-and-replace on binary container formats (`docx`, `xlsx`, `pptx`,
  `pdf`) and on any file whose first 8 KiB contains a NUL byte. Also enforces
  the configured `max_file_size_mb` limit to prevent regex hangs on huge
  files.
- **`content_*` raw-text mutation guard** for binary container formats. All
  `content_write` / `content_replace` / `content_append` / `content_insert`
  / `content_delete_range` / `content_patch` calls now refuse to clobber an
  existing `docx`, `xlsx`, `pptx`, or `pdf` with raw text (which would yield
  a non-conforming file). Use `struct_set` / `struct_delete` instead.
- **`DocxHandler.write_text` no longer overwrites existing docx files**,
  which previously dropped styles, tables, headers, and embedded images.
- **`file_create` refuses binary containers.** Creating a fresh `*.docx`,
  `*.xlsx`, `*.pptx`, or `*.pdf` via raw text (even an empty string) is
  blocked because the resulting file is not openable by any handler.
- **`file_delete(recursive=True)` now snapshots every contained file**
  before `rmtree`, so individual entries remain recoverable through
  `version_list` + `version_restore`. The result reports `snapshots_taken`.
  Snapshot failures on individual children no longer abort the delete.
- **Snapshot retention is now enforced at startup.** The server purges
  snapshots older than `versioning.retention_days` when it boots, so a
  long-running deployment can no longer silently exceed its retention SLA.

### Documentation

- Corrected CSV structured-query syntax in all README files: the documented
  `cell:R,C` form is now shown as `cell:row:N,col:NAME` (matching the
  long-standing handler implementation).
- README and README.id now document `--root`, `--read-only`, and
  `dokumen-pintar-doctor`.

---

## [1.0.0] - 2026-05-13

### Added

- Initial public release: 8 file-format handlers (text, JSON, YAML, CSV/TSV,
  XML, DOCX, XLSX, PPTX, PDF), versioning with SQLite index, audit logging,
  multi-root path sandbox, batch tools (rename / replace / delete with
  dry-run), search tools (filename / content / per-format / optional
  semantic), and FastMCP transports (stdio, SSE, streamable HTTP).

[1.0.1]: https://github.com/firdausmntp/Dokumen-Pintar/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/firdausmntp/Dokumen-Pintar/releases/tag/v1.0.0
