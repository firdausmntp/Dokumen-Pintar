"""Tests for JSON and YAML handlers."""

from __future__ import annotations

from pathlib import Path

import pytest

from dokumen_pintar.handlers.json_yaml_handler import JsonHandler, YamlHandler


# ---------------------------------------------------------------------- JSON


@pytest.fixture
def json_handler() -> JsonHandler:
    return JsonHandler()


def _write_json(path: Path) -> None:
    path.write_text(
        '{\n  "user": {\n    "name": "alice",\n    "age": 30,\n    "tags": ["a", "b", "c"]\n  }\n}\n',
        encoding="utf-8",
    )


def test_json_structured_get_nested(json_handler: JsonHandler, tmp_path: Path) -> None:
    target = tmp_path / "data.json"
    _write_json(target)
    assert json_handler.structured_get(target, "$.user.name") == "alice"
    assert json_handler.structured_get(target, "$.user.age") == 30
    tags = json_handler.structured_get(target, "$.user.tags[*]")
    assert tags == ["a", "b", "c"]


def test_json_structured_set_nested(json_handler: JsonHandler, tmp_path: Path) -> None:
    target = tmp_path / "data.json"
    _write_json(target)
    json_handler.structured_set(target, "$.user.name", "bob")
    assert json_handler.structured_get(target, "$.user.name") == "bob"


def test_json_structured_delete_nested(json_handler: JsonHandler, tmp_path: Path) -> None:
    target = tmp_path / "data.json"
    _write_json(target)
    json_handler.structured_delete(target, "$.user.age")
    # After deletion, the key should be gone; jsonpath returns [] for missing.
    result = json_handler.structured_get(target, "$.user.age")
    assert result == [] or result is None


# ---------------------------------------------------------------------- YAML


@pytest.fixture
def yaml_handler() -> YamlHandler:
    return YamlHandler()


def test_yaml_roundtrip_preserves_comments(yaml_handler: YamlHandler, tmp_path: Path) -> None:
    target = tmp_path / "cfg.yaml"
    original = "# top-level comment\nservice:\n  name: api  # inline comment\n  port: 8080\n"
    target.write_text(original, encoding="utf-8")

    # Trigger round-trip via structured_set (no-op value change on an unrelated key).
    yaml_handler.structured_set(target, "$.service.port", 9090)
    round_tripped = target.read_text(encoding="utf-8")

    assert "# top-level comment" in round_tripped
    assert "# inline comment" in round_tripped
    assert "9090" in round_tripped


def test_yaml_structured_get_nested(yaml_handler: YamlHandler, tmp_path: Path) -> None:
    target = tmp_path / "cfg.yaml"
    target.write_text("service:\n  name: api\n  port: 8080\n", encoding="utf-8")
    assert yaml_handler.structured_get(target, "$.service.name") == "api"
    assert yaml_handler.structured_get(target, "$.service.port") == 8080


def test_yaml_structured_delete(yaml_handler: YamlHandler, tmp_path: Path) -> None:
    target = tmp_path / "cfg.yaml"
    target.write_text("service:\n  name: api\n  port: 8080\n  debug: true\n", encoding="utf-8")
    yaml_handler.structured_delete(target, "$.service.debug")
    content = target.read_text(encoding="utf-8")
    assert "debug" not in content


# ── Additional JSON coverage ──


def test_json_detect(json_handler: JsonHandler) -> None:
    assert json_handler.detect(Path("data.json")) is True
    assert json_handler.detect(Path("data.jsonc")) is True
    assert json_handler.detect(Path("data.json5")) is True
    assert json_handler.detect(Path("data.xml")) is False


def test_json_read_text(json_handler: JsonHandler, tmp_path: Path) -> None:
    target = tmp_path / "r.json"
    target.write_text('{"a":1}', encoding="utf-8")
    text = json_handler.read_text(target)
    assert '"a"' in text


def test_json_write_text(json_handler: JsonHandler, tmp_path: Path) -> None:
    target = tmp_path / "w.json"
    json_handler.write_text(target, '{"b":2}\n')
    assert '"b"' in target.read_text(encoding="utf-8")


def test_json_read_meta(json_handler: JsonHandler, tmp_path: Path) -> None:
    target = tmp_path / "meta.json"
    target.write_text('{"x": 1, "y": 2}', encoding="utf-8")
    meta = json_handler.read_meta(target)
    assert meta["format"] == "json"
    assert meta["top_level_type"] == "object"
    assert meta["key_count"] == 2


