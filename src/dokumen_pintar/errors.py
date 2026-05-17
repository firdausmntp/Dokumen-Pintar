"""Runtime errors raised by Dokumen-Pintar.

Every error inherits from :class:`DokumenPintarError`, which carries
optional ``hint`` (one-line suggestion), ``docs_url`` (deep link into
the project docs), and ``code`` (stable identifier like
``DP_E_PATH_NOT_ALLOWED``). All three are positional / keyword-only
extensions; passing only the message keeps the old single-arg behaviour.
"""

from __future__ import annotations

from typing import Any


class DokumenPintarError(Exception):
    """Base class for all custom errors.

    Examples::

        raise PathNotAllowedError("absolute path /etc escapes the sandbox")

        raise UnsupportedFormatError(
            "PDF write_text is not supported",
            hint="Use compose_pdf to author a fresh PDF, or struct_set for metadata",
            docs_url="https://dokumen-pintar.dev/docs/formats#pdf",
            code="DP_E_PDF_WRITE_TEXT",
        )

    The ``hint`` and ``docs_url`` are appended to ``str(exc)`` so they
    surface in MCP error responses without callers having to inspect
    the structured fields. The ``code`` is exposed as ``exc.code`` for
    programmatic dispatch.
    """

    def __init__(
        self,
        message: str = "",
        *args: Any,
        hint: str | None = None,
        docs_url: str | None = None,
        code: str | None = None,
    ) -> None:
        super().__init__(message, *args)
        self.message: str = message
        self.hint: str | None = hint
        self.docs_url: str | None = docs_url
        self.code: str | None = code

    def __str__(self) -> str:
        parts: list[str] = [self.message] if self.message else []
        if self.hint:
            parts.append(f"\nHint: {self.hint}")
        if self.docs_url:
            parts.append(f"\nDocs: {self.docs_url}")
        if self.code:
            parts.append(f"\n[{self.code}]")
        return "".join(parts)

    def to_dict(self) -> dict[str, Any]:
        """Serialise the error for structured MCP transport."""
        return {
            "type": type(self).__name__,
            "message": self.message,
            "hint": self.hint,
            "docs_url": self.docs_url,
            "code": self.code,
        }


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
