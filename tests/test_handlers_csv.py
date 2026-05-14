"""Tests for :class:`dokumen_pintar.handlers.csv_handler.CsvHandler`."""

from __future__ import annotations

from pathlib import Path

import pytest

from dokumen_pintar.handlers.csv_handler import CsvHandler


@pytest.fixture
def handler() -> CsvHandler:
    return CsvHandler()


def _write_comma_csv(path: Path) -> None:
    path.write_text(
        "name,age,city\nalice,30,paris\nbob,25,berlin\ncara,42,tokyo\n",
        encoding="utf-8",
    )


def _write_semicolon_csv(path: Path) -> None:
    path.write_text(
        "name;age;city\nalice;30;paris\nbob;25;berlin\n",
        encoding="utf-8",
    )


def test_detect_comma_dialect(handler: CsvHandler, tmp_path: Path) -> None:
    target = tmp_path / "commas.csv"
    _write_comma_csv(target)
    meta = handler.read_meta(target)
    assert meta["format"] == "csv"
    assert meta["delimiter"] == ","
    assert meta["header"] == ["name", "age", "city"]
    assert meta["rows"] == 3


def test_detect_semicolon_dialect(handler: CsvHandler, tmp_path: Path) -> None:
    target = tmp_path / "semis.csv"
    _write_semicolon_csv(target)
    meta = handler.read_meta(target)
    assert meta["delimiter"] == ";"


def test_structured_get_row_returns_dict_with_header(handler: CsvHandler, tmp_path: Path) -> None:
    target = tmp_path / "people.csv"
    _write_comma_csv(target)
    row0 = handler.structured_get(target, "row:0")
    assert isinstance(row0, dict)
    assert row0 == {"name": "alice", "age": "30", "city": "paris"}


def test_structured_set_cell_mutates(handler: CsvHandler, tmp_path: Path) -> None:
    target = tmp_path / "people.csv"
    _write_comma_csv(target)
    handler.structured_set(target, "cell:row:0,col:name", "xyz")

    row0 = handler.structured_get(target, "row:0")
    assert isinstance(row0, dict)
    assert row0["name"] == "xyz"
    # Others preserved.
    assert row0["age"] == "30"
    assert row0["city"] == "paris"


def test_structured_delete_row_removes_row(handler: CsvHandler, tmp_path: Path) -> None:
    target = tmp_path / "people.csv"
    _write_comma_csv(target)
    meta_before = handler.read_meta(target)
    assert meta_before["rows"] == 3

    handler.structured_delete(target, "row:0")

    meta_after = handler.read_meta(target)
    assert meta_after["rows"] == 2

    new_row0 = handler.structured_get(target, "row:0")
    assert isinstance(new_row0, dict)
    # Original row 1 ("bob") is now row 0.
    assert new_row0["name"] == "bob"


# ── Additional coverage tests ──


def test_detect(handler: CsvHandler) -> None:
    assert handler.detect(Path("data.csv")) is True
    assert handler.detect(Path("data.tsv")) is True
    assert handler.detect(Path("data.txt")) is False


def test_read_text(handler: CsvHandler, tmp_path: Path) -> None:
    target = tmp_path / "r.csv"
    _write_comma_csv(target)
    text = handler.read_text(target)
    assert "alice" in text


def test_write_text_roundtrip(handler: CsvHandler, tmp_path: Path) -> None:
    target = tmp_path / "w.csv"
    handler.write_text(target, "a,b\n1,2\n")
    text = handler.read_text(target)
    assert "a,b" in text


def test_extract_for_search(handler: CsvHandler, tmp_path: Path) -> None:
    target = tmp_path / "s.csv"
    _write_comma_csv(target)
    text = handler.extract_for_search(target)
    assert "alice" in text


def test_extract_for_search_invalid(handler: CsvHandler, tmp_path: Path) -> None:
    target = tmp_path / "bad.csv"
    target.write_bytes(b"\x80\x81\x82")  # invalid encoding
    text = handler.extract_for_search(target)
    assert isinstance(text, str)


