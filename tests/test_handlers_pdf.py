"""Tests for :class:`dokumen_pintar.handlers.pdf_handler.PdfHandler`."""

from __future__ import annotations

from pathlib import Path

import pytest
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from dokumen_pintar.errors import HandlerError, UnsupportedFormatError
from dokumen_pintar.handlers.pdf_handler import PdfHandler, _parse_page_expr, _flatten_outline


@pytest.fixture
def handler() -> PdfHandler:
    return PdfHandler()


def _create_pdf(path: Path, pages: int = 2) -> None:
    c = canvas.Canvas(str(path), pagesize=A4)
    for i in range(pages):
        c.drawString(72, 700, f"Page {i} content hello world")
        c.showPage()
    c.save()


def test_detect(handler: PdfHandler) -> None:
    assert handler.detect(Path("doc.pdf")) is True
    assert handler.detect(Path("doc.txt")) is False


def test_read_meta(handler: PdfHandler, tmp_path: Path) -> None:
    target = tmp_path / "test.pdf"
    _create_pdf(target, pages=3)
    meta = handler.read_meta(target)
    assert meta["format"] == "pdf"
    assert meta["pages"] == 3
    assert meta["size"] > 0
    assert "metadata" in meta
    assert meta["encrypted"] is False


def test_read_text(handler: PdfHandler, tmp_path: Path) -> None:
    target = tmp_path / "test.pdf"
    _create_pdf(target)
    text = handler.read_text(target)
    assert "Page 0" in text
    assert "Page 1" in text


def test_write_text_raises(handler: PdfHandler, tmp_path: Path) -> None:
    target = tmp_path / "test.pdf"
    _create_pdf(target)
    with pytest.raises(UnsupportedFormatError):
        handler.write_text(target, "content")


def test_extract_for_search(handler: PdfHandler, tmp_path: Path) -> None:
    target = tmp_path / "test.pdf"
    _create_pdf(target)
    text = handler.extract_for_search(target)
    assert isinstance(text, str)
    assert len(text) > 0


def test_structured_get_page(handler: PdfHandler, tmp_path: Path) -> None:
    target = tmp_path / "test.pdf"
    _create_pdf(target, pages=2)
    text = handler.structured_get(target, "page:0")
    assert isinstance(text, str)


def test_structured_get_page_out_of_range(handler: PdfHandler, tmp_path: Path) -> None:
    target = tmp_path / "test.pdf"
    _create_pdf(target, pages=1)
    with pytest.raises(HandlerError, match="out of range"):
        handler.structured_get(target, "page:99")


def test_structured_get_metadata(handler: PdfHandler, tmp_path: Path) -> None:
    target = tmp_path / "test.pdf"
    _create_pdf(target)
    meta = handler.structured_get(target, "metadata")
    assert isinstance(meta, dict)


def test_structured_get_pages(handler: PdfHandler, tmp_path: Path) -> None:
    target = tmp_path / "test.pdf"
    _create_pdf(target, pages=3)
    pages = handler.structured_get(target, "pages")
    assert isinstance(pages, list)
    assert len(pages) == 3
    assert pages[0]["index"] == 0


def test_structured_get_outline(handler: PdfHandler, tmp_path: Path) -> None:
    target = tmp_path / "test.pdf"
    _create_pdf(target)
    outline = handler.structured_get(target, "outline")
    assert isinstance(outline, list)


def test_structured_get_unsupported(handler: PdfHandler, tmp_path: Path) -> None:
    target = tmp_path / "test.pdf"
    _create_pdf(target)
    with pytest.raises(HandlerError, match="unsupported"):
        handler.structured_get(target, "invalid_expr")


def test_structured_set_metadata(handler: PdfHandler, tmp_path: Path) -> None:
    target = tmp_path / "test.pdf"
    _create_pdf(target)
    handler.structured_set(target, "metadata", {"title": "Test Title"})
    meta = handler.structured_get(target, "metadata")
    assert meta["title"] is not None


def test_structured_set_non_metadata_raises(handler: PdfHandler, tmp_path: Path) -> None:
    target = tmp_path / "test.pdf"
    _create_pdf(target)
    with pytest.raises(UnsupportedFormatError):
        handler.structured_set(target, "page:0", "value")


def test_structured_set_metadata_non_dict_raises(handler: PdfHandler, tmp_path: Path) -> None:
    target = tmp_path / "test.pdf"
    _create_pdf(target)
    with pytest.raises(HandlerError, match="dict"):
        handler.structured_set(target, "metadata", "not a dict")


def test_structured_delete_page(handler: PdfHandler, tmp_path: Path) -> None:
    target = tmp_path / "test.pdf"
    _create_pdf(target, pages=3)
    handler.structured_delete(target, "page:1")
    meta = handler.read_meta(target)
    assert meta["pages"] == 2


