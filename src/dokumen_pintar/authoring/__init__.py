"""Document authoring API — JSON spec to DOCX/PDF rendering.

Pure-Python pipeline:
- :mod:`spec`             validates a deklaratif block list (the document IR).
- :mod:`render_docx`      renders the IR to a `.docx` file via python-docx.
- :mod:`render_pdf`       renders the IR to a `.pdf` file via reportlab.
- :mod:`markdown_to_spec` converts a Markdown source to the IR.
"""

from __future__ import annotations

from .spec import DocumentSpec, SpecError, validate_spec

__all__ = ["DocumentSpec", "SpecError", "validate_spec"]
