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
