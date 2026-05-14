"""CSV / TSV format handler."""

from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Any

from dokumen_pintar.errors import HandlerError, ValidationError
from dokumen_pintar.handlers.base import (
    FormatHandler,
    HandlerCapability,
    default_registry,
)
from dokumen_pintar.utils.encoding import (
    detect_encoding,
    read_text as _read_text,
    write_text as _write_text,
)

_SAMPLE_BYTES = 8192
_ALLOWED_FORMS = (
    "allowed expressions: 'row:<n>', 'col:<name-or-index>', 'cell:row:<n>,col:<name-or-index>', '*'"
)


def _make_dialect(delimiter: str, quotechar: str = '"') -> type[csv.Dialect]:
    class _D(csv.Dialect):
        pass

    _D.delimiter = delimiter
    _D.quotechar = quotechar
    _D.doublequote = True
    _D.skipinitialspace = False
    _D.lineterminator = "\r\n"
    _D.quoting = csv.QUOTE_MINIMAL
    return _D


class _DetectedDialect:
    __slots__ = (
        "delimiter",
        "quotechar",
        "doublequote",
        "skipinitialspace",
        "lineterminator",
        "quoting",
    )

    def __init__(self, base: Any | None, delimiter: str) -> None:
        self.delimiter = delimiter
        self.quotechar = getattr(base, "quotechar", '"') or '"'
        self.doublequote = bool(getattr(base, "doublequote", True))
        self.skipinitialspace = bool(getattr(base, "skipinitialspace", False))
        self.lineterminator = getattr(base, "lineterminator", "\r\n") or "\r\n"
        self.quoting = int(getattr(base, "quoting", csv.QUOTE_MINIMAL))

    def as_dialect_class(self) -> type[csv.Dialect]:
        class _D(csv.Dialect):
            pass

        _D.delimiter = self.delimiter
        _D.quotechar = self.quotechar
        _D.doublequote = self.doublequote
        _D.skipinitialspace = self.skipinitialspace
        _D.lineterminator = self.lineterminator
        _D.quoting = self.quoting  # type: ignore[assignment]
        return _D


def _detect_dialect(path: Path, sample_text: str) -> tuple[_DetectedDialect, bool]:
    """Return (dialect, has_header)."""
    suffix = path.suffix.lower()
    if suffix == ".tsv":
        return _DetectedDialect(None, "\t"), _sniff_header(sample_text, "\t")

    sniffer = csv.Sniffer()
    delim = ","
    base: Any | None = None
    try:
        base = sniffer.sniff(sample_text, delimiters=",;\t|")
        delim = base.delimiter
    except (csv.Error, ValueError):
        base = None
        delim = ","

    try:
        has_header = sniffer.has_header(sample_text)
    except (csv.Error, ValueError):
        has_header = _sniff_header(sample_text, delim)

    return _DetectedDialect(base, delim), has_header


def _sniff_header(sample_text: str, delim: str) -> bool:
    try:
        return csv.Sniffer().has_header(sample_text)
    except (csv.Error, ValueError):
        # Heuristic: first row entirely non-numeric strings -> header.
        try:
            reader = csv.reader(io.StringIO(sample_text), delimiter=delim)
            first = next(reader, None)
        except (csv.Error, ValueError):
            return False
        if not first:
            return False
        for cell in first:
            cell = cell.strip()
            if not cell:
                return False
            try:
                float(cell)
                return False
            except ValueError:
                continue
        return True


def _read_sample(path: Path) -> tuple[str, str]:  # pragma: no cover
    raw = path.read_bytes()[:_SAMPLE_BYTES]
    enc = detect_encoding(raw)
    return raw.decode(enc, errors="replace"), enc


def _parse_rows(
    path: Path,
) -> tuple[list[str] | None, list[list[str]], _DetectedDialect, str]:
    """Return (header, rows, dialect, encoding). Rows exclude the header row."""
    text, enc = _read_text(path)
    sample = text[:_SAMPLE_BYTES]
    dialect, has_header = _detect_dialect(path, sample)

    reader = csv.reader(io.StringIO(text), dialect=dialect.as_dialect_class())
    all_rows = [list(r) for r in reader]
    if has_header and all_rows:
        header = all_rows[0]
        body = all_rows[1:]
    else:
        header = None
        body = all_rows
    return header, body, dialect, enc


