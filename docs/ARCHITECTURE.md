# <svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="16" y="16" width="6" height="6" rx="1"/><rect x="2" y="16" width="6" height="6" rx="1"/><rect x="9" y="2" width="6" height="6" rx="1"/><path d="M5 16v-3a1 1 0 0 1 1-1h12a1 1 0 0 1 1 1v3"/><path d="M12 12V8"/></svg> Architecture

<a href="../README.md">Home</a> · <a href="USAGE.md">Usage</a> · <a href="TOOLS.md">Tools</a> · <a href="CONFIG.md">Config</a>

Dokumentasi internal **Dokumen-Pintar**: bagaimana modul saling terhubung, alur request, model versioning, kontrak antar layer, jaminan keamanan, decision rationale, dan cara extend.

> Untuk API publik tools, lihat [TOOLS.md](TOOLS.md). Untuk konfigurasi, lihat [CONFIG.md](CONFIG.md).

<p>
  <svg width="100%" height="2" xmlns="http://www.w3.org/2000/svg" role="presentation"><defs><linearGradient id="da" x1="0" x2="1" y1="0" y2="0"><stop offset="0" stop-color="#1e3a5f" stop-opacity="0"/><stop offset=".5" stop-color="#1e3a5f"/><stop offset="1" stop-color="#1e3a5f" stop-opacity="0"/></linearGradient></defs><rect width="100%" height="2" fill="url(#da)"/></svg>
</p>

## 1. Layered Architecture

Dokumen-Pintar terdiri dari **6 layer** yang ketat satu arah (atas → bawah). Layer atas tidak boleh dilewati, layer bawah tidak tahu konsumernya.

```
┌─────────────────────────────────────────────────────────────────┐
│  L6  Transport          stdio  │  SSE  │  streamable-http       │  ← server.py
├─────────────────────────────────────────────────────────────────┤
│  L5  MCP Surface        FastMCP — schema, dispatch, JSON-RPC    │  ← server.py + tools/*
├─────────────────────────────────────────────────────────────────┤
│  L4  Tools (30)         workspace · file · content · structured │  ← tools/*
│                         · search · batch · version · semantic   │
├─────────────────────────────────────────────────────────────────┤
│  L3  Orchestration      AppContext (guard + registry +          │  ← context.py
│                         versions + audit)                       │     tools/_common.py
├─────────────────────────────────────────────────────────────────┤
│  L2  Domain Services    PathGuard · VersionStore · AuditLogger  │  ← pathguard.py,
│                         · HandlerRegistry · SemanticIndex       │     versioning.py,
│                                                                 │     audit.py,
│                                                                 │     handlers/base.py
├─────────────────────────────────────────────────────────────────┤
│  L1  Format Handlers    9 handlers (text, json, yaml, csv, xml, │  ← handlers/*
│                         docx, xlsx, pptx, pdf)                  │
├─────────────────────────────────────────────────────────────────┤
│  L0  Foundation         config · errors · utils (encoding,      │  ← config.py, errors.py,
│                         locks, mime, globbing)                  │     utils/*
└─────────────────────────────────────────────────────────────────┘
```

**Aturan dependency:**

- L0 hanya bisa di-import oleh L1+. Tidak boleh import balik.
- L4 (tools) hanya bicara via L3 (`AppContext`). Tools NEVER import handler langsung — dispatch lewat `registry`.
- L1 (handlers) NEVER tahu tentang `AppContext`, audit, versioning. Mereka pure transformation.
- L5 (MCP surface) hanya wiring; logic ada di L4.

Konsekuensi: lo bisa swap transport (L6) tanpa sentuh tools, swap handler (L1) tanpa sentuh tools, dan unit-test handler tanpa boot server.

---

## 2. Module Map (akurat dengan source)

