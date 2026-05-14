"""PDF format handler backed by pypdf, pdfplumber, and pikepdf.

Page numbers in the public API are **0-based** (e.g. ``"page:0"`` is the first
page). Text replacement inside a PDF body is intentionally out of scope for
v1 - use the PDF-specific tools for that.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pdfplumber
import pikepdf
import pypdf
from pypdf.errors import PdfReadError

from dokumen_pintar.errors import HandlerError, UnsupportedFormatError
from dokumen_pintar.handlers.base import (
    FormatHandler,
    HandlerCapability,
    default_registry,
)


# ---------------------------------------------------------------- helpers ----
def _to_str(value: Any) -> str | None:
    """Best-effort stringify of PDF metadata values (pypdf returns varied types)."""
    if value is None:
        return None
    try:
        return str(value)
    except Exception:  # pragma: no cover - defensive
        return None


def _parse_page_expr(expr: str) -> int:
    """Parse ``"page:<n>"`` → int. Raises HandlerError on malformed input."""
    if not expr.startswith("page:"):
        raise HandlerError(f"expected 'page:<n>', got '{expr}'")
    raw = expr[len("page:") :].strip()
    try:
        idx = int(raw)
    except ValueError as exc:
        raise HandlerError(f"invalid page index '{raw}'") from exc
    if idx < 0:
        raise HandlerError(f"page index must be >= 0, got {idx}")
    return idx


def _open_reader(path: Path) -> pypdf.PdfReader:
    try:
        reader = pypdf.PdfReader(str(path))
    except PdfReadError as exc:
        raise HandlerError(f"invalid PDF: {exc}") from exc
    except OSError as exc:
        raise HandlerError(f"cannot read PDF: {exc}") from exc
    if reader.is_encrypted:
        # Try empty-password decrypt; many PDFs are flagged encrypted but openable.
        try:
            ok = reader.decrypt("")
        except Exception:  # pypdf raises various types on bad decrypt
            ok = 0
        if not ok:
            raise HandlerError(
                "PDF is encrypted and requires a password; decryption is not supported"
            )
    return reader


def _flatten_outline(items: Any, reader: pypdf.PdfReader) -> list[dict[str, Any]]:
    """Flatten pypdf's nested outline list into ``[{title, page}, ...]``."""
    out: list[dict[str, Any]] = []
    if not items:
        return out
    for item in items:
        if isinstance(item, list):
            out.extend(_flatten_outline(item, reader))
            continue
        title = getattr(item, "title", None) or ""
        page_num: int | None = None
        try:
            page_num = reader.get_destination_page_number(item)
        except Exception:
            page_num = None
        out.append({"title": str(title), "page": page_num})
    return out