def _write_rows(
    path: Path,
    header: list[str] | None,
    rows: list[list[str]],
    dialect: _DetectedDialect,
    encoding: str,
) -> None:
    buf = io.StringIO(newline="")
    writer = csv.writer(buf, dialect=dialect.as_dialect_class())
    if header is not None:
        writer.writerow(header)
    writer.writerows(rows)
    # Keep detected dialect (delimiter + quoting) and CRLF line terminator.
    _write_text(path, buf.getvalue(), encoding=encoding, newline="")


def _parse_int(value: str, label: str) -> int:
    try:
        return int(value)
    except ValueError as exc:
        raise ValidationError(f"invalid {label} index: {value!r}") from exc


def _resolve_col(col: str, header: list[str] | None, ncols: int) -> int:
    if header is not None:
        if col in header:
            return header.index(col)
        # Allow numeric index against header too.
        try:
            idx = int(col)
        except ValueError as exc:
            raise ValidationError(f"unknown column {col!r}; available: {header!r}") from exc
        if not 0 <= idx < ncols:
            raise ValidationError(f"column index {idx} out of range (0..{ncols - 1})")
        return idx
    idx = _parse_int(col, "column")
    if not 0 <= idx < ncols:
        raise ValidationError(f"column index {idx} out of range (0..{ncols - 1})")
    return idx


def _row_to_obj(row: list[str], header: list[str] | None) -> Any:
    if header is None:
        return list(row)
    # Pad / trim to header length for robustness.
    out: dict[str, str] = {}
    for i, name in enumerate(header):
        out[name] = row[i] if i < len(row) else ""
    return out


def _ncols(header: list[str] | None, rows: list[list[str]]) -> int:
    if header is not None:
        return len(header)
    return max((len(r) for r in rows), default=0)


def _parse_cell_expr(expr: str) -> tuple[str, str]:
    # expr: "cell:row:<n>,col:<x>"
    rest = expr[len("cell:") :]
    parts = rest.split(",", 1)
    if len(parts) != 2:
        raise ValidationError(f"malformed cell expression: {expr!r}")
    row_part, col_part = parts[0].strip(), parts[1].strip()
    if not row_part.startswith("row:") or not col_part.startswith("col:"):
        raise ValidationError(f"malformed cell expression: {expr!r}")
    return row_part[len("row:") :].strip(), col_part[len("col:") :].strip()