```
src/dokumen_pintar/
│
├── __init__.py             Versi paket (1.0.0).
├── server.py               Entry point CLI. Parse args, load config,
│                           build_server(), pilih transport, run.
├── config.py               Pydantic models: AppConfig, RootConfig,
│                           VersioningConfig, AuditConfig, TransportConfig,
│                           SemanticSearchConfig, SafetyConfig.
│                           find_config_file() & load_config().
├── context.py              AppContext dataclass + build_context().
│                           Wires PathGuard, VersionStore, AuditLogger,
│                           HandlerRegistry, dan trigger import handler.
├── errors.py               Exception hierarchy:
│                           DokumenPintarError
│                             ├── ConfigError
│                             ├── PathNotAllowedError
│                             ├── RootNotWritableError
│                             ├── FileTooLargeError
│                             ├── UnsupportedFormatError
│                             ├── HandlerError
│                             ├── VersioningError
│                             ├── ConcurrencyError
│                             └── ValidationError
├── pathguard.py            PathGuard + ResolvedPath. Sandbox enforcement.
├── versioning.py           VersionStore. SQLite index + COW snapshots.
├── audit.py                AuditLogger. JSONL append-only.
├── cli.py                  dokumen-pintar-init bootstrap.
│
├── handlers/
│   ├── base.py             FormatHandler protocol, HandlerCapability flags,
│   │                       HandlerRegistry, default_registry singleton.
│   ├── text_handler.py     Plain text / Markdown / source code (33 ext).
│   ├── json_yaml_handler.py JsonHandler + YamlHandler (ruamel round-trip).
│   ├── csv_handler.py      CsvHandler dengan dialect detection.
│   ├── xml_handler.py      XmlHandler dengan XPath (lxml, XXE-safe).
│   ├── docx_handler.py     DocxHandler (python-docx).
│   ├── xlsx_handler.py     XlsxHandler (openpyxl).
│   ├── pptx_handler.py     PptxHandler (python-pptx).
│   └── pdf_handler.py      PdfHandler (pdfplumber + pypdf + pikepdf).
│
├── tools/
│   ├── _common.py          resolve_for_read/write, handler_for, summarize_resolved.
│   ├── workspace.py        3 tools: list_roots, stat, tree.
│   ├── file_crud.py        5 tools: create, delete, rename, move, copy.
│   ├── content_crud.py     7 tools: read, write, append, insert, replace,
│   │                       delete_range, patch.
│   ├── structured.py       4 tools: get, set, delete, meta.
│   ├── search.py           3 base tools (filename, content, in_format)
│   │                       + 3 opsional semantic tools.
│   ├── batch.py            3 tools: rename, replace_content, delete (dry-run default).
│   └── version.py          5 tools: list, diff, restore, undo, purge.
│
├── semantic/
│   ├── __init__.py
│   └── index.py            SemanticIndex (sentence-transformers + SQLite vectors).
│                           Lazy-loaded; tidak load model kalau enabled=false.
│
└── utils/
    ├── encoding.py         detect_encoding (charset-normalizer), read_text, write_text.
    ├── globbing.py         compile_globs + any_match (handle leading-slash glob).
    ├── locks.py            file_lock context manager (filelock, per-path SHA1).
    └── mime.py             detect_format by extension + magic bytes fallback.
```

---

## 3. Request Flow (real, end-to-end)

```
                         [MCP Client]  Claude Desktop / Cursor / IDE
                              │
                              │  JSON-RPC 2.0
                              │   ┌──────────────┐
                              ├──▶│   stdio      │   tipikal local
                              │   └──────────────┘
                              │   ┌──────────────┐
                              └──▶│   SSE / HTTP │   multi-client
                                  └──────────────┘
                                      │
                                      ▼
                          ┌─────────────────────────┐
                          │   FastMCP server        │  server.py
                          │   - tool registry       │
                          │   - schema gen          │
                          │   - JSON-RPC dispatch   │
                          └─────────────┬───────────┘
                                        │  call_tool(name, args)
                                        ▼
                          ┌─────────────────────────┐
                          │   tools/<module>.py     │  registered closures
                          │   - validate args       │
                          │   - resolve_for_*()  ───┼──▶ PathGuard.resolve()
                          │                         │     ├ workspace URI parser
                          │                         │     ├ root containment check
                          │                         │     ├ symlink policy
                          │                         │     ├ exclude patterns
                          │                         │     ├ sensitive-file gate
                          │                         │     └ size limit
                          │   - file_lock(target) ──┼──▶ utils/locks.py
                          │   - snapshot(pre) ──────┼──▶ VersionStore
                          │   - dispatch:           │     │ writes COW copy
                          │       handler.X()  ─────┼──▶ HandlerRegistry
                          │                         │     │ for_path(p) → handler
                          │                         │     │ handler.read_text /
                          │                         │     │ structured_get / set /
                          │                         │     │ delete / extract_for_search
                          │   - snapshot(post) ─────┼──▶ VersionStore
                          │   - audit.log()    ─────┼──▶ AuditLogger (JSONL)
                          └─────────────┬───────────┘
                                        │  dict result
                                        ▼
                                  JSON to client
```

