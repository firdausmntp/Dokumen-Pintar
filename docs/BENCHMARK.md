# Benchmark

> What's fast, what's slow, what we measured, and how to reproduce it.

This document captures **representative** performance numbers, not a stress test. The point is to give you a feel for whether Dokumen-Pintar is the right tool for your workload, and to make every claim in the README reproducible.

---

## Quick Numbers

Hardware: Intel i7-1165G7 (4c/8t, 2.80 GHz), 16 GB RAM, NVMe SSD, Windows 11. Python 3.13.3, sync stdio transport. Median of 10 runs after a warm-up call. Numbers will be lower on slower disks or older laptops; higher on fast desktops.

| Operation | Format | Size | Median | Notes |
|:----------|:-------|:-----|-------:|:------|
| `content_read` | TXT | 1 KB | ~2 ms | bottleneck = JSON serialization, not I/O |
| `content_read` | TXT | 1 MB | ~7 ms | encoding detection runs once |
| `content_read` | DOCX | 200 KB | ~35 ms | python-docx open dominates |
| `content_read` | XLSX | 500 KB, 1 sheet | ~50 ms | openpyxl with `read_only=True` |
| `content_read` | PDF | 50 pages | ~600 ms | pdfplumber per-page extraction |
| `search_content` | first call (1 GB workspace) | mixed | ~8 s | walks tree, parses every supported file once |
| `search_content` | repeat call (cached) | mixed | ~80 ms | hits `extract_cache.sqlite` |
| `struct_get cell:Sheet1!B2` | XLSX | 500 KB | ~45 ms | full workbook load (could be optimized) |
| `struct_set cell:Sheet1!B2` | XLSX | 500 KB | ~120 ms | load + mutate + save + 2 snapshots |
| `compose_docx` | 50 blocks | n/a | ~280 ms | reportlab is the slower of the two renderers |
| `compose_pdf` | 50 blocks | n/a | ~190 ms | |
| `version_list` | 50 entries | n/a | ~3 ms | thread-local SQLite, WAL mode |
| `version_restore` | 1 MB file | n/a | ~12 ms | |
| `pytest` (full suite) | — | — | ~30 s | 1098 tests, `-n auto` parallel |

**Headline:** Reads on text formats are sub-10 ms. Office formats are 30-100 ms. PDFs scale with page count. Snapshot overhead is dominated by the file copy itself, not the SQLite write (~1 ms).

---

## Where the time actually goes

Profiling a single `content_read` on a 200 KB DOCX:

```
python-docx Document() open      ~22 ms   ← largest cost, unavoidable
  └─ ZIP unpack + XML parse
read_text() (paragraph iter)      ~9 ms
PathGuard.resolve                 ~0.4 ms
size limit check                  ~0.1 ms
audit log write                   ~0.3 ms
JSON response serialization       ~0.5 ms
                                  ─────────
total                            ~35 ms
```

The handler dominates. Anything we add at the framework layer is single-digit milliseconds.

For `search_content` on a 1 GB workspace with mixed formats, **the first call is bound by parsing**: every DOCX/PDF/XLSX in scope gets `extract_for_search()` called. The `extract_cache.sqlite` cache (mtime+size keyed) makes subsequent calls effectively free unless files changed.

---

## Optimization timeline (1.0.x)

These changes shipped during the 1.0 series and are baked in. Each one was measured before/after in isolation.

| Change | Where | Before | After | Notes |
|:-------|:------|-------:|------:|:------|
| pypdf primary, pdfplumber fallback | `extract_for_search` | ~600 ms / 50pp | ~110 ms / 50pp | 5-7x faster for typical PDFs |
| `read_only=True` for XLSX query paths | `read_meta`, `read_text`, `extract_for_search` | ~280 ms / 5MB | ~55 ms / 5MB | openpyxl skips style objects |
| Thread-local SQLite pool | `VersionStore._connect` | ~1.2 ms / call | ~0.05 ms / call | mostly noise reduction |
| `extract_cache.sqlite` (mtime+size) | `search_content` repeat calls | ~8 s | ~80 ms | first call still pays parse cost |
| `_BINARY_EXTENSIONS` fast-path | `batch_replace_content` skip filter | ~2 ms / file | ~0.001 ms / file | only relevant for large workspaces |

---

## How to reproduce

There's no formal benchmark harness yet (it's roadmap). For now, the methodology is:

```python
import time
from dokumen_pintar.config import load_config
from dokumen_pintar.context import build_context

ctx = build_context(load_config("docs/profiles/personal.json"))

# Warm up - first call pays import + parser warm cost.
ctx.registry.for_path(some_path).read_text(some_path)

# Measure 10 runs, report the median.
samples = []
for _ in range(10):
    t0 = time.perf_counter()
    ctx.registry.for_path(some_path).read_text(some_path)
    samples.append(time.perf_counter() - t0)
samples.sort()
print(f"median: {samples[5] * 1000:.1f} ms")
```

If you want to measure a tool **end to end** (including PathGuard, snapshot, audit, JSON serialization), call the registered MCP tool function directly via `ctx`. The overhead beyond the handler call is consistent and small enough that handler-level numbers are a reasonable proxy.

---

## Practical knobs

**Workspace too big to search?**
- Tighten `exclude_patterns` first. The default excludes `.git`, `node_modules`, and `.venv`; add your own (build outputs, vendored libs, generated docs).
- Lower `max_file_size_mb` if you don't need to read >25 MB files.
- Use `glob` arguments on search tools - `search_content("query", glob="docs:/*.md")` is dramatically faster than no filter.

**PDF parsing slow?**
- 50-page PDFs take ~100 ms with the current pypdf-first path. 500-page PDFs scale roughly linearly.
- Embedded scanned images aren't OCR'd - we extract the text layer only. If your PDF is scanned-only, `extract_for_search` returns "" and `search_content` won't find it. OCR is on the roadmap, not 1.x.

**Snapshots eating disk?**
- Lower `versioning.max_versions_per_file` (default 50) to drop the per-file ceiling.
- Lower `versioning.retention_days` (default 30) and run `version_purge`.
- Set `versioning.enabled = false` if you really don't need it (you'll lose `version_*` recovery).

**Search cache stale?**
- The `extract_cache.sqlite` is keyed on `(mtime, size)`. If your workflow modifies file times without changing content (rsync, copy-on-write), entries stay valid. If something edits a file without bumping mtime (rare), `extract_cache.invalidate(path)` is the escape hatch - exposed via the Python API but not yet as an MCP tool.

---

## What's NOT optimized (yet)

Honest list of known slow paths:

- **`struct_set cell:...` on XLSX** loads the whole workbook, mutates, saves. Round-trip is ~120 ms even for a single cell. The fix is to keep an open workbook handle for batch operations - planned for 1.2.
- **`compose_pdf` with embedded images** scales with image count and DPI. ~50 small images puts us in seconds territory. reportlab is the bottleneck.
- **`search_in_format` for PDFs** parses every PDF in scope on every call (cached on second call onwards). Walking 1000 PDFs cold takes minutes; the cache makes warm runs sub-second.
- **Semantic search** is opt-in. The `sentence-transformers` model load is ~500 ms first call; embedding a single query is ~10 ms after that. Indexing a fresh document corpus (~100 PDFs) takes minutes - this is the model's cost, not ours.
- **`batch_*` operations on >5000 files** allocate the full match list before processing. Memory hits ~1 GB on huge workspaces. Streamed iteration is on the roadmap.

If any of these block your use case, file an issue with a workload description and we'll prioritize.

---

## Comparison vs raw filesystem MCP

You won't beat a "just read the bytes" MCP server on raw text files - PathGuard, audit, and snapshot all add cost. The sweet spot is **structured access to office formats**: there's no equivalent in plain filesystem servers, and parsing a DOCX once for `struct_get paragraph:42` is faster than asking the model to re-parse the bytes.

| Workload | Raw FS MCP | Dokumen-Pintar |
|:---------|-----------:|---------------:|
| Read 1 KB TXT | ~1 ms | ~2 ms |
| Read 1 MB TXT | ~5 ms | ~7 ms |
| `paragraph:42` of DOCX | impossible (model parses bytes) | ~35 ms |
| `cell:Sheet1!B2` of XLSX | impossible (model parses bytes) | ~50 ms |
| Recover after a bad write | impossible (no snapshot) | `version_restore` ~12 ms |

For workflows that involve *editing* office documents, the gap closes further: a single `struct_set` call replaces "read bytes → ask model to rewrite XML → write bytes" which can easily run into the seconds.

---

## Reproducibility footnotes

- All numbers came from the same machine. Real numbers vary 2-3x across hardware.
- "Median of 10 runs" excludes the first call so we measure steady-state, not import + warm-up.
- Tests run in `-n auto` parallel mode. Single-thread runs are roughly 3-4x slower wall-clock.
- We use system Python (3.13.3 on Windows 11) for these numbers. Older Pythons don't differ materially for I/O-bound workloads.
- All timings are end-to-end inside the Python process. We don't measure MCP transport overhead - stdio adds ~1 ms; HTTP/SSE adds 5-15 ms depending on payload size.