class CsvHandler:
    """Handler for CSV / TSV files using the stdlib csv module."""

    name: str = "csv"
    extensions: tuple[str, ...] = (".csv", ".tsv")
    capabilities: HandlerCapability = (
        HandlerCapability.READ_TEXT
        | HandlerCapability.WRITE_TEXT
        | HandlerCapability.STRUCTURED_GET
        | HandlerCapability.STRUCTURED_SET
        | HandlerCapability.STRUCTURED_DELETE
        | HandlerCapability.SEARCH_EXTRACTED
    )

    def detect(self, path: Path) -> bool:
        return path.suffix.lower() in self.extensions

    def read_meta(self, path: Path) -> dict[str, Any]:
        stat = path.stat()
        try:
            header, rows, dialect, _enc = _parse_rows(path)
        except (OSError, csv.Error, ValueError) as exc:
            raise HandlerError(f"failed to read csv metadata: {exc}") from exc

        return {
            "format": self.name,
            "size": stat.st_size,
            "mtime": stat.st_mtime,
            "rows": len(rows),
            "columns": _ncols(header, rows),
            "header": list(header) if header is not None else None,
            "delimiter": dialect.delimiter,
        }

    def read_text(
        self,
        path: Path,
        *,
        encoding: str | None = None,
        auto_detect: bool = True,
        **_: Any,
    ) -> str:
        text, _enc = _read_text(path, encoding=encoding, auto_detect=auto_detect)
        return text

    def write_text(
        self,
        path: Path,
        content: str,
        *,
        encoding: str = "utf-8",
        newline: str = "\n",
        **_: Any,
    ) -> None:
        _write_text(path, content, encoding=encoding, newline=newline)

    def extract_for_search(self, path: Path) -> str:
        try:
            return self.read_text(path)
        except (OSError, UnicodeDecodeError, LookupError, ValueError):
            return ""

    # ------------------------------------------------------------------ get
    def structured_get(self, path: Path, expr: str) -> Any:
        if not isinstance(expr, str) or not expr:
            raise ValidationError(_ALLOWED_FORMS)

        try:
            header, rows, _dialect, _enc = _parse_rows(path)
        except (OSError, csv.Error, ValueError) as exc:
            raise HandlerError(f"failed to parse csv: {exc}") from exc

        ncols = _ncols(header, rows)

        if expr == "*":
            return [_row_to_obj(r, header) for r in rows]

        if expr.startswith("row:"):
            n = _parse_int(expr[len("row:") :].strip(), "row")
            if not 0 <= n < len(rows):
                raise ValidationError(f"row index {n} out of range (0..{len(rows) - 1})")
            return _row_to_obj(rows[n], header)

        if expr.startswith("col:"):
            col_key = expr[len("col:") :].strip()
            idx = _resolve_col(col_key, header, ncols)
            return [r[idx] if idx < len(r) else "" for r in rows]

        if expr.startswith("cell:"):
            row_key, col_key = _parse_cell_expr(expr)
            n = _parse_int(row_key, "row")
            if not 0 <= n < len(rows):
                raise ValidationError(f"row index {n} out of range (0..{len(rows) - 1})")
            idx = _resolve_col(col_key, header, ncols)
            row = rows[n]
            return row[idx] if idx < len(row) else ""

        raise HandlerError(f"unsupported expression {expr!r}; {_ALLOWED_FORMS}")

    # ------------------------------------------------------------------ set
    def structured_set(self, path: Path, expr: str, value: Any) -> None:
        if not isinstance(expr, str) or not expr:
            raise ValidationError(_ALLOWED_FORMS)

        try:
            header, rows, dialect, enc = _parse_rows(path)
        except (OSError, csv.Error, ValueError) as exc:
            raise HandlerError(f"failed to parse csv: {exc}") from exc

        ncols = _ncols(header, rows)

        if expr.startswith("cell:"):
            row_key, col_key = _parse_cell_expr(expr)
            n = _parse_int(row_key, "row")
            if not 0 <= n < len(rows):
                raise ValidationError(f"row index {n} out of range (0..{len(rows) - 1})")
            idx = _resolve_col(col_key, header, ncols)
            if isinstance(value, (list, tuple, dict)):
                raise ValidationError("cell value must be a scalar")
            row = rows[n]
            while len(row) <= idx:
                row.append("")
            row[idx] = "" if value is None else str(value)
            rows[n] = row
            _write_rows(path, header, rows, dialect, enc)
            return

        if expr.startswith("row:"):
            n = _parse_int(expr[len("row:") :].strip(), "row")
            if not 0 <= n < len(rows):
                raise ValidationError(f"row index {n} out of range (0..{len(rows) - 1})")

            if header is not None:
                if not isinstance(value, dict):
                    raise ValidationError("row value must be a dict when header is present")
                new_row = [
                    "" if value.get(name) is None else str(value.get(name, "")) for name in header
                ]
            else:
                if not isinstance(value, (list, tuple)):
                    raise ValidationError("row value must be a list when no header is present")
                if ncols and len(value) != ncols:
                    raise ValidationError(f"row must have {ncols} columns, got {len(value)}")
                new_row = ["" if v is None else str(v) for v in value]

            rows[n] = new_row
            _write_rows(path, header, rows, dialect, enc)
            return

        raise HandlerError(f"unsupported expression {expr!r}; {_ALLOWED_FORMS}")

    # --------------------------------------------------------------- delete
    def structured_delete(self, path: Path, expr: str) -> None:
        if not isinstance(expr, str) or not expr:
            raise ValidationError(_ALLOWED_FORMS)

        try:
            header, rows, dialect, enc = _parse_rows(path)
        except (OSError, csv.Error, ValueError) as exc:
            raise HandlerError(f"failed to parse csv: {exc}") from exc

        ncols = _ncols(header, rows)

        if expr.startswith("row:"):
            n = _parse_int(expr[len("row:") :].strip(), "row")
            if not 0 <= n < len(rows):
                raise ValidationError(f"row index {n} out of range (0..{len(rows) - 1})")
            del rows[n]
            _write_rows(path, header, rows, dialect, enc)
            return

        if expr.startswith("col:"):
            col_key = expr[len("col:") :].strip()
            idx = _resolve_col(col_key, header, ncols)
            new_header: list[str] | None
            if header is not None:
                new_header = [c for i, c in enumerate(header) if i != idx]
            else:
                new_header = None
            new_rows = [[c for i, c in enumerate(r) if i != idx] for r in rows]
            _write_rows(path, new_header, new_rows, dialect, enc)
            return

        raise HandlerError(f"unsupported expression {expr!r}; {_ALLOWED_FORMS}")


# Runtime-checkable protocol sanity assertion + self-registration.
_handler: FormatHandler = CsvHandler()
default_registry.register(_handler)