**Yang dijamin oleh urutan ini:**

1. Setiap mutasi file selalu `file_lock` → `snapshot pre` → `mutate` → `snapshot post` → `audit`. Ini deterministic, tidak bisa di-bypass tools karena ada di `_common` + tool function.
2. PathGuard run **sebelum** ada I/O. Path invalid = error sebelum lock dipakai.
3. AuditLog jalan **terakhir**, jadi log = bukti operasi sukses (bukan attempt).

---

## 4. Core Contracts

### 4.1 `FormatHandler` protocol (`handlers/base.py`)

Setiap handler mengimplementasikan protocol struktural berikut:

```python
class FormatHandler(Protocol):
    name: str                          # canonical id ("json", "docx", ...)
    extensions: tuple[str, ...]        # lowercase, leading dot
    capabilities: HandlerCapability    # bitwise flags

    def detect(self, path: Path) -> bool: ...
    def read_meta(self, path: Path) -> dict[str, Any]: ...
    def read_text(self, path: Path, **kwargs) -> str: ...
    def write_text(self, path: Path, content: str, **kwargs) -> None: ...
    def extract_for_search(self, path: Path) -> str: ...
    def structured_get(self, path: Path, expr: str) -> Any: ...
    def structured_set(self, path: Path, expr: str, value: Any) -> None: ...
    def structured_delete(self, path: Path, expr: str) -> None: ...
```

**Capability flags** = self-documenting matrix tentang apa yang handler dukung:

```python
class HandlerCapability(Flag):
    READ_TEXT          # bisa konversi ke string
    WRITE_TEXT         # bisa terima string penuh
    STRUCTURED_GET     # support expr-based read
    STRUCTURED_SET     # support expr-based write
    STRUCTURED_DELETE  # support expr-based delete
    LIST_ITEMS         # struktur enumerable
    SEARCH_EXTRACTED   # menyediakan plaintext untuk grep
    BINARY_ONLY        # tidak ada representasi tekstual
```

Method yang tidak didukung MUST raise `UnsupportedFormatError` — tools boleh memeriksa cap flag, tapi handler tetap defensif.

### 4.2 `PathGuard.resolve()` (`pathguard.py`)

Input bentuk:

| Form | Contoh | Resolusi |
|---|---|---|
| Workspace URI | `documents:/notes/q1.md` | Lookup root by name + join |
| Absolute path | `C:/Users/me/Documents/x.txt` | Match against all roots, first wins |
| Relative path | `q1.md` | Try each root; ambiguous → error |

Output: `ResolvedPath(original, absolute, root, root_absolute)` immutable. Setelah ini path sudah aman, semua tools downstream tinggal pakai `.absolute`.

**Properti penting:**

- `resolve()` deterministik, idempotent.
- Tidak melakukan I/O selain `Path.resolve()` (symlink follow + canonicalisation).
- Symlink di-detect setelah resolve, di-block kalau policy bilang demikian.

### 4.3 `VersionStore` (`versioning.py`)

Single class, kontrak:

```python
snapshot(*, root_name, rel_path, source: Path, action: str, note=None) -> dict | None
list_versions(*, root_name, rel_path) -> list[dict]
latest(*, root_name, rel_path) -> dict | None
get(version_id: int) -> dict | None
restore(version_id: int, target: Path) -> dict
purge(*, older_than_days: int | None) -> int
```

Side effect bukan masalah karena snapshots = append-only, dengan SQLite sebagai source-of-truth index. Snapshot file di disk + row di SQLite selalu ditulis dalam transaction yang sama.

**De-dup**: kalau sha256 file == sha256 snapshot terbaru, skip (hindari snapshot identik bertumpuk).

### 4.4 `AppContext` (`context.py`)

Container immutable yang dipassing ke setiap tool registration:

```python
@dataclass
class AppContext:
    config: AppConfig
    guard: PathGuard
    versions: VersionStore
    audit: AuditLogger
    registry: HandlerRegistry
```

Tools menerima `ctx` di registration time (closure), bukan tiap call. Ini bikin tool function clean tanpa global state.

---

## 5. Versioning Model — Decisions & Rationale

### Kenapa bukan git?