# ---------------------------------------------------------------- handler ----
class PdfHandler:
    """Handler for PDF documents.

    Public API uses **0-based** page indices (e.g. ``structured_get(p, "page:0")``
    returns the first page's text).
    """

    name: str = "pdf"
    extensions: tuple[str, ...] = (".pdf",)
    capabilities: HandlerCapability = (
        HandlerCapability.READ_TEXT
        | HandlerCapability.STRUCTURED_GET
        | HandlerCapability.STRUCTURED_SET
        | HandlerCapability.STRUCTURED_DELETE
        | HandlerCapability.SEARCH_EXTRACTED
    )

    # ------------------------------------------------------------ basics
    def detect(self, path: Path) -> bool:
        return path.suffix.lower() in self.extensions

    # -------------------------------------------------------------- meta
    def read_meta(self, path: Path) -> dict[str, Any]:
        stat = path.stat()
        try:
            reader = pypdf.PdfReader(str(path))
        except PdfReadError as exc:
            raise HandlerError(f"invalid PDF: {exc}") from exc
        except OSError as exc:
            raise HandlerError(f"cannot read PDF: {exc}") from exc

        encrypted = bool(reader.is_encrypted)
        # Try empty-password decrypt so we can still count pages / read docinfo.
        if encrypted:
            try:
                reader.decrypt("")
            except Exception:
                pass

        pages: int | None
        try:
            pages = len(reader.pages)
        except Exception:
            pages = None

        info = getattr(reader, "metadata", None) or {}
        metadata = {
            "title": _to_str(info.get("/Title")) if info else None,
            "author": _to_str(info.get("/Author")) if info else None,
            "subject": _to_str(info.get("/Subject")) if info else None,
            "creator": _to_str(info.get("/Creator")) if info else None,
            "producer": _to_str(info.get("/Producer")) if info else None,
            "creation_date": _to_str(info.get("/CreationDate")) if info else None,
            "modification_date": _to_str(info.get("/ModDate")) if info else None,
        }

        pdf_version: str | None = None
        try:
            header = getattr(reader, "pdf_header", None)
            if header:
                pdf_version = str(header).lstrip("%").strip()
        except Exception:
            pdf_version = None

        return {
            "format": self.name,
            "size": stat.st_size,
            "mtime": stat.st_mtime,
            "pages": pages,
            "metadata": metadata,
            "encrypted": encrypted,
            "pdf_version": pdf_version,
        }

    # -------------------------------------------------------------- text
    def read_text(self, path: Path, **_: Any) -> str:
        """Extract text from every page with pdfplumber, joined by blank lines."""
        try:
            with pdfplumber.open(str(path)) as pdf:
                parts = [page.extract_text() or "" for page in pdf.pages]
        except PdfReadError as exc:
            raise HandlerError(f"invalid PDF: {exc}") from exc
        except OSError as exc:
            raise HandlerError(f"cannot read PDF: {exc}") from exc
        except Exception as exc:  # pdfplumber wraps many parser errors
            raise HandlerError(f"failed to extract PDF text: {exc}") from exc
        return "\n\n".join(parts)

    def write_text(self, path: Path, content: str, **_: Any) -> None:
        raise UnsupportedFormatError("pdf does not support write_text; use PDF-specific tools")

    def extract_for_search(self, path: Path) -> str:
        """Best-effort text extraction. Returns "" on total failure."""
        # Primary: pdfplumber per-page with individual try/except.
        parts: list[str] = []
        try:
            with pdfplumber.open(str(path)) as pdf:
                for page in pdf.pages:
                    try:
                        parts.append(page.extract_text() or "")
                    except Exception:
                        continue
            if any(parts):  # pragma: no branch
                return "\n\n".join(parts)
        except Exception:
            pass

        # Fallback: pypdf per-page.
        fallback: list[str] = []
        try:
            reader = pypdf.PdfReader(str(path))
            if reader.is_encrypted:
                try:
                    reader.decrypt("")
                except Exception:
                    return ""
            for page in reader.pages:
                try:
                    fallback.append(page.extract_text() or "")
                except Exception:
                    continue
            return "\n\n".join(fallback)
        except Exception:
            return ""

    # -------------------------------------------------------- structured
    def structured_get(self, path: Path, expr: str) -> Any:
        if expr.startswith("page:"):
            idx = _parse_page_expr(expr)
            try:
                with pdfplumber.open(str(path)) as pdf:
                    if idx >= len(pdf.pages):
                        raise HandlerError(
                            f"page index {idx} out of range (pages={len(pdf.pages)})"
                        )
                    return pdf.pages[idx].extract_text() or ""
            except HandlerError:
                raise
            except PdfReadError as exc:
                raise HandlerError(f"invalid PDF: {exc}") from exc
            except OSError as exc:
                raise HandlerError(f"cannot read PDF: {exc}") from exc
            except Exception as exc:
                raise HandlerError(f"failed to read page {idx}: {exc}") from exc

        if expr == "metadata":
            return self.read_meta(path)["metadata"]

        if expr == "pages":
            try:
                with pdfplumber.open(str(path)) as pdf:
                    out: list[dict[str, Any]] = []
                    for i, page in enumerate(pdf.pages):
                        try:
                            text = page.extract_text() or ""
                        except Exception:
                            text = ""
                        first_line = text.split("\n", 1)[0] if text else ""
                        out.append(
                            {
                                "index": i,
                                "char_count": len(text),
                                "first_line": first_line,
                            }
                        )
                    return out
            except PdfReadError as exc:
                raise HandlerError(f"invalid PDF: {exc}") from exc
            except OSError as exc:
                raise HandlerError(f"cannot read PDF: {exc}") from exc
            except Exception as exc:
                raise HandlerError(f"failed to enumerate pages: {exc}") from exc

        if expr == "outline":
            reader = _open_reader(path)
            try:
                outline = reader.outline  # pypdf exposes parsed outline
            except Exception:
                outline = []
            return _flatten_outline(outline, reader)

        raise HandlerError(
            f"unsupported structured_get expression '{expr}' "
            "(expected 'page:<n>', 'metadata', 'pages', or 'outline')"
        )

    def structured_set(self, path: Path, expr: str, value: Any) -> None:
        if expr != "metadata":
            raise UnsupportedFormatError("pdf structured_set only supports metadata")
        if not isinstance(value, dict):
            raise HandlerError("metadata value must be a dict")

        # Map friendly keys to PDF docinfo keys.
        key_map = {
            "title": "/Title",
            "author": "/Author",
            "subject": "/Subject",
            "creator": "/Creator",
            "producer": "/Producer",
            "creation_date": "/CreationDate",
            "modification_date": "/ModDate",
        }
        docinfo_patch: dict[str, str] = {}
        for key, val in value.items():
            if val is None:
                continue
            pdf_key = key_map.get(key, key if str(key).startswith("/") else f"/{key}")
            docinfo_patch[pdf_key] = str(val)

        try:
            with pikepdf.open(str(path), allow_overwriting_input=True) as pdf:
                with pdf.open_metadata(set_pikepdf_as_editor=False) as meta:
                    # open_metadata synchronizes XMP <-> docinfo; direct docinfo
                    # write is still the reliable path for our tests.
                    pass
                # Update docinfo directly.
                for k, v in docinfo_patch.items():
                    pdf.docinfo[pikepdf.Name(k)] = v
                pdf.save(str(path))
        except pikepdf.PasswordError as exc:
            raise HandlerError(
                "PDF is encrypted and requires a password; metadata update aborted"
            ) from exc
        except pikepdf.PdfError as exc:
            raise HandlerError(f"failed to update PDF metadata: {exc}") from exc
        except OSError as exc:
            raise HandlerError(f"cannot write PDF: {exc}") from exc

    def structured_delete(self, path: Path, expr: str) -> None:
        if expr.startswith("page:"):
            idx = _parse_page_expr(expr)
            try:
                reader = pypdf.PdfReader(str(path))
            except PdfReadError as exc:
                raise HandlerError(f"invalid PDF: {exc}") from exc
            except OSError as exc:
                raise HandlerError(f"cannot read PDF: {exc}") from exc
            if reader.is_encrypted:
                try:
                    ok = reader.decrypt("")
                except Exception:
                    ok = 0
                if not ok:  # pragma: no branch
                    raise HandlerError(
                        "PDF is encrypted and requires a password; page delete aborted"
                    )

            total = len(reader.pages)
            if idx >= total:
                raise HandlerError(f"page index {idx} out of range (pages={total})")

            writer = pypdf.PdfWriter()
            for i, page in enumerate(reader.pages):
                if i == idx:
                    continue
                writer.add_page(page)
            try:
                with open(path, "wb") as fh:
                    writer.write(fh)
            except OSError as exc:
                raise HandlerError(f"cannot write PDF: {exc}") from exc
            return

        if expr == "metadata":
            try:
                with pikepdf.open(str(path), allow_overwriting_input=True) as pdf:
                    # Clear every docinfo entry.
                    for key in list(pdf.docinfo.keys()):
                        del pdf.docinfo[key]
                    pdf.save(str(path))
            except pikepdf.PasswordError as exc:
                raise HandlerError(
                    "PDF is encrypted and requires a password; metadata clear aborted"
                ) from exc
            except pikepdf.PdfError as exc:
                raise HandlerError(f"failed to clear PDF metadata: {exc}") from exc
            except OSError as exc:
                raise HandlerError(f"cannot write PDF: {exc}") from exc
            return

        raise HandlerError(
            f"unsupported structured_delete expression '{expr}' (expected 'page:<n>' or 'metadata')"
        )


# Runtime-checkable protocol sanity assertion + registry hookup.
_handler: FormatHandler = PdfHandler()
default_registry.register(_handler)
