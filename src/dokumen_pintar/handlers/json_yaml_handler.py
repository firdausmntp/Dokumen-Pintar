"""JSON and YAML format handlers.

JSON supports: .json, .jsonc (with // and /* */ comments stripped on parse),
and .json5 (best-effort via the same comment-stripping fallback).

YAML uses ``ruamel.yaml`` in round-trip mode to preserve comments, key order,
anchors, and scalar styles across ``structured_set`` / ``structured_delete``.
"""

from __future__ import annotations

import io
import json
import re
from pathlib import Path
from typing import Any

from jsonpath_ng.ext import parse as jsonpath_parse  # type: ignore[import-untyped]
from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from dokumen_pintar.errors import HandlerError
from dokumen_pintar.handlers.base import (
    FormatHandler,
    HandlerCapability,
    default_registry,
)
from dokumen_pintar.utils.encoding import (
    read_text as _read_text,
    write_text as _write_text,
)

_STRUCTURED_CAPS: HandlerCapability = (
    HandlerCapability.READ_TEXT
    | HandlerCapability.WRITE_TEXT
    | HandlerCapability.STRUCTURED_GET
    | HandlerCapability.STRUCTURED_SET
    | HandlerCapability.STRUCTURED_DELETE
    | HandlerCapability.SEARCH_EXTRACTED
)

# Match `// line` and `/* block */` comments while respecting string literals.
_JSONC_COMMENT_RE = re.compile(
    r"""
    (?P<string>"(?:\\.|[^"\\])*")   |  # JSON string literal (kept)
    (?P<line>//[^\n]*)              |  # // line comment (stripped)
    (?P<block>/\*.*?\*/)               # /* block comment */ (stripped)
    """,
    re.VERBOSE | re.DOTALL,
)


def _strip_jsonc_comments(source: str) -> str:
    """Remove // and /* */ comments from a JSONC/JSON5 source string.

    String literals are preserved verbatim so that sequences like ``"a//b"``
    are not mangled. Trailing commas are left alone - stdlib ``json`` will
    still reject them, which is the desired behavior for strict parsing.
    """

    def _repl(match: re.Match[str]) -> str:
        if match.group("string") is not None:
            return match.group("string")
        return ""

    return _JSONC_COMMENT_RE.sub(_repl, source)


def _top_level_type(value: Any) -> str:
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    return "scalar"


def _key_count(value: Any) -> int | None:
    if isinstance(value, (dict, list)):
        return len(value)
    return None


def _delete_match(match: Any) -> None:
    """Delete a jsonpath-ng ``match`` from its parent container.

    Works for both dict and list parents. Uses ``match.full_path`` walked
    against the root when ``match.context`` is unavailable.
    """

    parent: Any = match.context.value if match.context is not None else None
    if parent is None:
        raise HandlerError("cannot delete root element via jsonpath")

    path = match.path
    fields = getattr(path, "fields", None)
    index = getattr(path, "index", None)

    if isinstance(parent, dict):
        if fields:
            for field in fields:
                parent.pop(field, None)
        elif index is not None:
            # Dict addressed with an integer? Try string fallback.
            parent.pop(str(index), None)
        else:
            raise HandlerError(f"unsupported jsonpath segment for dict: {path!r}")
    elif isinstance(parent, list):
        if index is not None:
            if 0 <= index < len(parent):  # pragma: no branch
                del parent[index]
        else:
            raise HandlerError(f"unsupported jsonpath segment for list: {path!r}")
    else:
        raise HandlerError(f"cannot delete from parent of type {type(parent).__name__}")


class JsonHandler:
    """Handler for JSON, JSONC, and (best-effort) JSON5 files."""

    name: str = "json"
    extensions: tuple[str, ...] = (".json", ".jsonc", ".json5")
    capabilities: HandlerCapability = _STRUCTURED_CAPS

    def detect(self, path: Path) -> bool:
        return path.suffix.lower() in self.extensions

    # ------------------------------------------------------------------ IO

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

    # ------------------------------------------------------------------ meta

    def read_meta(self, path: Path) -> dict[str, Any]:
        stat = path.stat()
        text = self.read_text(path)
        try:
            data = self._loads(text, suffix=path.suffix.lower())
            top = _top_level_type(data)
            keys = _key_count(data)
        except HandlerError:
            top = "scalar"
            keys = None
        return {
            "format": self.name,
            "size": stat.st_size,
            "mtime": stat.st_mtime,
            "top_level_type": top,
            "key_count": keys,
        }

    # ------------------------------------------------------------------ search

    def extract_for_search(self, path: Path) -> str:
        text = self.read_text(path)
        try:
            data = self._loads(text, suffix=path.suffix.lower())
            return json.dumps(data, indent=2, ensure_ascii=False, sort_keys=False)
        except HandlerError:
            return text

    # ---------------------------------------------------------------- structured

    def structured_get(self, path: Path, expr: str) -> Any:
        data = self._load_file(path)
        parser = self._parse_expr(expr)
        matches = parser.find(data)
        values = [m.value for m in matches]
        if len(values) == 1:
            return values[0]
        return values

    def structured_set(self, path: Path, expr: str, value: Any) -> None:
        data = self._load_file(path)
        parser = self._parse_expr(expr)
        try:
            parser.update_or_create(data, value)
        except (TypeError, ValueError, AttributeError) as exc:
            raise HandlerError(f"failed to set jsonpath {expr!r} in {path}: {exc}") from exc
        serialized = json.dumps(data, indent=2, ensure_ascii=False)
        self.write_text(path, serialized + "\n")

    def structured_delete(self, path: Path, expr: str) -> None:
        data = self._load_file(path)
        parser = self._parse_expr(expr)
        matches = list(parser.find(data))
        if not matches:
            return
        # Delete from deepest indices first so list mutations stay correct.
        for match in sorted(
            matches,
            key=lambda m: getattr(m.path, "index", -1) or -1,
            reverse=True,
        ):
            _delete_match(match)
        serialized = json.dumps(data, indent=2, ensure_ascii=False)
        self.write_text(path, serialized + "\n")

    # ------------------------------------------------------------------ helpers

    def _parse_expr(self, expr: str) -> Any:
        try:
            return jsonpath_parse(expr)
        except (ValueError, TypeError, Exception) as exc:  # noqa: BLE001
            # jsonpath_ng raises its own JsonPathParserError which subclasses
            # Exception; keep the net wide but re-wrap with context.
            raise HandlerError(f"invalid jsonpath expression {expr!r}: {exc}") from exc

    def _load_file(self, path: Path) -> Any:
        text = self.read_text(path)
        return self._loads(text, suffix=path.suffix.lower())

    @staticmethod
    def _loads(text: str, *, suffix: str) -> Any:
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            if suffix in (".jsonc", ".json5"):
                try:
                    return json.loads(_strip_jsonc_comments(text))
                except json.JSONDecodeError as exc2:
                    raise HandlerError(
                        f"invalid {suffix} after stripping comments: {exc2}"
                    ) from exc2
            raise HandlerError(f"invalid json: {exc}") from exc


