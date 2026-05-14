"""Runtime errors raised by Dokumen-Pintar."""

from __future__ import annotations


class DokumenPintarError(Exception):
    """Base class for all custom errors."""


class ConfigError(DokumenPintarError):
    """Configuration loading / validation failure."""


class PathNotAllowedError(DokumenPintarError):
    """Path resolved outside of any allowed root."""


class RootNotWritableError(DokumenPintarError):
    """Attempted a write operation on a read-only root."""


class FileTooLargeError(DokumenPintarError):
    """File exceeds the configured size limit."""


class UnsupportedFormatError(DokumenPintarError):
    """No handler registered for this format / extension."""


class HandlerError(DokumenPintarError):
    """Generic handler-level failure."""


class VersioningError(DokumenPintarError):
    """Snapshot / restore related failure."""


class ConcurrencyError(DokumenPintarError):
    """File mutated outside of our lock window."""


class ValidationError(DokumenPintarError):
    """Input / argument validation failure."""