def test_structured_delete_page_out_of_range(handler: PdfHandler, tmp_path: Path) -> None:
    target = tmp_path / "test.pdf"
    _create_pdf(target, pages=1)
    with pytest.raises(HandlerError, match="out of range"):
        handler.structured_delete(target, "page:99")


def test_structured_delete_metadata(handler: PdfHandler, tmp_path: Path) -> None:
    target = tmp_path / "test.pdf"
    _create_pdf(target)
    handler.structured_delete(target, "metadata")
    # Should succeed without error


def test_structured_delete_unsupported(handler: PdfHandler, tmp_path: Path) -> None:
    target = tmp_path / "test.pdf"
    _create_pdf(target)
    with pytest.raises(HandlerError, match="unsupported"):
        handler.structured_delete(target, "invalid")


def test_parse_page_expr_valid() -> None:
    assert _parse_page_expr("page:0") == 0
    assert _parse_page_expr("page:42") == 42


def test_parse_page_expr_invalid_prefix() -> None:
    with pytest.raises(HandlerError, match="expected"):
        _parse_page_expr("invalid:0")


def test_parse_page_expr_negative() -> None:
    with pytest.raises(HandlerError, match="must be >= 0"):
        _parse_page_expr("page:-1")


def test_parse_page_expr_non_numeric() -> None:
    with pytest.raises(HandlerError, match="invalid"):
        _parse_page_expr("page:abc")


# ── Additional PDF coverage ──

from dokumen_pintar.handlers.pdf_handler import _open_reader, _flatten_outline


def test_open_reader_valid(tmp_path: Path) -> None:
    target = tmp_path / "valid.pdf"
    _create_pdf(target, pages=1)
    reader = _open_reader(target)
    assert len(reader.pages) == 1


def test_open_reader_invalid(tmp_path: Path) -> None:
    target = tmp_path / "bad.pdf"
    target.write_bytes(b"not a pdf")
    with pytest.raises(HandlerError, match="invalid PDF"):
        _open_reader(target)


def test_open_reader_missing(tmp_path: Path) -> None:
    target = tmp_path / "ghost.pdf"
    with pytest.raises(HandlerError, match="cannot read PDF"):
        _open_reader(target)


def test_flatten_outline_empty() -> None:
    assert _flatten_outline(None, None) == []
    assert _flatten_outline([], None) == []


def test_read_meta_with_version(handler: PdfHandler, tmp_path: Path) -> None:
    target = tmp_path / "ver.pdf"
    _create_pdf(target)
    meta = handler.read_meta(target)
    # pdf_version may or may not be set depending on reportlab version
    assert "pdf_version" in meta


def test_read_text_multipage(handler: PdfHandler, tmp_path: Path) -> None:
    target = tmp_path / "mp.pdf"
    _create_pdf(target, pages=3)
    text = handler.read_text(target)
    assert "Page 0" in text
    assert "Page 2" in text


def test_extract_for_search_valid(handler: PdfHandler, tmp_path: Path) -> None:
    target = tmp_path / "sr.pdf"
    _create_pdf(target, pages=2)
    text = handler.extract_for_search(target)
    assert len(text) > 0


def test_extract_for_search_invalid(handler: PdfHandler, tmp_path: Path) -> None:
    target = tmp_path / "badsearch.pdf"
    target.write_bytes(b"not a valid pdf file at all!")
    text = handler.extract_for_search(target)
    assert text == ""


def test_structured_get_pages_info(handler: PdfHandler, tmp_path: Path) -> None:
    target = tmp_path / "pi.pdf"
    _create_pdf(target, pages=2)
    pages = handler.structured_get(target, "pages")
    assert len(pages) == 2
    assert pages[0]["index"] == 0
    assert "char_count" in pages[0]
    assert "first_line" in pages[0]


def test_structured_set_metadata_with_keys(handler: PdfHandler, tmp_path: Path) -> None:
    target = tmp_path / "sm.pdf"
    _create_pdf(target)
    handler.structured_set(target, "metadata", {
        "title": "My PDF",
        "author": "Tester",
        "subject": "Testing",
    })
    meta = handler.structured_get(target, "metadata")
    assert meta["title"] is not None


def test_structured_set_metadata_none_value(handler: PdfHandler, tmp_path: Path) -> None:
    target = tmp_path / "smnone.pdf"
    _create_pdf(target)
    handler.structured_set(target, "metadata", {"title": None, "author": "A"})
    meta = handler.structured_get(target, "metadata")
    assert meta["author"] is not None


