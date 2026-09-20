"""Versioned aspect ontology and backwards-compatible normalization entry point."""

from __future__ import annotations

from .normalization import (
    ONTOLOGY_VERSION,
    CanonicalAspect,
    NormalizationResult,
    OntologyCollisionError,
    get_ontology,
    normalize_aspect,
)

# Legacy name consumed by the extraction prototype. Values remain display labels so
# existing callers keep working while IDs live alongside labels in the versioned data.
CANONICAL_ASPECTS = {
    item.display_label: item.aliases for item in get_ontology().aspects
}

__all__ = [
    "CANONICAL_ASPECTS",
    "ONTOLOGY_VERSION",
    "CanonicalAspect",
    "NormalizationResult",
    "OntologyCollisionError",
    "get_ontology",
    "normalize_aspect",
]