def test_tsv_dialect(handler: CsvHandler, tmp_path: Path) -> None:
    target = tmp_path / "data.tsv"
    target.write_text("name\tage\nalice\t30\n", encoding="utf-8")
    meta = handler.read_meta(target)
    assert meta["delimiter"] == "\t"
    assert meta["header"] == ["name", "age"]


def test_structured_get_all(handler: CsvHandler, tmp_path: Path) -> None:
    target = tmp_path / "all.csv"
    _write_comma_csv(target)
    rows = handler.structured_get(target, "*")
    assert isinstance(rows, list)
    assert len(rows) == 3
    assert rows[0]["name"] == "alice"


def test_structured_get_col(handler: CsvHandler, tmp_path: Path) -> None:
    target = tmp_path / "col.csv"
    _write_comma_csv(target)
    ages = handler.structured_get(target, "col:age")
    assert ages == ["30", "25", "42"]


def test_structured_get_col_by_index(handler: CsvHandler, tmp_path: Path) -> None:
    target = tmp_path / "col.csv"
    _write_comma_csv(target)
    names = handler.structured_get(target, "col:0")
    assert names == ["alice", "bob", "cara"]


def test_structured_get_cell(handler: CsvHandler, tmp_path: Path) -> None:
    target = tmp_path / "cell.csv"
    _write_comma_csv(target)
    val = handler.structured_get(target, "cell:row:1,col:city")
    assert val == "berlin"


def test_structured_get_invalid_expr(handler: CsvHandler, tmp_path: Path) -> None:
    target = tmp_path / "inv.csv"
    _write_comma_csv(target)
    with pytest.raises(Exception):
        handler.structured_get(target, "invalid")


def test_structured_get_row_out_of_range(handler: CsvHandler, tmp_path: Path) -> None:
    target = tmp_path / "oor.csv"
    _write_comma_csv(target)
    with pytest.raises(Exception, match="out of range"):
        handler.structured_get(target, "row:99")


def test_structured_set_row_with_header(handler: CsvHandler, tmp_path: Path) -> None:
    target = tmp_path / "sr.csv"
    _write_comma_csv(target)
    handler.structured_set(target, "row:0", {"name": "zara", "age": "99", "city": "rome"})
    row = handler.structured_get(target, "row:0")
    assert row["name"] == "zara"
    assert row["city"] == "rome"


def test_structured_set_row_invalid(handler: CsvHandler, tmp_path: Path) -> None:
    target = tmp_path / "inv.csv"
    _write_comma_csv(target)
    with pytest.raises(Exception, match="dict"):
        handler.structured_set(target, "row:0", "not a dict")


def test_structured_set_unsupported(handler: CsvHandler, tmp_path: Path) -> None:
    target = tmp_path / "un.csv"
    _write_comma_csv(target)
    with pytest.raises(Exception, match="unsupported"):
        handler.structured_set(target, "invalid_expr", "val")


def test_structured_delete_col(handler: CsvHandler, tmp_path: Path) -> None:
    target = tmp_path / "dc.csv"
    _write_comma_csv(target)
    handler.structured_delete(target, "col:age")
    meta = handler.read_meta(target)
    assert meta["columns"] == 2
    assert "age" not in (meta["header"] or [])


def test_structured_delete_unsupported(handler: CsvHandler, tmp_path: Path) -> None:
    target = tmp_path / "du.csv"
    _write_comma_csv(target)
    with pytest.raises(Exception, match="unsupported"):
        handler.structured_delete(target, "invalid")


def test_no_header_csv(handler: CsvHandler, tmp_path: Path) -> None:
    target = tmp_path / "nohead.csv"
    target.write_text("1,2,3\n4,5,6\n", encoding="utf-8")
    meta = handler.read_meta(target)
    assert meta["header"] is None or isinstance(meta["header"], list)
    rows = handler.structured_get(target, "*")
    assert isinstance(rows, list)