def test_structured_set_metadata_custom_key(handler: PdfHandler, tmp_path: Path) -> None:
    target = tmp_path / "smck.pdf"
    _create_pdf(target)
    handler.structured_set(target, "metadata", {"/CustomKey": "CustomValue"})


def test_structured_delete_page_first(handler: PdfHandler, tmp_path: Path) -> None:
    target = tmp_path / "dp.pdf"
    _create_pdf(target, pages=3)
    handler.structured_delete(target, "page:0")
    meta = handler.read_meta(target)
    assert meta["pages"] == 2


def test_structured_delete_metadata_clears(handler: PdfHandler, tmp_path: Path) -> None:
    target = tmp_path / "dm.pdf"
    _create_pdf(target)
    handler.structured_set(target, "metadata", {"title": "Will Be Cleared"})
    handler.structured_delete(target, "metadata")
    # Should succeed without error


def test_read_meta_invalid_pdf(handler: PdfHandler, tmp_path: Path) -> None:
    target = tmp_path / "badmeta.pdf"
    target.write_bytes(b"totally not a pdf")
    with pytest.raises(HandlerError, match="invalid PDF"):
        handler.read_meta(target)


def test_read_text_invalid_pdf(handler: PdfHandler, tmp_path: Path) -> None:
    target = tmp_path / "badread.pdf"
    target.write_bytes(b"this is not pdf data")
    with pytest.raises(HandlerError):
        handler.read_text(target)


def test_structured_get_outline(handler: PdfHandler, tmp_path: Path) -> None:
    target = tmp_path / "outline.pdf"
    _create_pdf(target, pages=2)
    outline = handler.structured_get(target, "outline")
    assert isinstance(outline, list)


def test_structured_get_unsupported(handler: PdfHandler, tmp_path: Path) -> None:
    target = tmp_path / "unsup.pdf"
    _create_pdf(target)
    with pytest.raises(HandlerError, match="unsupported"):
        handler.structured_get(target, "nonsense")


def test_structured_set_non_metadata(handler: PdfHandler, tmp_path: Path) -> None:
    target = tmp_path / "setnm.pdf"
    _create_pdf(target)
    with pytest.raises(UnsupportedFormatError, match="metadata"):
        handler.structured_set(target, "page:0", "value")


def test_structured_set_metadata_not_dict(handler: PdfHandler, tmp_path: Path) -> None:
    target = tmp_path / "setnd.pdf"
    _create_pdf(target)
    with pytest.raises(HandlerError, match="dict"):
        handler.structured_set(target, "metadata", "not a dict")


def test_structured_delete_unsupported(handler: PdfHandler, tmp_path: Path) -> None:
    target = tmp_path / "delunsup.pdf"
    _create_pdf(target)
    with pytest.raises(HandlerError, match="unsupported"):
        handler.structured_delete(target, "nonsense")


def test_structured_delete_page_out_of_range(handler: PdfHandler, tmp_path: Path) -> None:
    target = tmp_path / "deloor.pdf"
    _create_pdf(target, pages=2)
    with pytest.raises(HandlerError, match="out of range"):
        handler.structured_delete(target, "page:99")


def test_structured_get_page_out_of_range(handler: PdfHandler, tmp_path: Path) -> None:
    target = tmp_path / "getoor.pdf"
    _create_pdf(target, pages=1)
    with pytest.raises(HandlerError, match="out of range"):
        handler.structured_get(target, "page:99")


def test_structured_get_page_text(handler: PdfHandler, tmp_path: Path) -> None:
    target = tmp_path / "gpt.pdf"
    _create_pdf(target, pages=2)
    text = handler.structured_get(target, "page:0")
    assert isinstance(text, str)
    assert "Page 0" in text


def test_structured_get_metadata(handler: PdfHandler, tmp_path: Path) -> None:
    target = tmp_path / "gm.pdf"
    _create_pdf(target)
    meta = handler.structured_get(target, "metadata")
    assert isinstance(meta, dict)
    assert "title" in meta


def test_read_meta_metadata_fields(handler: PdfHandler, tmp_path: Path) -> None:
    target = tmp_path / "mf.pdf"
    _create_pdf(target)
    meta = handler.read_meta(target)
    m = meta["metadata"]
    assert "title" in m
    assert "author" in m
    assert "subject" in m
    assert "creator" in m
    assert "producer" in m
    assert "creation_date" in m
    assert "modification_date" in m


def test_structured_delete_page_last(handler: PdfHandler, tmp_path: Path) -> None:
    target = tmp_path / "dpl.pdf"
    _create_pdf(target, pages=2)
    handler.structured_delete(target, "page:1")
    meta = handler.read_meta(target)
    assert meta["pages"] == 1


