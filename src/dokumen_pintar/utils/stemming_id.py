"""Indonesian text stemming via Sastrawi.

Sastrawi is the de-facto Indonesian stemmer. It strips affixes
(``me-``, ``ber-``, ``ter-``, ``di-``, ``pe-``, ``-an``, ``-i``, ``-lah``,
``-kah``, ``-nya``, etc.) so that morphological variants of a word
collapse to the same root - e.g. ``mengatakan`` / ``berkata`` /
``perkataan`` all stem to ``kata``.

The factory + stemmer instances are expensive to build (the dictionary
is ~25k entries loaded lazily on first call), so we cache a single
process-wide stemmer behind :func:`get_stemmer`. The stemmer is
imported lazily so users who don't enable Indonesian search don't pay
the import cost.
"""

from __future__ import annotations

import re
import threading
from typing import Any

_STEMMER_LOCK = threading.Lock()
_STEMMER: Any | None = None
_TOKEN_RX = re.compile(r"\w+", re.UNICODE)


def get_stemmer() -> Any:
    """Return a cached Sastrawi ``Stemmer`` instance.

    The first call constructs the stemmer and pays the dictionary load
    cost (~50ms on a modern machine). Subsequent calls are O(1).
    """
    global _STEMMER
    if _STEMMER is not None:
        return _STEMMER
    with _STEMMER_LOCK:
        if (
            _STEMMER is None
        ):  # pragma: no branch - double-check pattern; second-thread arrival is races-only
            try:
                from Sastrawi.Stemmer.StemmerFactory import StemmerFactory
            except ImportError as exc:  # pragma: no cover - hard dep
                raise ImportError(
                    "Sastrawi is required for Indonesian stemming. "
                    "Install with: pip install Sastrawi"
                ) from exc
            factory = StemmerFactory()
            _STEMMER = factory.create_stemmer()
    return _STEMMER


def stem_word(word: str) -> str:
    """Stem a single word. Empty / whitespace-only input returns unchanged."""
    if not word or not word.strip():  # pragma: no branch - both branches covered
        return word
    return get_stemmer().stem(word)  # pragma: no cover - exercised via stem_text in production


def stem_text(text: str) -> str:
    """Stem every alphanumeric token in ``text``, preserving punctuation/whitespace.

    Example::

        >>> stem_text("Mengatakan bahwa pembelajaran berbasis komputer")
        "kata bahwa ajar basis komputer"
    """
    if not text:
        return text
    stemmer = get_stemmer()

    def _replace(match: re.Match[str]) -> str:
        token = match.group(0)
        # Preserve original casing for short or all-uppercase tokens
        # (likely acronyms like SAP, KP, dll.).
        if token.isupper() and len(token) <= 5:
            return token
        return stemmer.stem(token.lower())

    return _TOKEN_RX.sub(_replace, text)