def test_structured_get_empty_expr(handler: CsvHandler, tmp_path: Path) -> None:
    target = tmp_path / "e.csv"
    _write_comma_csv(target)
    with pytest.raises(Exception):
        handler.structured_get(target, "")


def test_structured_set_cell(handler: CsvHandler, tmp_path: Path) -> None:
    target = tmp_path / "sc.csv"
    _write_comma_csv(target)
    handler.structured_set(target, "cell:row:0,col:city", "london")
    val = handler.structured_get(target, "cell:row:0,col:city")
    assert val == "london"


def test_structured_set_cell_value_scalar_check(handler: CsvHandler, tmp_path: Path) -> None:
    target = tmp_path / "scv.csv"
    _write_comma_csv(target)
    with pytest.raises(Exception, match="scalar"):
        handler.structured_set(target, "cell:row:0,col:name", [1, 2])


def test_structured_set_row_no_header(handler: CsvHandler, tmp_path: Path) -> None:
    target = tmp_path / "nohr.csv"
    target.write_text("1,2,3\n4,5,6\n", encoding="utf-8")
    handler.structured_set(target, "row:0", ["7", "8", "9"])
    row = handler.structured_get(target, "row:0")
    # Sniffer may or may not detect header; just check first row got updated
    assert "7" in str(row)


def test_structured_set_row_no_header_wrong_len(handler: CsvHandler, tmp_path: Path) -> None:
    target = tmp_path / "nohrw.csv"
    target.write_text("1,2,3\n4,5,6\n", encoding="utf-8")
    with pytest.raises(Exception, match="columns"):
        handler.structured_set(target, "row:0", ["a", "b"])


def test_structured_set_empty_expr(handler: CsvHandler, tmp_path: Path) -> None:
    target = tmp_path / "se.csv"
    _write_comma_csv(target)
    with pytest.raises(Exception):
        handler.structured_set(target, "", "val")


def test_structured_delete_empty_expr(handler: CsvHandler, tmp_path: Path) -> None:
    target = tmp_path / "de.csv"
    _write_comma_csv(target)
    with pytest.raises(Exception):
        handler.structured_delete(target, "")


def test_structured_set_row_out_of_range(handler: CsvHandler, tmp_path: Path) -> None:
    target = tmp_path / "oor.csv"
    _write_comma_csv(target)
    with pytest.raises(Exception, match="out of range"):
        handler.structured_set(target, "row:99", {"name": "x", "age": "0", "city": "y"})


def test_structured_delete_row_out_of_range(handler: CsvHandler, tmp_path: Path) -> None:
    target = tmp_path / "dor.csv"
    _write_comma_csv(target)
    with pytest.raises(Exception, match="out of range"):
        handler.structured_delete(target, "row:99")


def test_structured_delete_col_no_header(handler: CsvHandler, tmp_path: Path) -> None:
    target = tmp_path / "dcnh.csv"
    target.write_text("1,2,3\n4,5,6\n", encoding="utf-8")
    handler.structured_delete(target, "col:0")
    rows = handler.structured_get(target, "*")
    assert rows[0] == ["2", "3"]


def test_malformed_cell_expr(handler: CsvHandler, tmp_path: Path) -> None:
    target = tmp_path / "mc.csv"
    _write_comma_csv(target)
    with pytest.raises(Exception, match="malformed"):
        handler.structured_get(target, "cell:badformat")


def test_semicolon_structured(handler: CsvHandler, tmp_path: Path) -> None:
    target = tmp_path / "semi.csv"
    _write_semicolon_csv(target)
    all_rows = handler.structured_get(target, "*")
    assert len(all_rows) == 2
    assert all_rows[0]["name"] == "alice"


def test_col_index_out_of_range(handler: CsvHandler, tmp_path: Path) -> None:
    target = tmp_path / "coor.csv"
    _write_comma_csv(target)
    with pytest.raises(Exception, match="out of range"):
        handler.structured_get(target, "col:99")