| Pendekatan | Pros | Cons | Verdict |
|---|---|---|---|
| **git per root** | Standard tool, cabang penuh | Repo membengkak untuk binary (PDF/XLSX), butuh git ter-install, conflict dengan repo user | ditolak |
| **WAL log** | Compact | Replay kompleks, sulit untuk format non-text | ditolak |
| **COW + SQLite index** | Sederhana, cepat list/restore, format-agnostic | Disk usage linear dengan write count (mitigasi: retention) | dipakai |

### Storage modes

| Mode | Lokasi snapshot | Kapan |
|---|---|---|
| `per_root` | `<root>/.mcpdocs/versions/` | Semua root writable, isolasi clean |
| `global` | `global_storage_path` | Root read-only atau di network drive |
| `flexible` (default) | Per-root, fallback ke global | Mixed read/write roots — opsi paling umum |

### Snapshot pair pattern

Untuk setiap mutasi:

```
T-0:   snapshot(action="op_pre")      ← state sebelum
T-1:   mutate file
T-2:   snapshot(action="op_post")     ← state sesudah
```

Memungkinkan:
- `version_undo` = pakai `_pre` terbaru.
- `version_diff` = bandingkan dua snapshot tanpa decode handler.
- Audit reconstruction: tahu persis state pre/post.

### Retention

`max_versions_per_file` (default 50) + `retention_days` (default 30). `_enforce_retention()` jalan setelah setiap snapshot baru — drop ekor antrian. `version_purge` tool eksplisit untuk cleanup global.

---

## 6. Safety Posture

Empat lapis defense, semua di-enforce di `PathGuard` **sebelum** ada I/O:

### 6.1 Path sandbox

```python
resolved = Path(input).expanduser().resolve()
if resolved == root or root in resolved.parents:
    accept
else:
    raise PathNotAllowedError
```

`resolve()` mem-follow symlink dulu, jadi `<root>/symlink-to-/etc/passwd` akan ter-canonical ke `/etc/passwd` dan langsung gagal containment check.

### 6.2 Symlink policy

`safety.follow_symlinks = false` (default) — `Path.is_symlink()` di-check setelah resolve. Symlink di-block walaupun dia mengarah ke dalam root sendiri. Mitigasi TOCTOU.

### 6.3 Sensitive-file gate

`safety.allow_sensitive = false` (default) — daftar nama file rawan (`.env`, `id_rsa`, `credentials.json`, `.aws`, `.ssh`, dll) di-block by name. Plus prefix-match `.env*` semua di-block. Override per-deployment hanya via config.

### 6.4 Size limits

`max_file_size_mb` (default 100). Setiap read di-cek `path.stat().st_size`. Tools batch/search skip oversized file alih-alih abort total.

### 6.5 Concurrency

`utils/locks.py` per-path advisory lock via `filelock` (cross-platform). Tools yang mutasi acquire dulu, kemudian snapshot+mutate+snapshot+audit, kemudian release. Mencegah:

- Dua tool call di server yang sama saling stomp (multi-client di SSE).
- Snapshot pre/post jadi tidak konsisten karena interleaving.

---

## 7. Tool Layer Anatomy

Tiap modul `tools/*.py` mengikuti pattern yang sama:

```python
def register(mcp: FastMCP, ctx: AppContext) -> None:

    @mcp.tool(name="...", description="...")
    def my_tool(path: str, ...) -> dict[str, Any]:
        resolved = resolve_for_write(ctx, path)        # L3 helper
        with file_lock(resolved.absolute):             # L0 lock
            ctx.versions.snapshot(..., action="X_pre") # L2 snapshot
            handler = handler_for(ctx, ...)            # L3 dispatch
            handler.structured_set(...)                # L1 mutation
            snap = ctx.versions.snapshot(..., action="X_post")
        ctx.audit.log("X", path=...)                   # L2 audit
        return {**summarize_resolved(resolved), "snapshot": snap}
```

Konsekuensi gaya ini:

- **Type-checked**: signature fungsi = JSON schema. Pydantic + FastMCP gen schema otomatis.
- **No hidden state**: semua dependency masuk via `ctx`. Test pakai dummy `AppContext`.
- **Uniform error surface**: `DokumenPintarError` family naik ke FastMCP yang turn ke MCP error response. Tools tidak swallow.

---

## 8. Server Wiring (`server.py`)

```python
def main(argv):
    cfg = load_config(args.config)
    mcp, ctx = _build_server(cfg)

    transport = args.transport or pick_from_config(cfg)
    if transport == "stdio":
        mcp.run("stdio")
    elif transport in ("sse", "http"):
        app = mcp.sse_app() if sse else mcp.streamable_http_app()
        uvicorn.run(app, host, port)
```