def test_read_meta_missing_file(handler: PdfHandler, tmp_path: Path) -> None:
    target = tmp_path / "ghost.pdf"
    with pytest.raises((HandlerError, FileNotFoundError)):
        handler.read_meta(target)


def test_structured_set_metadata_friendly_keys(handler: PdfHandler, tmp_path: Path) -> None:
    target = tmp_path / "fk.pdf"
    _create_pdf(target)
    handler.structured_set(target, "metadata", {
        "title": "Test Title",
        "author": "Test Author",
        "creator": "Test Creator",
        "producer": "Test Producer",
        "creation_date": "2024-01-01",
        "modification_date": "2024-12-31",
    })
    meta = handler.structured_get(target, "metadata")
    assert meta["title"] is not None


def test_flatten_outline_nested() -> None:
    # Test with nested list (simulating outline structure)
    from unittest.mock import MagicMock
    reader = MagicMock()
    reader.get_destination_page_number.return_value = 0
    
    item = MagicMock()
    item.title = "Chapter 1"
    nested_item = MagicMock()
    nested_item.title = "Section 1.1"
    
    items = [item, [nested_item]]
    result = _flatten_outline(items, reader)
    assert len(result) == 2
    assert result[0]["title"] == "Chapter 1"
    assert result[1]["title"] == "Section 1.1"


def test_flatten_outline_exception_on_page_number() -> None:
    from unittest.mock import MagicMock
    reader = MagicMock()
    reader.get_destination_page_number.side_effect = Exception("bad")
    
    item = MagicMock()
    item.title = "Bad Item"
    
    result = _flatten_outline([item], reader)
    assert len(result) == 1
    assert result[0]["page"] is None


def test_structured_get_pages_list(handler: PdfHandler, tmp_path: Path) -> None:
    target = tmp_path / "plist.pdf"
    _create_pdf(target, pages=3)
    result = handler.structured_get(target, "pages")
    assert isinstance(result, list)
    assert len(result) == 3
    assert result[0]["index"] == 0
    assert "char_count" in result[0]
    assert "first_line" in result[0]


def test_extract_for_search_valid(handler: PdfHandler, tmp_path: Path) -> None:
    target = tmp_path / "efs.pdf"
    _create_pdf(target, pages=2)
    text = handler.extract_for_search(target)
    assert "Page 0" in text
    assert "Page 1" in text


def test_extract_for_search_invalid(handler: PdfHandler, tmp_path: Path) -> None:
    target = tmp_path / "efsi.pdf"
    target.write_bytes(b"not a pdf")
    text = handler.extract_for_search(target)
    assert text == ""


def test_structured_delete_metadata(handler: PdfHandler, tmp_path: Path) -> None:
    target = tmp_path / "delm.pdf"
    _create_pdf(target)
    handler.structured_set(target, "metadata", {"title": "Temp"})
    handler.structured_delete(target, "metadata")
    meta = handler.structured_get(target, "metadata")
    # After delete, most fields should be cleared
    assert meta.get("title") is None or meta.get("title") == ""


def test_structured_delete_page_first(handler: PdfHandler, tmp_path: Path) -> None:
    target = tmp_path / "dpf.pdf"
    _create_pdf(target, pages=3)
    handler.structured_delete(target, "page:0")
    meta = handler.read_meta(target)
    assert meta["pages"] == 2


def test_read_text_valid(handler: PdfHandler, tmp_path: Path) -> None:
    target = tmp_path / "rtv.pdf"
    _create_pdf(target, pages=2)
    text = handler.read_text(target)
    assert "Page 0" in text
    assert "Page 1" in text


def test_structured_get_page_invalid_pdf(handler: PdfHandler, tmp_path: Path) -> None:
    target = tmp_path / "ip.pdf"
    target.write_bytes(b"not a pdf file")
    with pytest.raises(HandlerError):
        handler.structured_get(target, "page:0")


def test_structured_get_pages_invalid_pdf(handler: PdfHandler, tmp_path: Path) -> None:
    target = tmp_path / "ips.pdf"
    target.write_bytes(b"not a pdf file")
    with pytest.raises(HandlerError):
        handler.structured_get(target, "pages")


def test_structured_delete_page_invalid_pdf(handler: PdfHandler, tmp_path: Path) -> None:
    target = tmp_path / "dip.pdf"
    target.write_bytes(b"not a pdf")
    with pytest.raises(HandlerError):
        handler.structured_delete(target, "page:0")


def test_structured_set_metadata_invalid_pdf(handler: PdfHandler, tmp_path: Path) -> None:
    target = tmp_path / "sip.pdf"
    target.write_bytes(b"not a pdf")
    with pytest.raises(HandlerError):
        handler.structured_set(target, "metadata", {"title": "X"})