def test_json_read_meta_array(json_handler: JsonHandler, tmp_path: Path) -> None:
    target = tmp_path / "arr.json"
    target.write_text('[1,2,3]', encoding="utf-8")
    meta = json_handler.read_meta(target)
    assert meta["top_level_type"] == "array"
    assert meta["key_count"] == 3


def test_json_extract_for_search(json_handler: JsonHandler, tmp_path: Path) -> None:
    target = tmp_path / "s.json"
    target.write_text('{"key": "searchable_value"}', encoding="utf-8")
    text = json_handler.extract_for_search(target)
    assert "searchable_value" in text


def test_jsonc_comments_stripped(json_handler: JsonHandler, tmp_path: Path) -> None:
    target = tmp_path / "data.jsonc"
    target.write_text(
        '{\n  // line comment\n  "key": "value" /* block comment */\n}\n',
        encoding="utf-8",
    )
    result = json_handler.structured_get(target, "$.key")
    assert result == "value"


def test_json_invalid_raises(json_handler: JsonHandler, tmp_path: Path) -> None:
    target = tmp_path / "bad.json"
    target.write_text("not json at all", encoding="utf-8")
    with pytest.raises(Exception):
        json_handler.structured_get(target, "$.x")


def test_json_structured_delete_no_match(json_handler: JsonHandler, tmp_path: Path) -> None:
    target = tmp_path / "nm.json"
    target.write_text('{"a": 1}', encoding="utf-8")
    json_handler.structured_delete(target, "$.nonexistent")
    # Should be a no-op
    assert json_handler.structured_get(target, "$.a") == 1


def test_json_structured_delete_key_from_nested(json_handler: JsonHandler, tmp_path: Path) -> None:
    target = tmp_path / "nested.json"
    target.write_text('{"a": {"x": 1, "y": 2}, "b": 3}', encoding="utf-8")
    json_handler.structured_delete(target, "$.a.x")
    result = json_handler.structured_get(target, "$.a")
    assert "x" not in result
    assert result["y"] == 2


# ── Additional YAML coverage ──


def test_yaml_detect(yaml_handler: YamlHandler) -> None:
    assert yaml_handler.detect(Path("data.yaml")) is True
    assert yaml_handler.detect(Path("data.yml")) is True
    assert yaml_handler.detect(Path("data.json")) is False


def test_yaml_read_text(yaml_handler: YamlHandler, tmp_path: Path) -> None:
    target = tmp_path / "r.yaml"
    target.write_text("key: value\n", encoding="utf-8")
    text = yaml_handler.read_text(target)
    assert "key: value" in text


def test_yaml_write_text(yaml_handler: YamlHandler, tmp_path: Path) -> None:
    target = tmp_path / "w.yaml"
    yaml_handler.write_text(target, "a: 1\n")
    assert "a: 1" in target.read_text(encoding="utf-8")


def test_yaml_read_meta(yaml_handler: YamlHandler, tmp_path: Path) -> None:
    target = tmp_path / "meta.yaml"
    target.write_text("x: 1\ny: 2\nz: 3\n", encoding="utf-8")
    meta = yaml_handler.read_meta(target)
    assert meta["format"] == "yaml"
    assert meta["top_level_type"] == "object"
    assert meta["key_count"] == 3


def test_yaml_extract_for_search(yaml_handler: YamlHandler, tmp_path: Path) -> None:
    target = tmp_path / "s.yaml"
    target.write_text("search: findme_yaml\n", encoding="utf-8")
    text = yaml_handler.extract_for_search(target)
    assert "findme_yaml" in text


def test_yaml_invalid_raises(yaml_handler: YamlHandler, tmp_path: Path) -> None:
    target = tmp_path / "bad.yaml"
    target.write_text(":\n  :\n   :\n{{{", encoding="utf-8")
    with pytest.raises(Exception):
        yaml_handler.structured_get(target, "$.x")


def test_yaml_structured_set_creates_key(yaml_handler: YamlHandler, tmp_path: Path) -> None:
    target = tmp_path / "create.yaml"
    target.write_text("existing: 1\n", encoding="utf-8")
    yaml_handler.structured_set(target, "$.new_key", "new_value")
    result = yaml_handler.structured_get(target, "$.new_key")
    assert result == "new_value"


