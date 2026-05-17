# Configuration Profiles

Pre-tuned configs for common scenarios. Pick the one that matches your workflow, copy it to your project root as `dokumen-pintar.config.json`, edit the `roots` paths, and you're ready.

## How to use a profile

```bash
# Copy a profile into the project root and rename it
cp docs/profiles/personal.json ./dokumen-pintar.config.json

# Edit the roots to point at your real folders
# (open in your editor of choice)

# Run with the new config
dokumen-pintar --config dokumen-pintar.config.json

# Verify health
dokumen-pintar-doctor --config dokumen-pintar.config.json
```

The `_profile` and `_description` keys at the top of every profile are decorative - the server ignores unknown root-level keys that start with `_`. You can keep them as labels or strip them out.

## Pick a profile

| Profile | Best for | Key trade-offs |
|:--------|:---------|:---------------|
| [`minimal.json`](minimal.json) | First-time users, one-off sessions | Defaults everywhere; one writable root |
| [`personal.json`](personal.json) | Daily desktop use across documents + projects | Versioning + audit; 30-day retention |
| [`developer.json`](developer.json) | Coding sessions with notes/scratch | Aggressive excludes for build artefacts; 14-day retention |
| [`research.json`](research.json) | Big PDFs, papers, thesis libraries | Long retention (180d); semantic search on; 250 MB limit |
| [`read-only.json`](read-only.json) | Browsing a shared reference library | All roots non-writable; versioning off |
| [`team-server.json`](team-server.json) | Multi-client HTTP server behind a proxy | Bearer auth required; global snapshot storage |

## Editing tips

### Make the `$schema` reference work in your editor

Every profile starts with:

```json
"$schema": "../config.schema.json"
```

When you copy the profile into your project root, change the path so it points at the schema in the cloned repo, or use the absolute URL:

```json
"$schema": "./docs/config.schema.json"
```

```json
"$schema": "https://raw.githubusercontent.com/firdausmntp/Dokumen-Pintar/main/docs/config.schema.json"
```

VS Code, Cursor, IntelliJ, and Zed all use this for autocomplete + inline validation. You'll get descriptions on hover for every field and a red squiggle on typos.

### `roots` is the only required field

Every other section has a sensible default. Strip what you don't need - profiles deliberately spell things out for clarity, not because the keys are required.

```jsonc
// This is a complete, valid config.
{ "roots": [{ "name": "docs", "path": "~/Documents", "writable": true }] }
```

### Tune `exclude_patterns` based on what's in your roots

Excludes are matched against the **relative posix path** within a root. Always wrap directory names in `**/...` or `.../**`:

```jsonc
// Wrong - this only matches a top-level file literally named "node_modules"
"exclude_patterns": ["node_modules"]

// Right - matches any node_modules dir at any depth
"exclude_patterns": ["**/node_modules/**"]
```

A handy starter set lives in [`developer.json`](developer.json) - dev cruft for most ecosystems.

### `max_file_size_mb` applies to compressed size

DOCX/XLSX/PPTX are ZIP archives internally. The limit applies to bytes on disk, not extracted text. A 50 MB DOCX with embedded images can decompress to several hundred MB of XML. Bump the limit if you hit `FileTooLargeError` on legitimately large research PDFs.

### Versioning storage trade-off

| Mode       | Where snapshots go | When to pick |
|:-----------|:-------------------|:-------------|
| `per_root` | Inside each root, under `.mcpdocs/versions/` | You sync roots between machines and want history to travel along |
| `global`   | One shared dir on local disk | Roots are read-only, or you want to keep your project dirs clean |
| `flexible` | per_root if writable, else global | Default. Best for mixed read/write multi-root setups |

The SQLite **index** lives in `global_storage_path` regardless of mode - moving snapshot files between machines without the index file means `version_list` returns nothing on the destination.

### Retention vs disk space

```
disk_used ~= sum(file_sizes_at_each_snapshot) ~= avg_file_size * retention_days * mutations_per_day
```

For a workspace with 500 MB of churn per day and a 30-day retention, expect ~15 GB of snapshots. Reduce `max_versions_per_file` first (it caps per-file blowup), then `retention_days` if disk pressure remains.

### HTTP transport hardening (when you must)

`team-server.json` is the only profile that turns HTTP on. **Never expose port 7878 directly** - put it behind:

- Caddy / nginx / Traefik with TLS
- Tailscale / Cloudflare Tunnel for zero-port-forwarding setups
- A WireGuard / VPN where only known peers can reach it

Generate a strong `auth_token`:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Or with `openssl`:

```bash
openssl rand -base64 36
```

If you set `host` to anything other than `127.0.0.1`, the server is reachable from the network and **the `auth_token` is the only thing between callers and your files**.

### Semantic search is optional and slow on first run

Enabling it pulls in `sentence-transformers` and downloads the embedding model (~80 MB for the default `all-MiniLM-L6-v2`). The first call to `semantic_index_path` per file pays the embedding cost. After that it's a fast vector lookup.

```bash
pip install dokumen-pintar[semantic]
```

If you don't actually need semantic search, leave it disabled - the dependency footprint is significantly larger.

### Sensitive files are blocked by default

`safety.allow_sensitive: false` blocks `.env`, `id_rsa`, `.netrc`, `credentials.json`, and a handful of similar paths even when they sit inside a configured root. If you legitimately need to read or rewrite these (devops automation, secret rotation), flip the flag and audit the resulting `audit.jsonl` regularly.

## Combining profiles with CLI overrides

Profiles are starting points. You can override roots without editing the file:

```bash
# Use the personal profile but mount a scratch dir for this session only
dokumen-pintar --config docs/profiles/personal.json --root tmp:/tmp/scratch

# Force the entire personal profile read-only for a quick browsing session
dokumen-pintar --config docs/profiles/personal.json --read-only

# Promote the team-server profile to a different port
dokumen-pintar --config docs/profiles/team-server.json --port 9090
```

CLI overrides win against the file, in the order: `--read-only` > `--root` > config file.

## What makes a config "effective"

A few rules of thumb based on what people actually trip over:

1. **One writable root per concern.** Don't mount one giant `~/` and rely on excludes. Mount the directories you actually edit.
2. **Read-only the rest.** Reference material, archives, vendored libraries - all `writable: false`. The path guard cannot be defeated by a typo this way.
3. **Tune excludes to your churn.** A python+node monorepo regenerates `__pycache__/` on every test run; without the exclude, `search_content` re-walks all of it on every call.
4. **Keep `max_file_size_mb` honest.** The default 100 MB is generous. Lower it for code-only setups (25 MB is plenty); raise it for research workloads.
5. **Audit + versioning are cheap insurance.** Leave them on unless you have a hard reason. They cost milliseconds per write and save hours when an agent does something unexpected.
6. **Snapshot retention isn't free.** If you're seeing the snapshot store balloon, drop `retention_days` before disabling versioning entirely.
7. **Restart matters.** Config changes take effect on next launch - the server caches paths and roots at startup.

If you're unsure which profile to start from, use `personal.json` and edit the roots. It's the closest to "sensible defaults for one human on a laptop."