def test_structured_delete_metadata_invalid_pdf(handler: PdfHandler, tmp_path: Path) -> None:
    target = tmp_path / "dmi.pdf"
    target.write_bytes(b"not a pdf")
    with pytest.raises(HandlerError):
        handler.structured_delete(target, "metadata")


def test_read_meta_encrypted_pdf_empty_password(handler: PdfHandler, tmp_path: Path) -> None:
    # Create a normal PDF and verify read_meta works (not encrypted)
    target = tmp_path / "enc.pdf"
    _create_pdf(target)
    meta = handler.read_meta(target)
    assert meta["encrypted"] is False


def test_parse_page_expr_non_numeric() -> None:
    with pytest.raises(HandlerError, match="invalid page index"):
        _parse_page_expr("page:abc")


def test_parse_page_expr_negative() -> None:
    with pytest.raises(HandlerError, match="must be >= 0"):
        _parse_page_expr("page:-1")


def test_parse_page_expr_not_page() -> None:
    with pytest.raises(HandlerError, match="expected"):
        _parse_page_expr("notpage:0")


def test_read_text_os_error(handler: PdfHandler, tmp_path: Path) -> None:
    from unittest.mock import patch
    target = tmp_path / "oserr.pdf"
    _create_pdf(target)
    with patch("pdfplumber.open", side_effect=OSError("disk error")):
        with pytest.raises(HandlerError, match="cannot read PDF"):
            handler.read_text(target)


def test_read_text_pdfread_error(handler: PdfHandler, tmp_path: Path) -> None:
    from unittest.mock import patch
    from pypdf.errors import PdfReadError
    target = tmp_path / "prderr.pdf"
    _create_pdf(target)
    with patch("pdfplumber.open", side_effect=PdfReadError("corrupt")):
        with pytest.raises(HandlerError, match="invalid PDF"):
            handler.read_text(target)


def test_extract_for_search_pdfplumber_fails_pypdf_fallback(handler: PdfHandler, tmp_path: Path) -> None:
    from unittest.mock import patch, MagicMock
    target = tmp_path / "fb.pdf"
    _create_pdf(target, pages=1)
    # Make pdfplumber fail so pypdf fallback is used
    with patch("pdfplumber.open", side_effect=Exception("pdfplumber fail")):
        text = handler.extract_for_search(target)
        # pypdf fallback should still extract text
        assert "Page 0" in text


def test_extract_for_search_both_fail(handler: PdfHandler, tmp_path: Path) -> None:
    from unittest.mock import patch
    target = tmp_path / "bothfail.pdf"
    _create_pdf(target)
    with patch("pdfplumber.open", side_effect=Exception("fail1")), \
         patch("pypdf.PdfReader", side_effect=Exception("fail2")):
        text = handler.extract_for_search(target)
        assert text == ""


def test_structured_get_page_os_error(handler: PdfHandler, tmp_path: Path) -> None:
    from unittest.mock import patch
    target = tmp_path / "pgoserr.pdf"
    _create_pdf(target)
    with patch("pdfplumber.open", side_effect=OSError("disk")):
        with pytest.raises(HandlerError, match="cannot read PDF"):
            handler.structured_get(target, "page:0")


def test_structured_get_pages_os_error(handler: PdfHandler, tmp_path: Path) -> None:
    from unittest.mock import patch
    target = tmp_path / "psoserr.pdf"
    _create_pdf(target)
    with patch("pdfplumber.open", side_effect=OSError("disk")):
        with pytest.raises(HandlerError, match="cannot read PDF"):
            handler.structured_get(target, "pages")


def test_open_reader_encrypted_empty_decrypt(handler: PdfHandler, tmp_path: Path) -> None:
    from unittest.mock import patch, MagicMock, PropertyMock
    target = tmp_path / "encr.pdf"
    _create_pdf(target)
    
    mock_reader = MagicMock()
    type(mock_reader).is_encrypted = PropertyMock(return_value=True)
    mock_reader.decrypt.return_value = 1  # success
    mock_reader.outline = []
    
    with patch("pypdf.PdfReader", return_value=mock_reader):
        result = handler.structured_get(target, "outline")
        assert isinstance(result, list)


def test_open_reader_encrypted_fails(handler: PdfHandler, tmp_path: Path) -> None:
    from unittest.mock import patch, MagicMock, PropertyMock
    target = tmp_path / "encfail.pdf"
    _create_pdf(target)
    
    mock_reader = MagicMock()
    type(mock_reader).is_encrypted = PropertyMock(return_value=True)
    mock_reader.decrypt.return_value = 0  # fail
    
    with patch("pypdf.PdfReader", return_value=mock_reader):
        with pytest.raises(HandlerError, match="encrypted"):
            handler.structured_get(target, "outline")


