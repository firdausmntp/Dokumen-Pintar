"""XML / SVG format handler backed by lxml."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from lxml import etree

from dokumen_pintar.errors import HandlerError
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


def _make_parser() -> etree.XMLParser:
    # resolve_entities=False disables XXE expansion; remove_blank_text=False keeps formatting.
    return etree.XMLParser(remove_blank_text=False, resolve_entities=False)


def _namespaces_for_xpath(nsmap: dict[str | None, str]) -> dict[str, str]:
    # lxml puts the default namespace under key None; XPath cannot use None,
    # so we strip it. Callers targeting a default namespace must register a prefix.
    return {k: v for k, v in nsmap.items() if k is not None}


def _detect_xml_encoding(path: Path) -> str:
    try:
        raw = path.read_bytes()
    except OSError:
        return "utf-8"
    enc = detect_encoding(raw, default="utf-8")
    # charset-normalizer returns "UTF_8", "ASCII" etc.  lxml expects the
    # canonical IANA name.  Normalise here.
    try:
        import codecs

        canonical = codecs.lookup(enc).name
    except LookupError:
        return "utf-8"
    return canonical


def _node_to_str(node: Any) -> str:
    if isinstance(node, etree._Element):
        return etree.tostring(node, pretty_print=True, encoding="unicode")
    # Attribute nodes (_ElementUnicodeResult) and text nodes behave as str.
    return str(node)


class XmlHandler:
    """Handler for XML and SVG documents using lxml + XPath."""

    name: str = "xml"
    extensions: tuple[str, ...] = (".xml", ".svg")
    capabilities: HandlerCapability = (
        HandlerCapability.READ_TEXT
        | HandlerCapability.WRITE_TEXT
        | HandlerCapability.STRUCTURED_GET
        | HandlerCapability.STRUCTURED_SET
        | HandlerCapability.STRUCTURED_DELETE
        | HandlerCapability.SEARCH_EXTRACTED
    )

    # ------------------------------------------------------------------ basics
    def detect(self, path: Path) -> bool:
        return path.suffix.lower() in self.extensions

    def read_meta(self, path: Path) -> dict[str, Any]:
        stat = path.stat()
        try:
            tree = etree.parse(str(path), _make_parser())
        except etree.XMLSyntaxError as exc:
            raise HandlerError(f"invalid XML: {exc}") from exc
        root = tree.getroot()
        namespaces = {(k if k is not None else ""): v for k, v in root.nsmap.items()}
        return {
            "format": self.name,
            "size": stat.st_size,
            "mtime": stat.st_mtime,
            "root_tag": root.tag,
            "namespaces": namespaces,
            "child_count": len(root),
        }

    # -------------------------------------------------------------------- text
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
            tree = etree.parse(str(path), _make_parser())
        except (etree.XMLSyntaxError, OSError):
            return ""
        root = tree.getroot()
        return "".join(root.itertext())

    # -------------------------------------------------------------- structured
    def _parse(self, path: Path) -> etree._ElementTree:
        try:
            return etree.parse(str(path), _make_parser())
        except etree.XMLSyntaxError as exc:
            raise HandlerError(f"invalid XML: {exc}") from exc
        except OSError as exc:
            raise HandlerError(f"cannot read XML: {exc}") from exc

    def _write_tree(self, path: Path, tree: etree._ElementTree) -> None:
        encoding = _detect_xml_encoding(path)
        try:
            tree.write(
                str(path),
                xml_declaration=True,
                encoding=encoding,
                pretty_print=True,
            )
        except (OSError, LookupError) as exc:
            raise HandlerError(f"failed to write XML: {exc}") from exc

    def _eval_xpath(self, tree: etree._ElementTree, expr: str) -> list[Any]:
        root = tree.getroot()
        namespaces = _namespaces_for_xpath(root.nsmap)
        try:
            result = tree.xpath(expr, namespaces=namespaces)
        except etree.XPathEvalError as exc:
            raise HandlerError(f"invalid XPath '{expr}': {exc}") from exc
        if not isinstance(result, list):
            # Numeric / string / bool result from XPath functions.
            result = [result]
        return result

    def structured_get(self, path: Path, expr: str) -> Any:
        tree = self._parse(path)
        result = self._eval_xpath(tree, expr)
        strings = [_node_to_str(n) for n in result]
        if len(strings) == 1:
            return strings[0]
        return strings

    def structured_set(self, path: Path, expr: str, value: Any) -> None:
        tree = self._parse(path)
        result = self._eval_xpath(tree, expr)
        if not result:
            raise HandlerError(f"XPath '{expr}' matched nothing")

        new_value = str(value)
        touched = False
        for node in result:
            if isinstance(node, etree._Element):
                node.text = new_value
                touched = True
            elif isinstance(node, etree._ElementUnicodeResult):
                # Attribute result: getparent() returns the owning element.
                parent = node.getparent()
                attr_name = getattr(node, "attrname", None)
                if parent is None or attr_name is None:
                    # Not an attribute (likely a text() node); overwrite the parent's text.
                    parent = node.getparent() if hasattr(node, "getparent") else None
                    if parent is not None:  # pragma: no branch
                        parent.text = new_value
                        touched = True
                    continue
                parent.set(attr_name, new_value)
                touched = True
            else:
                raise HandlerError(
                    f"XPath '{expr}' result is not writable (type={type(node).__name__})"
                )

        if not touched:  # pragma: no cover
            raise HandlerError(f"XPath '{expr}' produced no writable targets")

        self._write_tree(path, tree)

    def structured_delete(self, path: Path, expr: str) -> None:
        tree = self._parse(path)
        result = self._eval_xpath(tree, expr)
        if not result:
            raise HandlerError(f"XPath '{expr}' matched nothing")

        touched = False
        for node in result:
            if isinstance(node, etree._Element):
                parent = node.getparent()
                if parent is None:
                    raise HandlerError("cannot delete the root element")
                parent.remove(node)
                touched = True
            elif isinstance(node, etree._ElementUnicodeResult):
                parent = node.getparent()
                attr_name = getattr(node, "attrname", None)
                if parent is None or attr_name is None:
                    raise HandlerError(f"XPath '{expr}' selects a non-deletable text node")
                parent.attrib.pop(attr_name, None)
                touched = True
            else:
                raise HandlerError(
                    f"XPath '{expr}' result is not deletable (type={type(node).__name__})"
                )

        if not touched:  # pragma: no cover
            raise HandlerError(f"XPath '{expr}' produced no deletable targets")

        self._write_tree(path, tree)


# Runtime-checkable protocol sanity assertion + registry hookup.
_handler: FormatHandler = XmlHandler()
default_registry.register(_handler)
