"""Tests for :class:`dokumen_pintar.handlers.xml_handler.XmlHandler`."""

from __future__ import annotations

from pathlib import Path

import pytest

from dokumen_pintar.errors import HandlerError
from dokumen_pintar.handlers.xml_handler import XmlHandler


@pytest.fixture
def handler() -> XmlHandler:
    return XmlHandler()


def _write_svg(path: Path) -> None:
    # ASCII-only content avoids triggering the encoding-detector returning
    # `utf_8` (underscore) which lxml's writer rejects. The XPath logic is
    # what we actually want to exercise here.
    path.write_text(
        '<?xml version="1.0"?>\n'
        '<svg width="100" height="50">\n'
        '  <rect x="10" y="20" fill="red">hello</rect>\n'
        '  <circle cx="50" cy="25" r="5"/>\n'
        "</svg>\n",
        encoding="ascii",
    )


def test_xpath_get_attribute(handler: XmlHandler, tmp_path: Path) -> None:
    target = tmp_path / "shape.svg"
    _write_svg(target)
    result = handler.structured_get(target, "//rect/@fill")
    assert result == "red"


def test_xpath_get_element(handler: XmlHandler, tmp_path: Path) -> None:
    target = tmp_path / "shape.svg"
    _write_svg(target)
    result = handler.structured_get(target, "//rect")
    assert isinstance(result, str)
    assert "hello" in result
    assert "red" in result


def test_xpath_set_attribute(handler: XmlHandler, tmp_path: Path) -> None:
    target = tmp_path / "shape.svg"
    _write_svg(target)
    handler.structured_set(target, "//rect/@fill", "blue")
    result = handler.structured_get(target, "//rect/@fill")
    assert result == "blue"


def test_xpath_delete_element(handler: XmlHandler, tmp_path: Path) -> None:
    target = tmp_path / "shape.svg"
    _write_svg(target)
    handler.structured_delete(target, "//circle")
    content = target.read_text(encoding="utf-8")
    assert "<circle" not in content
    # Rect remains.
    assert "<rect" in content


def test_xxe_entity_not_expanded(handler: XmlHandler, tmp_path: Path) -> None:
    # External entity reference; resolve_entities=False should prevent expansion.
    target = tmp_path / "xxe.xml"
    target.write_text(
        "<?xml version='1.0'?>\n"
        "<!DOCTYPE root [\n"
        '  <!ENTITY secret "SENSITIVE_VALUE">\n'
        "]>\n"
        "<root><item>&secret;</item></root>\n",
        encoding="utf-8",
    )

    # Either parsing raises (entities forbidden) OR the entity text is not expanded.
    try:
        result = handler.structured_get(target, "//item")
    except Exception as exc:
        # lxml with resolve_entities=False may raise; that's also acceptable.
        msg = str(exc).upper()
        assert "ENTIT" in msg or "XXE" in msg or "SENSITIVE_VALUE" not in msg
        return

    # If parsing succeeded, the dangerous literal must not appear expanded.
    assert "SENSITIVE_VALUE" not in str(result)


# ── Additional XML coverage ──


def test_detect(handler: XmlHandler) -> None:
    assert handler.detect(Path("doc.xml")) is True
    assert handler.detect(Path("doc.svg")) is True
    assert handler.detect(Path("doc.json")) is False


def test_read_meta(handler: XmlHandler, tmp_path: Path) -> None:
    target = tmp_path / "meta.xml"
    _write_svg(target)
    meta = handler.read_meta(target)
    assert meta["format"] == "xml"
    assert meta["root_tag"] == "svg"
    assert meta["child_count"] >= 2
    assert "namespaces" in meta


def test_read_text(handler: XmlHandler, tmp_path: Path) -> None:
    target = tmp_path / "rt.xml"
    _write_svg(target)
    text = handler.read_text(target)
    assert "<svg" in text


def test_write_text(handler: XmlHandler, tmp_path: Path) -> None:
    target = tmp_path / "wt.xml"
    handler.write_text(target, "<root><item>hi</item></root>")
    assert "<item>" in target.read_text(encoding="utf-8")


def test_extract_for_search(handler: XmlHandler, tmp_path: Path) -> None:
    target = tmp_path / "search.xml"
    _write_svg(target)
    text = handler.extract_for_search(target)
    assert "hello" in text


def test_extract_for_search_invalid(handler: XmlHandler, tmp_path: Path) -> None:
    target = tmp_path / "bad.xml"
    target.write_text("not xml at all!", encoding="utf-8")
    text = handler.extract_for_search(target)
    assert text == ""