def test_read_meta_encrypted_decrypt_ok(handler: PdfHandler, tmp_path: Path) -> None:
    from unittest.mock import patch, MagicMock, PropertyMock
    target = tmp_path / "encmeta.pdf"
    _create_pdf(target)
    
    mock_reader = MagicMock()
    type(mock_reader).is_encrypted = PropertyMock(return_value=True)
    mock_reader.decrypt.return_value = 1
    mock_reader.pages = [MagicMock()]
    mock_reader.metadata = {}
    mock_reader.pdf_header = "%PDF-1.4"
    
    with patch("pypdf.PdfReader", return_value=mock_reader):
        meta = handler.read_meta(target)
        assert meta["encrypted"] is True
        assert meta["pages"] == 1


def test_structured_delete_page_encrypted_fail(handler: PdfHandler, tmp_path: Path) -> None:
    from unittest.mock import patch, MagicMock, PropertyMock
    target = tmp_path / "dencfail.pdf"
    _create_pdf(target)
    
    mock_reader = MagicMock()
    type(mock_reader).is_encrypted = PropertyMock(return_value=True)
    mock_reader.decrypt.return_value = 0
    
    with patch("pypdf.PdfReader", return_value=mock_reader):
        with pytest.raises(HandlerError, match="encrypted"):
            handler.structured_delete(target, "page:0")


# ── Additional PDF coverage tests ──

def test_open_reader_decrypt_exception(handler: PdfHandler, tmp_path: Path) -> None:
    from unittest.mock import patch, MagicMock, PropertyMock
    target = tmp_path / "decexc.pdf"
    _create_pdf(target)
    mock_reader = MagicMock()
    type(mock_reader).is_encrypted = PropertyMock(return_value=True)
    mock_reader.decrypt.side_effect = Exception("decrypt crash")
    with patch("pypdf.PdfReader", return_value=mock_reader):
        with pytest.raises(HandlerError, match="encrypted"):
            handler.structured_get(target, "outline")


def test_read_meta_oserror(handler: PdfHandler, tmp_path: Path) -> None:
    from unittest.mock import patch
    target = tmp_path / "metaos.pdf"
    _create_pdf(target)
    with patch("pypdf.PdfReader", side_effect=OSError("disk")):
        with pytest.raises(HandlerError, match="cannot read PDF"):
            handler.read_meta(target)


def test_read_meta_decrypt_exception(handler: PdfHandler, tmp_path: Path) -> None:
    from unittest.mock import patch, MagicMock, PropertyMock
    target = tmp_path / "mdecex.pdf"
    _create_pdf(target)
    mock_reader = MagicMock()
    type(mock_reader).is_encrypted = PropertyMock(return_value=True)
    mock_reader.decrypt.side_effect = Exception("bad")
    mock_reader.pages = []
    mock_reader.metadata = {}
    mock_reader.pdf_header = None
    with patch("pypdf.PdfReader", return_value=mock_reader):
        meta = handler.read_meta(target)
        assert meta["encrypted"] is True


def test_read_meta_pages_exception(handler: PdfHandler, tmp_path: Path) -> None:
    from unittest.mock import patch, MagicMock, PropertyMock
    target = tmp_path / "mpgex.pdf"
    _create_pdf(target)
    mock_reader = MagicMock()
    type(mock_reader).is_encrypted = PropertyMock(return_value=False)
    type(mock_reader).pages = PropertyMock(side_effect=Exception("corrupt pages"))
    mock_reader.metadata = {}
    mock_reader.pdf_header = None
    with patch("pypdf.PdfReader", return_value=mock_reader):
        meta = handler.read_meta(target)
        assert meta["pages"] is None


def test_read_meta_pdf_header_exception(handler: PdfHandler, tmp_path: Path) -> None:
    from unittest.mock import patch, MagicMock, PropertyMock
    target = tmp_path / "mhdrex.pdf"
    _create_pdf(target)
    mock_reader = MagicMock()
    type(mock_reader).is_encrypted = PropertyMock(return_value=False)
    mock_reader.pages = [MagicMock()]
    mock_reader.metadata = {}
    type(mock_reader).pdf_header = PropertyMock(side_effect=Exception("no header"))
    with patch("pypdf.PdfReader", return_value=mock_reader):
        meta = handler.read_meta(target)
        assert meta["pdf_version"] is None