def test_unknown_column_name(handler: CsvHandler, tmp_path: Path) -> None:
    target = tmp_path / "ucn.csv"
    _write_comma_csv(target)
    with pytest.raises(Exception, match="unknown column"):
        handler.structured_get(target, "col:nonexistent")


# ── More CSV coverage ──

from dokumen_pintar.handlers.csv_handler import (
    _parse_cell_expr,
    _parse_int,
    _resolve_col,
    _row_to_obj,
    _ncols,
    _sniff_header,
)
from dokumen_pintar.errors import ValidationError


def test_parse_cell_expr_valid() -> None:
    r, c = _parse_cell_expr("cell:row:0,col:name")
    assert r == "0"
    assert c == "name"


def test_parse_cell_expr_missing_col() -> None:
    with pytest.raises(ValidationError, match="malformed"):
        _parse_cell_expr("cell:row:0")


def test_parse_cell_expr_bad_prefix() -> None:
    with pytest.raises(ValidationError, match="malformed"):
        _parse_cell_expr("cell:foo:0,bar:1")


def test_parse_int_valid() -> None:
    assert _parse_int("5", "test") == 5


def test_parse_int_invalid() -> None:
    with pytest.raises(ValidationError, match="invalid"):
        _parse_int("abc", "test")


def test_resolve_col_no_header() -> None:
    assert _resolve_col("1", None, 3) == 1


def test_resolve_col_no_header_oor() -> None:
    with pytest.raises(ValidationError, match="out of range"):
        _resolve_col("5", None, 3)


def test_row_to_obj_no_header() -> None:
    assert _row_to_obj(["a", "b"], None) == ["a", "b"]


def test_row_to_obj_with_header_short_row() -> None:
    result = _row_to_obj(["val"], ["col1", "col2"])
    assert result == {"col1": "val", "col2": ""}


def test_ncols_no_header_empty() -> None:
    assert _ncols(None, []) == 0


def test_ncols_with_header() -> None:
    assert _ncols(["a", "b", "c"], []) == 3


def test_sniff_header_numeric_first_row() -> None:
    result = _sniff_header("1,2,3\n4,5,6\n", ",")
    assert result is False


def test_sniff_header_string_first_row() -> None:
    result = _sniff_header("name,age,city\nalice,30,paris\n", ",")
    assert result is True


def test_sniff_header_empty() -> None:
    result = _sniff_header("", ",")
    assert result is False


def test_structured_set_cell_none_value(handler: CsvHandler, tmp_path: Path) -> None:
    target = tmp_path / "none.csv"
    _write_comma_csv(target)
    handler.structured_set(target, "cell:row:0,col:name", None)
    val = handler.structured_get(target, "cell:row:0,col:name")
    assert val == ""


def test_structured_set_cell_out_of_range(handler: CsvHandler, tmp_path: Path) -> None:
    target = tmp_path / "scoor.csv"
    _write_comma_csv(target)
    with pytest.raises(Exception, match="out of range"):
        handler.structured_set(target, "cell:row:99,col:name", "x")


# ── CSV dialect detection and write coverage ──

from dokumen_pintar.handlers.csv_handler import (
    _make_dialect,
    _detect_dialect,
    _DetectedDialect,
)


def test_make_dialect() -> None:
    import csv
    D = _make_dialect(";", "'")
    assert D.delimiter == ";"
    assert D.quotechar == "'"
    assert D.quoting == csv.QUOTE_MINIMAL


def test_detected_dialect_as_class() -> None:
    dd = _DetectedDialect(None, "\t")
    cls = dd.as_dialect_class()
    assert cls.delimiter == "\t"
    assert cls.quotechar == '"'


def test_detect_dialect_tsv(tmp_path: Path) -> None:
    target = tmp_path / "test.tsv"
    target.write_text("a\tb\n1\t2\n", encoding="utf-8")
    dd, has_h = _detect_dialect(target, "a\tb\n1\t2\n")
    assert dd.delimiter == "\t"


