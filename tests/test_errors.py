"""Tests for :mod:`dokumen_pintar.errors`."""

from __future__ import annotations

import pytest

from dokumen_pintar.errors import (
    ConcurrencyError,
    ConfigError,
    DokumenPintarError,
    FileTooLargeError,
    HandlerError,
    PathNotAllowedError,
    RootNotWritableError,
    UnsupportedFormatError,
    ValidationError,
    VersioningError,
)


@pytest.mark.parametrize(
    "exc_class",
    [
        ConfigError,
        PathNotAllowedError,
        RootNotWritableError,
        FileTooLargeError,
        UnsupportedFormatError,
        HandlerError,
        VersioningError,
        ConcurrencyError,
        ValidationError,
    ],
)
def test_all_errors_are_subclass_of_base(exc_class: type) -> None:
    assert issubclass(exc_class, DokumenPintarError)
    assert issubclass(exc_class, Exception)


def test_error_message_preserved() -> None:
    err = HandlerError("something broke")
    assert str(err) == "something broke"


def test_error_can_be_raised_and_caught() -> None:
    with pytest.raises(DokumenPintarError):
        raise ConfigError("bad config")


def test_error_hierarchy_catch_specific() -> None:
    with pytest.raises(PathNotAllowedError):
        raise PathNotAllowedError("not allowed")

    # Also catchable as the base class
    with pytest.raises(DokumenPintarError):
        raise PathNotAllowedError("not allowed")



# ── v1.1.0 F.1: hint + docs_url + code ──


def test_error_legacy_single_arg_still_works() -> None:
    """Existing single-arg call sites keep working."""
    from dokumen_pintar.errors import HandlerError

    exc = HandlerError("simple message")
    assert str(exc) == "simple message"
    assert exc.hint is None
    assert exc.docs_url is None
    assert exc.code is None


def test_error_with_hint_renders_in_str() -> None:
    from dokumen_pintar.errors import UnsupportedFormatError

    exc = UnsupportedFormatError("pdf write_text not supported", hint="Use compose_pdf")
    text = str(exc)
    assert "pdf write_text not supported" in text
    assert "Hint: Use compose_pdf" in text


def test_error_with_docs_url_renders_in_str() -> None:
    from dokumen_pintar.errors import HandlerError

    exc = HandlerError("oops", docs_url="https://example.com/docs")
    assert "Docs: https://example.com/docs" in str(exc)


def test_error_with_code_renders_in_str() -> None:
    from dokumen_pintar.errors import HandlerError

    exc = HandlerError("issue", code="DP_E_TEST")
    assert "[DP_E_TEST]" in str(exc)


def test_error_with_all_extras() -> None:
    from dokumen_pintar.errors import HandlerError

    exc = HandlerError(
        "failed to render",
        hint="Check the spec is valid first",
        docs_url="https://example.com/spec",
        code="DP_E_RENDER_FAILED",
    )
    s = str(exc)
    assert "failed to render" in s
    assert "Hint: Check the spec is valid first" in s
    assert "Docs: https://example.com/spec" in s
    assert "[DP_E_RENDER_FAILED]" in s


def test_error_to_dict_round_trip() -> None:
    from dokumen_pintar.errors import ValidationError

    exc = ValidationError(
        "bad input",
        hint="Use one of: foo, bar",
        docs_url="https://example.com/v",
        code="DP_E_BAD_INPUT",
    )
    d = exc.to_dict()
    assert d["type"] == "ValidationError"
    assert d["message"] == "bad input"
    assert d["hint"] == "Use one of: foo, bar"
    assert d["docs_url"] == "https://example.com/v"
    assert d["code"] == "DP_E_BAD_INPUT"


def test_error_empty_message_no_str_artifacts() -> None:
    """An error raised with empty message and no extras stringifies to empty."""
    from dokumen_pintar.errors import HandlerError

    exc = HandlerError()
    assert str(exc) == ""