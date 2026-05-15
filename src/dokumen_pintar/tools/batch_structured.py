"""Structured (format-aware) batch find/replace for binary container formats.

``batch_replace_content`` deliberately refuses DOCX/XLSX/PPTX because raw
byte-level find/replace would corrupt the ZIP container. This module
provides a *safe* alternative that walks the document's structured content
(paragraphs / table cells / spreadsheet cells / slide text frames) and
writes the modified document back through the format's native writer.

Currently supported: ``.docx``, ``.xlsx``, ``.xlsm``, ``.pptx``.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from ..context import AppContext
from ..errors import UnsupportedFormatError
from ..utils.locks import file_lock
from .batch import _iter_writable_files  # reuse glob iteration


_SUPPORTED_FORMATS = frozenset({"docx", "xlsx", "pptx"})


def _replace_in_docx(
    path: Path, pattern: re.Pattern[str], repl: str, *, apply: bool
) -> tuple[int, list[dict[str, Any]]]:
    from docx import Document

    doc = Document(str(path))
    total = 0
    locations: list[dict[str, Any]] = []

    for idx, para in enumerate(doc.paragraphs):
        if not para.text:
            continue
        new_text, n = pattern.subn(repl, para.text)
        if n > 0:
            total += n
            locations.append({"kind": "paragraph", "index": idx, "matches": n})
            if apply:
                # Replace the entire paragraph text — preserves the
                # paragraph's style; per-run formatting inside is lost
                # (rare for plain text replace, acceptable trade-off).
                for run in list(para.runs):
                    run.text = ""
                if para.runs:
                    para.runs[0].text = new_text
                else:  # pragma: no cover — defensive: a python-docx
                    # paragraph that has text without runs is constructible
                    # only via raw OXML, never via the normal authoring path.
                    para.add_run(new_text)

    for t_idx, table in enumerate(doc.tables):
        for r_idx, row in enumerate(table.rows):
            for c_idx, cell in enumerate(row.cells):
                if not cell.text:
                    continue
                new_text, n = pattern.subn(repl, cell.text)
                if n > 0:
                    total += n
                    locations.append(
                        {
                            "kind": "table_cell",
                            "table": t_idx,
                            "row": r_idx,
                            "col": c_idx,
                            "matches": n,
                        }
                    )
                    if apply:
                        cell.text = new_text

    if apply and total > 0:
        doc.save(str(path))

    return total, locations


def _replace_in_xlsx(
    path: Path, pattern: re.Pattern[str], repl: str, *, apply: bool
) -> tuple[int, list[dict[str, Any]]]:
    import openpyxl

    wb = openpyxl.load_workbook(str(path))
    total = 0
    locations: list[dict[str, Any]] = []
    try:
        for ws in wb.worksheets:
            for row in ws.iter_rows():
                for cell in row:
                    val = cell.value
                    if not isinstance(val, str) or not val:
                        continue
                    new_val, n = pattern.subn(repl, val)
                    if n > 0:
                        total += n
                        locations.append(
                            {
                                "kind": "cell",
                                "sheet": ws.title,
                                "ref": cell.coordinate,
                                "matches": n,
                            }
                        )
                        if apply:
                            cell.value = new_val
        if apply and total > 0:
            wb.save(str(path))
    finally:
        wb.close()

    return total, locations


def _replace_in_pptx(
    path: Path, pattern: re.Pattern[str], repl: str, *, apply: bool
) -> tuple[int, list[dict[str, Any]]]:
    from pptx import Presentation

    prs = Presentation(str(path))
    total = 0
    locations: list[dict[str, Any]] = []

    for s_idx, slide in enumerate(prs.slides):
        for sh_idx, shape in enumerate(slide.shapes):
            tf = getattr(shape, "text_frame", None)
            if tf is None:
                continue
            for p_idx, para in enumerate(tf.paragraphs):
                full_text = "".join(run.text for run in para.runs)
                if not full_text:
                    continue
                new_text, n = pattern.subn(repl, full_text)
                if n > 0:
                    total += n
                    locations.append(
                        {
                            "kind": "slide_text",
                            "slide": s_idx,
                            "shape": sh_idx,
                            "paragraph": p_idx,
                            "matches": n,
                        }
                    )
                    if apply:
                        runs = list(para.runs)
                        for run in runs[1:]:
                            run.text = ""
                        if runs:
                            runs[0].text = new_text
                        else:  # pragma: no cover — defensive: a paragraph
                            # with non-empty .text but zero runs is not
                            # producible via the python-pptx public API.
                            new_run = para.add_run()
                            new_run.text = new_text

    if apply and total > 0:
        prs.save(str(path))

    return total, locations


def register(mcp: FastMCP, ctx: AppContext) -> None:
    @mcp.tool(
        name="batch_replace_structured",
        description=(
            "Format-aware find/replace inside DOCX/XLSX/PPTX files. Walks "
            "paragraphs, table cells, spreadsheet cells, and slide text "
            "frames via the native writer (no raw bytes), so the binary "
            "container stays valid. `regex=False` and `case_sensitive=True` "
            "by default. Always snapshots pre+post when applying."
        ),
    )
    def batch_replace_structured(
        glob: str,
        old: str,
        new: str,
        regex: bool = False,
        dry_run: bool = True,
        case_sensitive: bool = True,
    ) -> dict[str, Any]:
        flags = 0 if case_sensitive else re.IGNORECASE
        pattern = re.compile(old if regex else re.escape(old), flags)

        plan: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []

        for root_name, p, root_abs in _iter_writable_files(ctx, glob):
            uri = f"{root_name}:/{p.relative_to(root_abs).as_posix()}"
            handler = ctx.registry.for_path(p)
            if handler is None or handler.name not in _SUPPORTED_FORMATS:
                skipped.append({"uri": uri, "reason": "format_not_supported"})
                continue

            # Step 1 — always do a no-write pass first so we can pre-snapshot
            # before mutating, and so dry runs are completely side-effect-free.
            try:
                if handler.name == "docx":
                    total, locs = _replace_in_docx(p, pattern, new, apply=False)
                elif handler.name == "xlsx":
                    total, locs = _replace_in_xlsx(p, pattern, new, apply=False)
                else:  # pptx
                    total, locs = _replace_in_pptx(p, pattern, new, apply=False)
            except UnsupportedFormatError:
                raise
            except Exception as exc:  # noqa: BLE001
                skipped.append({"uri": uri, "reason": "render_failed", "error": str(exc)})
                continue

            if total == 0:
                continue

            entry: dict[str, Any] = {
                "uri": uri,
                "absolute": str(p),
                "format": handler.name,
                "replacements": total,
                "locations": locs,
            }
            plan.append(entry)

            if dry_run:
                continue

            rel = p.relative_to(root_abs).as_posix()
            with file_lock(p):
                # Pre-snapshot before mutation so we can roll back.
                try:
                    ctx.versions.snapshot(
                        root_name=root_name,
                        rel_path=rel,
                        source=p,
                        action="batch_replace_structured_pre",
                    )
                except Exception:  # noqa: BLE001
                    pass
                # Step 2 — apply.
                try:
                    if handler.name == "docx":
                        _replace_in_docx(p, pattern, new, apply=True)
                    elif handler.name == "xlsx":
                        _replace_in_xlsx(p, pattern, new, apply=True)
                    else:  # pptx
                        _replace_in_pptx(p, pattern, new, apply=True)
                except Exception as exc:  # noqa: BLE001
                    # Demote planned entry into skipped on apply failure.
                    plan.pop()
                    skipped.append(
                        {"uri": uri, "reason": "apply_failed", "error": str(exc)}
                    )
                    continue
                try:
                    ctx.versions.snapshot(
                        root_name=root_name,
                        rel_path=rel,
                        source=p,
                        action="batch_replace_structured_post",
                    )
                except Exception:  # noqa: BLE001
                    pass
            ctx.audit.log(
                "batch_replace_structured",
                uri=uri,
                format=handler.name,
                replacements=total,
            )

        result: dict[str, Any] = {
            "dry_run": dry_run,
            "count": len(plan),
            "files": plan,
        }
        if skipped:
            result["skipped"] = skipped
            summary: dict[str, int] = {}
            for s in skipped:
                summary[s["reason"]] = summary.get(s["reason"], 0) + 1
            result["skipped_summary"] = summary
        return result