**`_build_server`** = single source of truth untuk wiring:

```python
def _build_server(cfg):
    ctx = build_context(cfg)         # context.py — wires guard/versions/audit/registry
    mcp = FastMCP("dokumen-pintar", instructions=...)
    workspace.register(mcp, ctx)
    file_crud.register(mcp, ctx)
    content_crud.register(mcp, ctx)
    structured.register(mcp, ctx)
    search.register(mcp, ctx)
    batch.register(mcp, ctx)
    version.register(mcp, ctx)
    return mcp, ctx
```

Test bisa panggil `_build_server()` tanpa transport, lalu `await mcp.call_tool(...)` langsung — itu pattern yang dipakai di smoke test maupun pytest.

---

## 9. Extension Points

### 9.1 Tambah Format Handler Baru

```python
# src/dokumen_pintar/handlers/parquet_handler.py
from __future__ import annotations
from pathlib import Path
from typing import Any

from .base import HandlerCapability, default_registry
from ..errors import HandlerError, UnsupportedFormatError


class ParquetHandler:
    name = "parquet"
    extensions = (".parquet", ".pq")
    capabilities = (
        HandlerCapability.STRUCTURED_GET
        | HandlerCapability.SEARCH_EXTRACTED
    )

    def detect(self, path: Path) -> bool:
        return path.suffix.lower() in self.extensions

    def read_meta(self, path: Path) -> dict[str, Any]:
        import pyarrow.parquet as pq
        meta = pq.read_metadata(str(path))
        return {
            "format": "parquet",
            "size": path.stat().st_size,
            "mtime": path.stat().st_mtime,
            "rows": meta.num_rows,
            "columns": meta.num_columns,
            "schema": meta.schema.to_arrow_schema().to_string(),
        }

    def read_text(self, path: Path, **_):
        raise UnsupportedFormatError("parquet has no plaintext form")

    def write_text(self, path: Path, content: str, **_):
        raise UnsupportedFormatError("parquet does not support write_text")

    def extract_for_search(self, path: Path) -> str:
        import pyarrow.parquet as pq
        try:
            return pq.read_table(str(path)).to_pandas().to_csv(index=False)
        except Exception:
            return ""

    def structured_get(self, path: Path, expr: str) -> Any:
        import pyarrow.parquet as pq
        table = pq.read_table(str(path))
        if expr == "schema":
            return table.schema.to_string()
        if expr.startswith("col:"):
            col = expr.split(":", 1)[1]
            return table.column(col).to_pylist()
        raise HandlerError(f"unsupported expr: {expr}")

    def structured_set(self, *_args, **_kw):
        raise UnsupportedFormatError("parquet structured_set not implemented")

    def structured_delete(self, *_args, **_kw):
        raise UnsupportedFormatError("parquet structured_delete not implemented")


default_registry.register(ParquetHandler())
```

Lalu di `context.py` `build_context()` tambah:

```python
from .handlers import parquet_handler  # noqa: F401  side-effect register
```

Itu saja. Handler langsung available di `struct_get`, `struct_meta`, `search_in_format`, `search_content`, `workspace_stat`.

### 9.2 Tambah Tool Baru

```python
# src/dokumen_pintar/tools/git_blame.py
from mcp.server.fastmcp import FastMCP
from ..context import AppContext
from ._common import resolve_for_read, summarize_resolved

def register(mcp: FastMCP, ctx: AppContext) -> None:

    @mcp.tool(name="git_blame", description="Show git blame for a file in workspace")
    def git_blame(path: str) -> dict:
        resolved = resolve_for_read(ctx, path)
        import subprocess
        out = subprocess.check_output(
            ["git", "blame", "--porcelain", str(resolved.absolute)],
            cwd=resolved.root_absolute,
        ).decode()
        ctx.audit.log("git_blame", path=str(resolved.absolute))
        return {**summarize_resolved(resolved), "blame": out}
```

Daftarkan di `server._build_server`:

```python
from .tools import git_blame
git_blame.register(mcp, ctx)
```

### 9.3 Tambah Transport Baru

`server.main()` punya cabang `if transport == ...`. Tambah cabang baru, panggil `mcp.<custom>_app()` atau wrap manual via `mcp._mcp_server` low-level handle.

### 9.4 Tambah Error Type Baru

