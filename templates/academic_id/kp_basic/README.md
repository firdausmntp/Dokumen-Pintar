# KP Basic - Generic Indonesian Kerja Praktik Template

A starter template for Kerja Praktik (KP) reports following the structural conventions of most Indonesian universities. Use it as a skeleton — swap the institution name, jurusan, and any local sectioning rules to match your university's pedoman penulisan.

## Structure

The template lays out the canonical KP report sections expected by the `academic_id_kp` lint preset:

1. **Cover page** with title, name, NIM, jurusan, university, year.
2. **LEMBAR PENGESAHAN** — supervisor / coordinator approval block.
3. **KATA PENGANTAR** — boilerplate prefix.
4. **BAB I PENDAHULUAN** with `1.1 Latar Belakang` and `1.2 Tujuan`.
5. **BAB II PELAKSANAAN** — body of the report.
6. **LOG BOOK** — repeating table populated from the `entries` loop.
7. **DAFTAR PUSTAKA** — references list.

## Render

```python
from dokumen_pintar.tools.templates import register
# (or via MCP tool template_render_named)

mcp_call("template_render_named", {
    "template_id": "academic_id/kp_basic",
    "dst": "kp:/laporan_firdaus.docx",
    "vars": {
        "judul": "Sistem Monitoring SAP",
        "nama": "Firdaus Satrio Utomo",
        "nim": "3337230039",
        "jurusan": "Teknik Informatika",
        "universitas": "Universitas Sultan Ageng Tirtayasa",
        "tahun": "2026",
        "tanggal_pengesahan": "1 Juni 2026"
    }
})
```

After rendering, populate the LOG BOOK table by appending rows in Word, or use the structured tools to add rows programmatically:

```python
mcp_call("struct_set", {
    "path": "kp:/laporan_firdaus.docx",
    "expr": "table:0!row:1",
    "value": ["2 Mei 2026", "Setup environment", ""]
})
```

## Customising

Drop a copy into your own templates directory and edit the DOCX in Word:

```bash
# In an MCP session
template_install("academic_id/kp_basic", "docs:/my_template.docx")
```

The template uses `docxtpl` syntax, so you can:

- Add new `{{ variable }}` placeholders.
- Insert `{% if show_lampiran %}…{% endif %}` blocks for optional sections.
- Replicate the log book table by copying the `{%tr for … %}…{%tr endfor %}` row pattern.

## Lint compatibility

This template passes the `academic_id_kp` preset out of the box (every required heading is present). After rendering, run:

```python
document_lint("kp:/laporan_firdaus.docx", rules="academic_id_kp")
```

You will only see issues for missing content (empty headings if you skip a `vars` value, malformed citations if your `pustaka` doesn't match APA/IEEE).

## Contributing your university's template

PRs welcome. Add a sibling directory under `templates/academic_id/<your_uni>/` containing:

- `template.docx` — the actual template
- `manifest.json` — variables + loops + license
- `README.md` — like this one, describing institution-specific conventions