def test_extract_for_search_page_exception_continues(handler: PdfHandler, tmp_path: Path) -> None:
    from unittest.mock import patch, MagicMock
    target = tmp_path / "efspe.pdf"
    _create_pdf(target, pages=2)
    mock_pdf = MagicMock()
    page_ok = MagicMock()
    page_ok.extract_text.return_value = "good text"
    page_fail = MagicMock()
    page_fail.extract_text.side_effect = Exception("page fail")
    mock_pdf.pages = [page_fail, page_ok]
    mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
    mock_pdf.__exit__ = MagicMock(return_value=False)
    with patch("pdfplumber.open", return_value=mock_pdf):
        text = handler.extract_for_search(target)
        assert "good text" in text


def test_extract_for_search_encrypted_pypdf_fallback_fails(handler: PdfHandler, tmp_path: Path) -> None:
    from unittest.mock import patch, MagicMock, PropertyMock
    target = tmp_path / "efsef.pdf"
    _create_pdf(target)
    mock_reader = MagicMock()
    type(mock_reader).is_encrypted = PropertyMock(return_value=True)
    mock_reader.decrypt.side_effect = Exception("fail")
    with patch("pdfplumber.open", side_effect=Exception("plumber fail")), \
         patch("pypdf.PdfReader", return_value=mock_reader):
        text = handler.extract_for_search(target)
        assert text == ""


def test_extract_for_search_pypdf_page_exception(handler: PdfHandler, tmp_path: Path) -> None:
    from unittest.mock import patch, MagicMock, PropertyMock
    target = tmp_path / "efspx.pdf"
    _create_pdf(target)
    mock_reader = MagicMock()
    type(mock_reader).is_encrypted = PropertyMock(return_value=False)
    page_bad = MagicMock()
    page_bad.extract_text.side_effect = Exception("extract fail")
    mock_reader.pages = [page_bad]
    with patch("pdfplumber.open", side_effect=Exception("plumber fail")), \
         patch("pypdf.PdfReader", return_value=mock_reader):
        text = handler.extract_for_search(target)
        assert text == ""


def test_structured_get_page_generic_exception(handler: PdfHandler, tmp_path: Path) -> None:
    from unittest.mock import patch, MagicMock
    target = tmp_path / "gpex.pdf"
    _create_pdf(target)
    mock_pdf = MagicMock()
    mock_pdf.pages = [MagicMock()]
    mock_pdf.pages[0].extract_text.side_effect = Exception("weird")
    mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
    mock_pdf.__exit__ = MagicMock(return_value=False)
    with patch("pdfplumber.open", return_value=mock_pdf):
        with pytest.raises(HandlerError, match="failed to read page"):
            handler.structured_get(target, "page:0")


def test_structured_get_pages_generic_exception(handler: PdfHandler, tmp_path: Path) -> None:
    from unittest.mock import patch
    target = tmp_path / "gpsex.pdf"
    _create_pdf(target)
    with patch("pdfplumber.open", side_effect=RuntimeError("bad")):
        with pytest.raises(HandlerError, match="failed to enumerate"):
            handler.structured_get(target, "pages")


def test_structured_get_page_pdfread_error(handler: PdfHandler, tmp_path: Path) -> None:
    from unittest.mock import patch
    from pypdf.errors import PdfReadError
    target = tmp_path / "gpprd.pdf"
    _create_pdf(target)
    with patch("pdfplumber.open", side_effect=PdfReadError("corrupt")):
        with pytest.raises(HandlerError, match="invalid PDF"):
            handler.structured_get(target, "page:0")


def test_structured_get_pages_page_extract_exception(handler: PdfHandler, tmp_path: Path) -> None:
    from unittest.mock import patch, MagicMock
    target = tmp_path / "gpspex.pdf"
    _create_pdf(target)
    mock_pdf = MagicMock()
    page_fail = MagicMock()
    page_fail.extract_text.side_effect = Exception("fail")
    mock_pdf.pages = [page_fail]
    mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
    mock_pdf.__exit__ = MagicMock(return_value=False)
    with patch("pdfplumber.open", return_value=mock_pdf):
        result = handler.structured_get(target, "pages")
        assert result[0]["char_count"] == 0


def test_structured_delete_page_oserror(handler: PdfHandler, tmp_path: Path) -> None:
    from unittest.mock import patch, MagicMock, PropertyMock
    import pypdf
    target = tmp_path / "dposerr.pdf"
    _create_pdf(target, pages=2)
    with patch.object(pypdf.PdfWriter, "write", side_effect=OSError("write fail")):
        with pytest.raises(HandlerError, match="cannot write PDF"):
            handler.structured_delete(target, "page:0")


def test_structured_delete_page_pdfread_error(handler: PdfHandler, tmp_path: Path) -> None:
    from unittest.mock import patch
    from pypdf.errors import PdfReadError
    target = tmp_path / "dpprd.pdf"
    _create_pdf(target)
    with patch("pypdf.PdfReader", side_effect=PdfReadError("bad")):
        with pytest.raises(HandlerError, match="invalid PDF"):
            handler.structured_delete(target, "page:0")