def test_yaml_structured_delete(yaml_handler: YamlHandler, tmp_path: Path) -> None:
    target = tmp_path / "del.yaml"
    target.write_text("a: 1\nb: 2\n", encoding="utf-8")
    yaml_handler.structured_delete(target, "$.a")
    result = yaml_handler.structured_get(target, "$.b")
    assert result == 2


def test_yaml_structured_delete_no_match(yaml_handler: YamlHandler, tmp_path: Path) -> None:
    target = tmp_path / "delnm.yaml"
    target.write_text("a: 1\n", encoding="utf-8")
    yaml_handler.structured_delete(target, "$.nonexistent")
    assert yaml_handler.structured_get(target, "$.a") == 1


def test_yaml_to_plain_recursive(yaml_handler: YamlHandler, tmp_path: Path) -> None:
    target = tmp_path / "plain.yaml"
    target.write_text("a:\n  b: [1, 2]\n  c: hello\n", encoding="utf-8")
    result = yaml_handler.structured_get(target, "$.a")
    assert isinstance(result, dict)
    assert result["b"] == [1, 2]
    assert result["c"] == "hello"


# ── Additional JSON coverage ──

from dokumen_pintar.errors import HandlerError


def test_json_read_meta(json_handler: JsonHandler, tmp_path: Path) -> None:
    target = tmp_path / "meta.json"
    _write_json(target)
    meta = json_handler.read_meta(target)
    assert meta["format"] == "json"
    assert meta["top_level_type"] == "object"
    assert meta["key_count"] == 1


def test_json_read_meta_list(json_handler: JsonHandler, tmp_path: Path) -> None:
    target = tmp_path / "arr.json"
    target.write_text("[1, 2, 3]", encoding="utf-8")
    meta = json_handler.read_meta(target)
    assert meta["top_level_type"] == "array"
    assert meta["key_count"] == 3


def test_json_extract_for_search(json_handler: JsonHandler, tmp_path: Path) -> None:
    target = tmp_path / "s.json"
    _write_json(target)
    text = json_handler.extract_for_search(target)
    assert "alice" in text


def test_json_read_text(json_handler: JsonHandler, tmp_path: Path) -> None:
    target = tmp_path / "rt.json"
    _write_json(target)
    text = json_handler.read_text(target)
    assert "alice" in text


def test_json_write_text(json_handler: JsonHandler, tmp_path: Path) -> None:
    target = tmp_path / "wt.json"
    json_handler.write_text(target, '{"x": 1}')
    assert target.read_text(encoding="utf-8") == '{"x": 1}'


def test_json_invalid_jsonpath(json_handler: JsonHandler, tmp_path: Path) -> None:
    target = tmp_path / "inv.json"
    _write_json(target)
    with pytest.raises(HandlerError, match="invalid jsonpath"):
        json_handler.structured_get(target, "$[[[invalid")


def test_json_invalid_file(json_handler: JsonHandler, tmp_path: Path) -> None:
    target = tmp_path / "bad.json"
    target.write_text("{not valid json}", encoding="utf-8")
    with pytest.raises(HandlerError, match="invalid json"):
        json_handler.structured_get(target, "$.x")


def test_jsonc_strip_comments(json_handler: JsonHandler, tmp_path: Path) -> None:
    target = tmp_path / "data.jsonc"
    target.write_text('{\n  // comment\n  "key": "val"\n}\n', encoding="utf-8")
    result = json_handler.structured_get(target, "$.key")
    assert result == "val"


def test_json_structured_set_error(json_handler: JsonHandler, tmp_path: Path) -> None:
    target = tmp_path / "serr.json"
    target.write_text("42", encoding="utf-8")
    with pytest.raises(HandlerError):
        json_handler.structured_set(target, "$.x", "v")


# ── More JSON/YAML coverage ──

from dokumen_pintar.handlers.json_yaml_handler import (
    _top_level_type,
    _key_count,
    _delete_match,
)


def test_top_level_type_scalar() -> None:
    assert _top_level_type(42) == "scalar"
    assert _top_level_type("hello") == "scalar"
    assert _top_level_type(None) == "scalar"


def test_key_count_scalar() -> None:
    assert _key_count(42) is None
    assert _key_count("str") is None


def test_key_count_dict() -> None:
    assert _key_count({"a": 1, "b": 2}) == 2


