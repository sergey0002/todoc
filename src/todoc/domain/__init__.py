"""Domain models (no Click/filesystem/search-provider knowledge)."""

from todoc.domain.models import (
    Diagnostic,
    Document,
    Folder,
    Record,
    Relation,
    SearchHit,
    SuggestedFix,
    ValidationReport,
    WritePlan,
)

__all__ = [
    "Diagnostic",
    "Document",
    "Folder",
    "Record",
    "Relation",
    "SearchHit",
    "SuggestedFix",
    "ValidationReport",
    "WritePlan",
]
