"""Semantic search subsystem (optional)."""

from .index import SemanticHit, SemanticIndex, serialize_hits

__all__ = ["SemanticHit", "SemanticIndex", "serialize_hits"]
