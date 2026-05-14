# Changelog

All notable changes to **Dokumen-Pintar** are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