def test_structured_delete_page_os_error_reader(handler: PdfHandler, tmp_path: Path) -> None:
    from unittest.mock import patch
    target = tmp_path / "dposr.pdf"
    _create_pdf(target)
    with patch("pypdf.PdfReader", side_effect=OSError("no disk")):
        with pytest.raises(HandlerError, match="cannot read PDF"):
            handler.structured_delete(target, "page:0")


def test_structured_delete_page_encrypted_decrypt_exception(handler: PdfHandler, tmp_path: Path) -> None:
    from unittest.mock import patch, MagicMock, PropertyMock
    target = tmp_path / "ddecex.pdf"
    _create_pdf(target)
    mock_reader = MagicMock()
    type(mock_reader).is_encrypted = PropertyMock(return_value=True)
    mock_reader.decrypt.side_effect = Exception("decrypt crash")
    with patch("pypdf.PdfReader", return_value=mock_reader):
        with pytest.raises(HandlerError, match="encrypted"):
            handler.structured_delete(target, "page:0")


def test_structured_set_metadata_password_error(handler: PdfHandler, tmp_path: Path) -> None:
    import pikepdf
    from unittest.mock import patch
    target = tmp_path / "smpw.pdf"
    _create_pdf(target)
    with patch("pikepdf.open", side_effect=pikepdf.PasswordError("password required")):
        with pytest.raises(HandlerError, match="encrypted"):
            handler.structured_set(target, "metadata", {"title": "T"})


def test_structured_set_metadata_pdf_error(handler: PdfHandler, tmp_path: Path) -> None:
    import pikepdf
    from unittest.mock import patch
    target = tmp_path / "smpe.pdf"
    _create_pdf(target)
    with patch("pikepdf.open", side_effect=pikepdf.PdfError("corrupt")):
        with pytest.raises(HandlerError, match="failed to update"):
            handler.structured_set(target, "metadata", {"title": "T"})


def test_structured_set_metadata_os_error(handler: PdfHandler, tmp_path: Path) -> None:
    from unittest.mock import patch
    target = tmp_path / "smos.pdf"
    _create_pdf(target)
    with patch("pikepdf.open", side_effect=OSError("disk full")):
        with pytest.raises(HandlerError, match="cannot write PDF"):
            handler.structured_set(target, "metadata", {"title": "T"})


def test_structured_delete_metadata_password_error(handler: PdfHandler, tmp_path: Path) -> None:
    import pikepdf
    from unittest.mock import patch
    target = tmp_path / "dmpw.pdf"
    _create_pdf(target)
    with patch("pikepdf.open", side_effect=pikepdf.PasswordError("pw")):
        with pytest.raises(HandlerError, match="encrypted"):
            handler.structured_delete(target, "metadata")


def test_structured_delete_metadata_pdf_error(handler: PdfHandler, tmp_path: Path) -> None:
    import pikepdf
    from unittest.mock import patch
    target = tmp_path / "dmpe.pdf"
    _create_pdf(target)
    with patch("pikepdf.open", side_effect=pikepdf.PdfError("corrupt")):
        with pytest.raises(HandlerError, match="failed to clear"):
            handler.structured_delete(target, "metadata")


def test_structured_delete_metadata_os_error(handler: PdfHandler, tmp_path: Path) -> None:
    from unittest.mock import patch
    target = tmp_path / "dmos.pdf"
    _create_pdf(target)
    with patch("pikepdf.open", side_effect=OSError("nope")):
        with pytest.raises(HandlerError, match="cannot write PDF"):
            handler.structured_delete(target, "metadata")


def test_structured_get_pages_pdfread_error(handler: PdfHandler, tmp_path: Path) -> None:
    from unittest.mock import patch
    from pypdf.errors import PdfReadError
    target = tmp_path / "pgprd.pdf"
    _create_pdf(target)
    with patch("pdfplumber.open", side_effect=PdfReadError("corrupt")):
        with pytest.raises(HandlerError, match="invalid PDF"):
            handler.structured_get(target, "pages")


def test_structured_get_outline_exception(handler: PdfHandler, tmp_path: Path) -> None:
    from unittest.mock import patch, MagicMock, PropertyMock
    target = tmp_path / "outex.pdf"
    _create_pdf(target)
    mock_reader = MagicMock()
    type(mock_reader).outline = PropertyMock(side_effect=Exception("no outline"))
    with patch("pypdf.PdfReader", return_value=mock_reader):
        result = handler.structured_get(target, "outline")
    assert isinstance(result, list)