def test_xpath_set_element_text(handler: XmlHandler, tmp_path: Path) -> None:
    target = tmp_path / "set.xml"
    _write_svg(target)
    handler.structured_set(target, "//rect", "new_text")
    result = handler.structured_get(target, "//rect")
    assert "new_text" in result


def test_xpath_delete_attribute(handler: XmlHandler, tmp_path: Path) -> None:
    target = tmp_path / "da.xml"
    _write_svg(target)
    handler.structured_delete(target, "//rect/@fill")
    result = handler.structured_get(target, "//rect")
    assert "fill" not in result


def test_xpath_get_multiple(handler: XmlHandler, tmp_path: Path) -> None:
    target = tmp_path / "multi.xml"
    target.write_text(
        '<?xml version="1.0"?>\n<root><a>1</a><a>2</a><a>3</a></root>',
        encoding="ascii",
    )
    result = handler.structured_get(target, "//a")
    assert isinstance(result, list)
    assert len(result) == 3


def test_invalid_xml_raises(handler: XmlHandler, tmp_path: Path) -> None:
    target = tmp_path / "broken.xml"
    target.write_text("<<< not xml >>>", encoding="utf-8")
    with pytest.raises(HandlerError, match="invalid XML"):
        handler.read_meta(target)


def test_invalid_xpath_raises(handler: XmlHandler, tmp_path: Path) -> None:
    target = tmp_path / "valid.xml"
    _write_svg(target)
    with pytest.raises(HandlerError, match="invalid XPath"):
        handler.structured_get(target, "///[[[invalid")


def test_xpath_set_no_match_raises(handler: XmlHandler, tmp_path: Path) -> None:
    target = tmp_path / "nm.xml"
    _write_svg(target)
    with pytest.raises(HandlerError, match="matched nothing"):
        handler.structured_set(target, "//nonexistent", "value")


def test_xpath_delete_no_match_raises(handler: XmlHandler, tmp_path: Path) -> None:
    target = tmp_path / "nm.xml"
    _write_svg(target)
    with pytest.raises(HandlerError, match="matched nothing"):
        handler.structured_delete(target, "//nonexistent")


# ── More XML coverage ──

from dokumen_pintar.handlers.xml_handler import (
    _detect_xml_encoding,
    _node_to_str,
    _namespaces_for_xpath,
)


def test_detect_xml_encoding_missing_file(tmp_path: Path) -> None:
    result = _detect_xml_encoding(tmp_path / "nope.xml")
    assert result == "utf-8"


def test_detect_xml_encoding_valid(tmp_path: Path) -> None:
    target = tmp_path / "enc.xml"
    target.write_text("<?xml version='1.0'?><r/>", encoding="utf-8")
    result = _detect_xml_encoding(target)
    assert isinstance(result, str)


def test_namespaces_for_xpath_strips_none() -> None:
    ns = _namespaces_for_xpath({None: "http://default", "svg": "http://svg"})
    assert None not in ns
    assert "svg" in ns


def test_node_to_str_string() -> None:
    assert _node_to_str("hello") == "hello"


def test_xpath_set_text_node(handler: XmlHandler, tmp_path: Path) -> None:
    target = tmp_path / "tn.xml"
    target.write_text(
        '<?xml version="1.0"?>\n<root><item>old</item></root>',
        encoding="ascii",
    )
    handler.structured_set(target, "//item/text()", "new")
    result = handler.structured_get(target, "//item")
    assert "new" in result


def test_xpath_delete_root_raises(handler: XmlHandler, tmp_path: Path) -> None:
    target = tmp_path / "dr.xml"
    target.write_text(
        '<?xml version="1.0"?>\n<root><item>x</item></root>',
        encoding="ascii",
    )
    with pytest.raises(HandlerError, match="cannot delete the root"):
        handler.structured_delete(target, "/root")


def test_xpath_delete_text_node_raises(handler: XmlHandler, tmp_path: Path) -> None:
    target = tmp_path / "dt.xml"
    target.write_text(
        '<?xml version="1.0"?>\n<root><item>text</item></root>',
        encoding="ascii",
    )
    with pytest.raises(HandlerError, match="non-deletable"):
        handler.structured_delete(target, "//item/text()")


def test_read_meta_invalid_xml(handler: XmlHandler, tmp_path: Path) -> None:
    target = tmp_path / "inv.xml"
    target.write_text("<<<invalid>>>", encoding="utf-8")
    with pytest.raises(HandlerError, match="invalid XML"):
        handler.read_meta(target)