def test_detect_dialect_semicolon(tmp_path: Path) -> None:
    target = tmp_path / "test.csv"
    sample = "a;b;c\n1;2;3\n4;5;6\n7;8;9\n10;11;12\n"
    target.write_text(sample, encoding="utf-8")
    dd, _ = _detect_dialect(target, sample)
    assert dd.delimiter == ";"


def test_detect_dialect_sniff_error(tmp_path: Path) -> None:
    target = tmp_path / "test.csv"
    # Single character with no clear delimiter
    sample = "x"
    dd, _ = _detect_dialect(target, sample)
    assert dd.delimiter == ","


def test_structured_set_row_with_header(handler: CsvHandler, tmp_path: Path) -> None:
    target = tmp_path / "srh.csv"
    _write_comma_csv(target)
    handler.structured_set(target, "row:0", {"name": "new_name", "age": "99", "city": "NYC"})
    row = handler.structured_get(target, "row:0")
    assert row["name"] == "new_name"
    assert row["age"] == "99"


def test_structured_delete_row(handler: CsvHandler, tmp_path: Path) -> None:
    target = tmp_path / "dr.csv"
    _write_comma_csv(target)
    handler.structured_delete(target, "row:0")
    rows = handler.structured_get(target, "*")
    assert len(rows) == 2  # Was 3 rows, now 2


def test_structured_delete_col_by_name(handler: CsvHandler, tmp_path: Path) -> None:
    target = tmp_path / "dcn.csv"
    _write_comma_csv(target)
    handler.structured_delete(target, "col:age")
    # After deletion, file should not contain age values in first row
    row = handler.structured_get(target, "row:0")
    if isinstance(row, dict):
        assert "age" not in row
    else:
        # 3 cols → 2 cols
        assert len(row) == 2


def test_write_text_preserves_content(handler: CsvHandler, tmp_path: Path) -> None:
    target = tmp_path / "wt.csv"
    content = "a,b,c\n1,2,3\n"
    handler.write_text(target, content)
    assert target.read_text(encoding="utf-8") == content


def test_structured_set_col_invalid_expr(handler: CsvHandler, tmp_path: Path) -> None:
    target = tmp_path / "ice.csv"
    _write_comma_csv(target)
    with pytest.raises(Exception):
        handler.structured_set(target, "invalid_expr", "val")


# ── Additional CSV coverage tests ──

from dokumen_pintar.errors import HandlerError, ValidationError


def test_read_meta_parse_error(handler: CsvHandler, tmp_path: Path) -> None:
    from unittest.mock import patch
    target = tmp_path / "bad.csv"
    target.write_text("a,b,c\n1,2,3\n", encoding="utf-8")
    with patch("dokumen_pintar.handlers.csv_handler._parse_rows", side_effect=OSError("fail")):
        with pytest.raises(HandlerError, match="failed to read csv metadata"):
            handler.read_meta(target)


def test_extract_for_search_oserror(handler: CsvHandler, tmp_path: Path) -> None:
    target = tmp_path / "gone.csv"
    result = handler.extract_for_search(target)
    assert result == ""


def test_structured_get_parse_error(handler: CsvHandler, tmp_path: Path) -> None:
    from unittest.mock import patch
    target = tmp_path / "badget.csv"
    target.write_text("a,b\n1,2\n", encoding="utf-8")
    with patch("dokumen_pintar.handlers.csv_handler._parse_rows", side_effect=OSError("fail")):
        with pytest.raises(HandlerError, match="failed to parse csv"):
            handler.structured_get(target, "*")


def test_structured_set_parse_error(handler: CsvHandler, tmp_path: Path) -> None:
    from unittest.mock import patch
    target = tmp_path / "badset.csv"
    target.write_text("a,b\n1,2\n", encoding="utf-8")
    with patch("dokumen_pintar.handlers.csv_handler._parse_rows", side_effect=OSError("fail")):
        with pytest.raises(HandlerError, match="failed to parse csv"):
            handler.structured_set(target, "cell:0,0", "x")


