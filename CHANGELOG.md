# Changelog

All notable changes to **Dokumen-Pintar** are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

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