Subclass `DokumenPintarError`. Di tool, raise normal — FastMCP konversi ke MCP error response otomatis.

---

## 10. Decision Log (kenapa pilihan diambil)

| Topik | Pilihan | Alternatif yang ditolak | Alasan |
|---|---|---|---|
| Bahasa | Python 3.10+ | TypeScript / Go / Rust | Ekosistem dokumen Python paling lengkap (python-docx, openpyxl, pdfplumber, ruamel) |
| MCP framework | FastMCP (mcp SDK Anthropic) | Implementasi manual JSON-RPC | First-party, schema gen otomatis, multi-transport built-in |
| Sandbox | Resolve + containment | chroot / namespace | Cross-platform; user-space cukup untuk threat model agent-vs-mistake |
| Versioning | COW + SQLite index | git, append log, fossil | Format-agnostic (binary OK), restore O(1), index queryable |
| YAML | ruamel.yaml | PyYAML | Round-trip preserve comments + ordering |
| XML | lxml + XPath | stdlib ElementTree | Performance + XPath 1.0 lengkap; XXE-safe via parser flag |
| PDF write | metadata only via pikepdf | pdf body manipulation | Body manipulation rapuh (font/encoding); v1 fokus reliable |
| Concurrency | Per-path filelock | Single global lock / lockfree | Multi-client SSE jalan paralel, file-level cukup granular |
| Semantic | sentence-transformers + SQLite vectors | FAISS / Chroma / Qdrant | Zero infra, lazy-loaded, cukup untuk skala personal |
| Config format | JSON | YAML / TOML | JSON Schema-able, no parser dependency |
| Path schema | `<root>:/rel` URI | UNC path / opaque ID | Human-readable, jelas memetakan ke root |

---

## 11. Performance Notes

- **Search**: `_iter_files` rglob lazy; exclude check by compiled regex; stop di `max_files`/`max_results`. Belum pakai ripgrep — tradeoff: portable, pure-Python, ~mid-tier perf.
- **Versioning**: snapshot = file write + 1 INSERT; sub-millisecond untuk file <10MB. SQLite WAL mode, sync=NORMAL.
- **Handler load**: handler self-register di import time, registry adalah dict — O(1) lookup by extension.
- **Semantic**: model load lazy (~2-5s pertama), embed batch~chunks; index pakai numpy dot product (scaling sampai ~100k chunks fine).

---

## 12. Threat Model & Non-Goals

### Yang **DI-DEFENSE**:

- Path traversal (`..`, encoded, symlink)
- Sensitive file read (`.env`, SSH keys)
- Multi-process / multi-tool concurrency
- Oversized file → memory blow-up
- Accidental destructive batch op (dry-run default)

### Yang **TIDAK** di-defense (out-of-scope):

- Adversary dengan akses lokal yang sama dengan server process
- TOCTOU race antara host filesystem & MCP (filelock advisory only)
- Handler library vulnerability (rely on upstream)
- HTTP transport authentication beyond shared bearer token
- DoS via banyak request kecil — rate limit di luar scope MCP

Untuk hardening lebih lanjut: jalankan di container, drop privileges, audit `audit.jsonl`, review `safety.allow_sensitive` setting.

---

## 13. Testing Strategy

48 test di-organize:

- **Unit**: handler-by-handler (text, json/yaml, csv, xml).
- **Integration**: PathGuard sandbox, VersionStore COW + dedup + restore, build_context wiring.
- **Smoke** (manual): boot server, dispatch tools end-to-end via `mcp.call_tool` async.

Tidak ada test yang butuh network. Office/PDF heavy test di-`importorskip` kalau dependency hilang. CSV/XML edge case di-cover.

---

## 14. Future Architecture Work (jika dilanjut)

| Area | Improvement |
|---|---|
| Search | Optional ripgrep wrapper kalau biner ter-detect, untuk 5-10x speedup. |
| Versioning | Compaction: snapshot lama jadi diff terhadap base, hemat disk. |
| Handlers | Streaming read untuk file >100MB (PDF terutama) lewat chunked parser. |
| Transport | WebSocket transport, kalau MCP spec menerima. |
| Auth | Per-tool ACL (read-only token, write token). |
| Observability | OpenTelemetry trace + metrics export. |
| Cluster mode | VersionStore via Postgres untuk multi-node. |

Semua di atas additive — layering saat ini siap menampungnya tanpa breaking change ke tools layer.