class YamlHandler:
    """Handler for YAML files with comment/style-preserving round-trips."""

    name: str = "yaml"
    extensions: tuple[str, ...] = (".yaml", ".yml")
    capabilities: HandlerCapability = _STRUCTURED_CAPS

    def __init__(self) -> None:
        self._yaml = YAML(typ="rt")
        self._yaml.preserve_quotes = True
        self._yaml.width = 4096  # avoid surprising wrapping on dump

    def detect(self, path: Path) -> bool:
        return path.suffix.lower() in self.extensions

    # ------------------------------------------------------------------ IO

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

    # ------------------------------------------------------------------ meta

    def read_meta(self, path: Path) -> dict[str, Any]:
        stat = path.stat()
        try:
            data = self._load_file(path)
            top = _top_level_type(data)
            keys = _key_count(data)
        except HandlerError:
            top = "scalar"
            keys = None
        return {
            "format": self.name,
            "size": stat.st_size,
            "mtime": stat.st_mtime,
            "top_level_type": top,
            "key_count": keys,
        }

    # ------------------------------------------------------------------ search

    def extract_for_search(self, path: Path) -> str:
        return self.read_text(path)

    # ---------------------------------------------------------------- structured

    def structured_get(self, path: Path, expr: str) -> Any:
        data = self._load_file(path)
        parser = self._parse_expr(expr)
        matches = parser.find(data)
        # Coerce ruamel scalar wrappers to plain Python for caller ergonomics.
        values = [self._to_plain(m.value) for m in matches]
        if len(values) == 1:
            return values[0]
        return values

    def structured_set(self, path: Path, expr: str, value: Any) -> None:
        data = self._load_file(path)
        parser = self._parse_expr(expr)
        try:
            parser.update_or_create(data, value)
        except (TypeError, ValueError, AttributeError) as exc:
            raise HandlerError(f"failed to set jsonpath {expr!r} in {path}: {exc}") from exc
        self._dump_file(path, data)

    def structured_delete(self, path: Path, expr: str) -> None:
        data = self._load_file(path)
        parser = self._parse_expr(expr)
        matches = list(parser.find(data))
        if not matches:
            return
        for match in sorted(
            matches,
            key=lambda m: getattr(m.path, "index", -1) or -1,
            reverse=True,
        ):
            _delete_match(match)
        self._dump_file(path, data)

    # ------------------------------------------------------------------ helpers

    def _parse_expr(self, expr: str) -> Any:
        try:
            return jsonpath_parse(expr)
        except (ValueError, TypeError, Exception) as exc:  # noqa: BLE001
            raise HandlerError(f"invalid jsonpath expression {expr!r}: {exc}") from exc

    def _load_file(self, path: Path) -> Any:
        text = self.read_text(path)
        try:
            return self._yaml.load(text)
        except YAMLError as exc:
            raise HandlerError(f"invalid yaml in {path}: {exc}") from exc

    def _dump_file(self, path: Path, data: Any) -> None:
        buf = io.StringIO()
        try:
            self._yaml.dump(data, buf)
        except YAMLError as exc:
            raise HandlerError(f"failed to serialize yaml for {path}: {exc}") from exc
        self.write_text(path, buf.getvalue())

    @staticmethod
    def _to_plain(value: Any) -> Any:
        """Best-effort conversion of ruamel scalar types to plain Python."""
        # ruamel CommentedMap / CommentedSeq already behave like dict/list,
        # but consumers often prefer vanilla containers for JSON-ability.
        if isinstance(value, dict):
            return {k: YamlHandler._to_plain(v) for k, v in value.items()}
        if isinstance(value, list):
            return [YamlHandler._to_plain(v) for v in value]
        # Scalar wrappers subclass their native type - str/int/float/bool -
        # so direct return is fine; tests can still compare equality.
        return value


# Protocol sanity checks + registration.
_json_handler: FormatHandler = JsonHandler()
_yaml_handler: FormatHandler = YamlHandler()
default_registry.register(_json_handler)
default_registry.register(_yaml_handler)