def test_key_count_list() -> None:
    assert _key_count([1, 2, 3]) == 3


def test_json_delete_from_dict(json_handler: JsonHandler, tmp_path: Path) -> None:
    target = tmp_path / "ddict.json"
    target.write_text('{"a": 1, "b": 2, "c": 3}', encoding="utf-8")
    json_handler.structured_delete(target, "$.b")
    result = json_handler.structured_get(target, "$")
    assert "b" not in result
    assert result["a"] == 1
    assert result["c"] == 3


def test_json_delete_no_match(json_handler: JsonHandler, tmp_path: Path) -> None:
    target = tmp_path / "dnm.json"
    target.write_text('{"a": 1}', encoding="utf-8")
    # Delete nonexistent key should be a no-op
    json_handler.structured_delete(target, "$.nonexistent")
    result = json_handler.structured_get(target, "$.a")
    assert result == 1


def test_json_meta_invalid_json(json_handler: JsonHandler, tmp_path: Path) -> None:
    target = tmp_path / "metainv.json"
    target.write_text("{not valid json!!!", encoding="utf-8")
    meta = json_handler.read_meta(target)
    assert meta["top_level_type"] == "scalar"
    assert meta["key_count"] is None


def test_json_extract_for_search_invalid(json_handler: JsonHandler, tmp_path: Path) -> None:
    target = tmp_path / "extractinv.json"
    target.write_text("{broken!", encoding="utf-8")
    text = json_handler.extract_for_search(target)
    assert text == "{broken!"


def test_jsonc_invalid_after_strip(json_handler: JsonHandler, tmp_path: Path) -> None:
    target = tmp_path / "bad.jsonc"
    target.write_text("// comment\n{broken invalid", encoding="utf-8")
    with pytest.raises(HandlerError, match="invalid .jsonc"):
        json_handler.structured_get(target, "$.x")


def test_yaml_delete_key(yaml_handler, tmp_path: Path) -> None:
    target = tmp_path / "delk.yaml"
    target.write_text("a: 1\nb: 2\nc: 3\n", encoding="utf-8")
    yaml_handler.structured_delete(target, "$.b")
    result = yaml_handler.structured_get(target, "$")
    assert "b" not in result


def test_yaml_structured_set_nested(yaml_handler, tmp_path: Path) -> None:
    target = tmp_path / "setn.yaml"
    target.write_text("a:\n  b: 1\n", encoding="utf-8")
    yaml_handler.structured_set(target, "$.a.b", 42)
    result = yaml_handler.structured_get(target, "$.a.b")
    assert result == 42


def test_yaml_meta(yaml_handler, tmp_path: Path) -> None:
    target = tmp_path / "meta.yaml"
    target.write_text("key: val\nother: 2\n", encoding="utf-8")
    meta = yaml_handler.read_meta(target)
    assert meta["format"] == "yaml"
    assert meta["key_count"] == 2
    assert meta["top_level_type"] == "object"


def test_yaml_extract_for_search(yaml_handler, tmp_path: Path) -> None:
    target = tmp_path / "search.yaml"
    target.write_text("msg: hello world\n", encoding="utf-8")
    text = yaml_handler.extract_for_search(target)
    assert "hello world" in text


def test_json_structured_get_multiple_matches(json_handler: JsonHandler, tmp_path: Path) -> None:
    target = tmp_path / "multi.json"
    target.write_text('{"items": [{"x": 1}, {"x": 2}]}', encoding="utf-8")
    result = json_handler.structured_get(target, "$.items[*].x")
    assert result == [1, 2]


# ── YAML-specific coverage ──

from dokumen_pintar.errors import HandlerError


def test_yaml_meta_invalid(yaml_handler, tmp_path: Path) -> None:
    target = tmp_path / "badmeta.yaml"
    target.write_text("a: [unterminated", encoding="utf-8")
    meta = yaml_handler.read_meta(target)
    assert meta["top_level_type"] == "scalar"
    assert meta["key_count"] is None


def test_yaml_structured_get_multiple(yaml_handler, tmp_path: Path) -> None:
    target = tmp_path / "multi.yaml"
    target.write_text("items:\n  - x: 1\n  - x: 2\n", encoding="utf-8")
    result = yaml_handler.structured_get(target, "$.items[*].x")
    assert result == [1, 2]