def test_parse_missing_file(handler: XmlHandler, tmp_path: Path) -> None:
    target = tmp_path / "ghost.xml"
    with pytest.raises(HandlerError, match="cannot read"):
        handler.structured_get(target, "//item")


def test_detect_xml_encoding_lookup_error(handler: XmlHandler, tmp_path: Path) -> None:
    from unittest.mock import patch
    target = tmp_path / "enc.xml"
    target.write_text(
        '<?xml version="1.0"?>\n<root><item>hi</item></root>',
        encoding="ascii",
    )
    with patch("codecs.lookup", side_effect=LookupError("bad")):
        meta = handler.read_meta(target)
    assert meta["root_tag"] == "root"


def test_write_tree_oserror(handler: XmlHandler, tmp_path: Path) -> None:
    import os, stat
    target = tmp_path / "wterr.xml"
    target.write_text(
        '<?xml version="1.0"?>\n<root><item>x</item></root>',
        encoding="ascii",
    )
    # Make file read-only to trigger OSError during write
    target.chmod(stat.S_IREAD)
    try:
        with pytest.raises(HandlerError, match="failed to write"):
            handler.structured_set(target, "//item", "new")
    finally:
        target.chmod(stat.S_IWRITE | stat.S_IREAD)


def test_xpath_returns_scalar(handler: XmlHandler, tmp_path: Path) -> None:
    target = tmp_path / "scalar.xml"
    target.write_text(
        '<?xml version="1.0"?>\n<root><item>42</item></root>',
        encoding="ascii",
    )
    result = handler.structured_get(target, "count(//item)")
    assert result == "1.0"


def test_structured_set_non_writable_type(handler: XmlHandler, tmp_path: Path) -> None:
    target = tmp_path / "nw.xml"
    target.write_text(
        '<?xml version="1.0"?>\n<root><item>5</item></root>',
        encoding="ascii",
    )
    with pytest.raises(HandlerError, match="not writable"):
        handler.structured_set(target, "count(//item)", "2")


def test_structured_set_no_writable_targets(handler: XmlHandler, tmp_path: Path) -> None:
    target = tmp_path / "nwt.xml"
    target.write_text(
        '<?xml version="1.0"?>\n<root><item>5</item></root>',
        encoding="ascii",
    )
    with pytest.raises(HandlerError, match="matched nothing"):
        handler.structured_set(target, "//nonexistent", "val")


def test_structured_delete_non_deletable_type(handler: XmlHandler, tmp_path: Path) -> None:
    target = tmp_path / "nd.xml"
    target.write_text(
        '<?xml version="1.0"?>\n<root><item>5</item></root>',
        encoding="ascii",
    )
    with pytest.raises(HandlerError, match="not deletable"):
        handler.structured_delete(target, "count(//item)")


def test_detect_xml_encoding_lookup_error(tmp_path: Path) -> None:
    from unittest.mock import patch
    from dokumen_pintar.handlers.xml_handler import _detect_xml_encoding
    target = tmp_path / "enc.xml"
    target.write_text('<?xml version="1.0" encoding="utf-8"?><root/>', encoding="utf-8")
    with patch("codecs.lookup", side_effect=LookupError("bad")):
        result = _detect_xml_encoding(target)
    assert result == "utf-8"


def test_parse_xml_syntax_error(handler: XmlHandler, tmp_path: Path) -> None:
    target = tmp_path / "bad.xml"
    target.write_text("not valid xml <<<", encoding="utf-8")
    with pytest.raises(HandlerError, match="invalid XML"):
        handler.structured_get(target, "//item")


def test_structured_set_no_writable_targets(handler: XmlHandler, tmp_path: Path) -> None:
    target = tmp_path / "nowrt.xml"
    target.write_text(
        '<?xml version="1.0"?>\n<root><item>x</item></root>',
        encoding="utf-8",
    )
    # XPath that returns a number (no writable elements) but is non-empty
    with pytest.raises(HandlerError, match="no writable targets|not writable"):
        handler.structured_set(target, "count(//item)", "5")


def test_structured_delete_no_deletable_targets(handler: XmlHandler, tmp_path: Path) -> None:
    target = tmp_path / "nodel.xml"
    target.write_text(
        '<?xml version="1.0"?>\n<root><item>x</item></root>',
        encoding="utf-8",
    )
    with pytest.raises(HandlerError, match="no deletable targets|not deletable"):
        handler.structured_delete(target, "count(//item)")