def test_structured_delete_parse_error(handler: CsvHandler, tmp_path: Path) -> None:
    from unittest.mock import patch
    target = tmp_path / "baddel.csv"
    target.write_text("a,b\n1,2\n", encoding="utf-8")
    with patch("dokumen_pintar.handlers.csv_handler._parse_rows", side_effect=OSError("fail")):
        with pytest.raises(HandlerError, match="failed to parse csv"):
            handler.structured_delete(target, "row:0")


def test_structured_get_cell_out_of_range(handler: CsvHandler, tmp_path: Path) -> None:
    target = tmp_path / "oor.csv"
    target.write_text("a,b\n1,2\n", encoding="utf-8")
    with pytest.raises(ValidationError, match="out of range"):
        handler.structured_get(target, "cell:row:99,col:a")


def test_structured_set_cell_extend_row(handler: CsvHandler, tmp_path: Path) -> None:
    target = tmp_path / "ext.csv"
    # Row 0 has only 1 column, but header says 3 → col:2 is valid but row is short
    target.write_text("a,b,c\n1\n", encoding="utf-8")
    handler.structured_set(target, "cell:row:0,col:2", "extended")
    result = handler.structured_get(target, "cell:row:0,col:2")
    assert result == "extended"


def test_structured_set_row_no_header_list(handler: CsvHandler, tmp_path: Path) -> None:
    target = tmp_path / "nohdr.csv"
    target.write_text("1,2,3\n4,5,6\n", encoding="utf-8")
    # No header CSV → row set requires list
    handler.structured_set(target, "row:0", ["a", "b", "c"])
    result = handler.structured_get(target, "row:0")
    assert isinstance(result, (list, dict))


def test_structured_set_row_no_header_wrong_type(handler: CsvHandler, tmp_path: Path) -> None:
    target = tmp_path / "nohdr2.csv"
    target.write_text("1,2,3\n4,5,6\n", encoding="utf-8")
    with pytest.raises(ValidationError, match="list"):
        handler.structured_set(target, "row:0", "not_a_list")


def test_sniff_header_heuristic(tmp_path: Path) -> None:
    import csv
    from dokumen_pintar.handlers.csv_handler import _sniff_header
    from unittest.mock import patch
    # Force Sniffer to fail so heuristic kicks in
    with patch.object(csv.Sniffer, "has_header", side_effect=csv.Error("force")):
        # All string first row → header
        assert _sniff_header("name,city\nalice,paris\n", ",") is True
        # Numeric first row → no header
        assert _sniff_header("1,2\n3,4\n", ",") is False
        # Empty cell → no header
        assert _sniff_header(",city\nalice,paris\n", ",") is False
        # Empty first row → no header
        assert _sniff_header("", ",") is False


def test_sniff_header_reader_error(tmp_path: Path) -> None:
    import csv
    from dokumen_pintar.handlers.csv_handler import _sniff_header
    from unittest.mock import patch
    with patch.object(csv.Sniffer, "has_header", side_effect=csv.Error("force")):
        with patch("csv.reader", side_effect=csv.Error("reader fail")):
            assert _sniff_header("a,b\n1,2\n", ",") is False


def test_sniff_has_header_csv_error(tmp_path: Path) -> None:
    from unittest.mock import patch
    import csv
    from dokumen_pintar.handlers.csv_handler import _detect_dialect
    target = tmp_path / "sniff_err.csv"
    target.write_text("a,b,c\n1,2,3\n", encoding="utf-8")
    with patch.object(csv.Sniffer, "has_header", side_effect=csv.Error("sniff fail")):
        _dialect, has_hdr = _detect_dialect(target, "a,b,c\n1,2,3\n")
    assert isinstance(has_hdr, bool)