def test_yaml_structured_get_no_match(yaml_handler, tmp_path: Path) -> None:
    target = tmp_path / "nomatch.yaml"
    target.write_text("a: 1\n", encoding="utf-8")
    result = yaml_handler.structured_get(target, "$.nonexistent")
    assert result == []


def test_yaml_structured_set_error_scalar(yaml_handler, tmp_path: Path) -> None:
    target = tmp_path / "serr.yaml"
    target.write_text("42\n", encoding="utf-8")
    with pytest.raises(HandlerError):
        yaml_handler.structured_set(target, "$.x", "v")


def test_yaml_structured_delete(yaml_handler, tmp_path: Path) -> None:
    target = tmp_path / "del.yaml"
    target.write_text("a: 1\nb: 2\nc: 3\n", encoding="utf-8")
    yaml_handler.structured_delete(target, "$.c")
    result = yaml_handler.structured_get(target, "$")
    assert "c" not in result


def test_yaml_structured_delete_no_match(yaml_handler, tmp_path: Path) -> None:
    target = tmp_path / "delnm.yaml"
    target.write_text("a: 1\n", encoding="utf-8")
    yaml_handler.structured_delete(target, "$.missing")
    result = yaml_handler.structured_get(target, "$.a")
    assert result == 1


def test_yaml_parse_expr_invalid(yaml_handler, tmp_path: Path) -> None:
    target = tmp_path / "inv.yaml"
    target.write_text("a: 1\n", encoding="utf-8")
    with pytest.raises(HandlerError, match="invalid jsonpath"):
        yaml_handler.structured_get(target, "[[[invalid")


def test_yaml_load_invalid(yaml_handler, tmp_path: Path) -> None:
    target = tmp_path / "loadinv.yaml"
    target.write_text("a: [unterminated", encoding="utf-8")
    with pytest.raises(HandlerError, match="invalid yaml"):
        yaml_handler.structured_get(target, "$.a")


def test_yaml_dump_error(yaml_handler, tmp_path: Path) -> None:
    from ruamel.yaml import YAMLError
    target = tmp_path / "dumperr.yaml"
    target.write_text("a: 1\n", encoding="utf-8")
    from unittest.mock import patch
    with patch.object(yaml_handler._yaml, "dump", side_effect=YAMLError("dump fail")):
        with pytest.raises(HandlerError, match="failed to serialize"):
            yaml_handler.structured_set(target, "$.a", 2)


def test_delete_match_root() -> None:
    from unittest.mock import MagicMock
    match = MagicMock()
    match.context = MagicMock()
    match.context.value = None
    with pytest.raises(HandlerError, match="cannot delete root"):
        _delete_match(match)


def test_delete_match_dict_with_index() -> None:
    from unittest.mock import MagicMock
    match = MagicMock()
    parent = {"0": "val", "1": "other"}
    match.context = MagicMock()
    match.context.value = parent
    match.path = MagicMock()
    match.path.fields = None
    match.path.index = 0
    _delete_match(match)
    assert "0" not in parent


def test_delete_match_dict_unsupported_segment() -> None:
    from unittest.mock import MagicMock
    match = MagicMock()
    match.context = MagicMock()
    match.context.value = {"a": 1}
    match.path = MagicMock()
    match.path.fields = None
    match.path.index = None
    with pytest.raises(HandlerError, match="unsupported jsonpath segment for dict"):
        _delete_match(match)


def test_delete_match_list() -> None:
    from unittest.mock import MagicMock
    match = MagicMock()
    parent = ["a", "b", "c"]
    match.context = MagicMock()
    match.context.value = parent
    match.path = MagicMock()
    match.path.fields = None
    match.path.index = 1
    _delete_match(match)
    assert parent == ["a", "c"]


def test_delete_match_list_unsupported() -> None:
    from unittest.mock import MagicMock
    match = MagicMock()
    match.context = MagicMock()
    match.context.value = ["a", "b"]
    match.path = MagicMock()
    match.path.fields = None
    match.path.index = None
    with pytest.raises(HandlerError, match="unsupported jsonpath segment for list"):
        _delete_match(match)


def test_delete_match_non_container() -> None:
    from unittest.mock import MagicMock
    match = MagicMock()
    match.context = MagicMock()
    match.context.value = 42  # not dict or list
    match.path = MagicMock()
    match.path.fields = None
    match.path.index = None
    with pytest.raises(HandlerError, match="cannot delete from parent"):
        _delete_match(match)
