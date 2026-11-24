"""Domain dataclasses: stable contracts shared by CLI, MCP and web adapters."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SuggestedFix:
    kind: str
    replacement: str
    basis: str
    autofixable: bool = True
    requires_review: bool = True


@dataclass(frozen=True)
class Diagnostic:
    dataset_id: str
    id: str
    code: str
    severity: str  # error | warning
    path: str
    message: str
    location: dict[str, Any] = field(default_factory=dict)
    evidence: str = ""
    suggested_fixes: tuple[SuggestedFix, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset_id": self.dataset_id,
            "id": self.id,
            "code": self.code,
            "severity": self.severity,
            "path": self.path,
            "location": dict(self.location),
            "evidence": self.evidence,
            "message": self.message,
            "suggested_fixes": [
                {
                    "kind": f.kind,
                    "replacement": f.replacement,
                    "basis": f.basis,
                    "autofixable": f.autofixable,
                    "requires_review": f.requires_review,
                }
                for f in self.suggested_fixes
            ],
        }


@dataclass(frozen=True)
class Folder:
    folder_id: str
    dataset_id: str
    path: str
    parent_folder_id: str | None
    dir_type: str
    rule_source: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "folder_id": self.folder_id,
            "dataset_id": self.dataset_id,
            "path": self.path,
            "parent_folder_id": self.parent_folder_id,
            "dir_type": self.dir_type,
            "rule_source": self.rule_source,
        }


@dataclass(frozen=True)
class Document:
    document_id: str
    dataset_id: str
    path: str
    parent_folder_id: str | None
    format: str
    doc_type: str
    rule_source: str
    hash: str
    size: int
    title: str = ""
    status: str = "ok"  # ok | parse_error | unsupported | ignored

    def to_dict(self) -> dict[str, Any]:
        return {
            "document_id": self.document_id,
            "dataset_id": self.dataset_id,
            "path": self.path,
            "parent_folder_id": self.parent_folder_id,
            "format": self.format,
            "doc_type": self.doc_type,
            "rule_source": self.rule_source,
            "hash": self.hash,
            "size": self.size,
            "title": self.title,
            "status": self.status,
        }


@dataclass(frozen=True)
class Record:
    record_id: str
    entity_type: str
    dataset_id: str
    path: str
    hash: str
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "entity_type": self.entity_type,
            "dataset_id": self.dataset_id,
            "path": self.path,
            "hash": self.hash,
            "data": dict(self.data),
        }


@dataclass(frozen=True)
class Relation:
    type_id: str
    source_id: str
    target_id: str
    dataset_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "type_id": self.type_id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "dataset_id": self.dataset_id,
        }


@dataclass(frozen=True)
class SearchHit:
    id: str
    path: str
    title: str
    heading_path: tuple[str, ...]
    rank: int
    relevance_method: str
    matched_terms: tuple[str, ...]
    snippet_text: str
    line_start: int
    line_end: int
    snippet_truncated: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "path": self.path,
            "title": self.title,
            "heading_path": list(self.heading_path),
            "rank": self.rank,
            "relevance": {"method": self.relevance_method, "matched_by": [self.relevance_method]},
            "matched_terms": list(self.matched_terms),
            "snippet": {
                "text": self.snippet_text,
                "line_start": self.line_start,
                "line_end": self.line_end,
                "snippet_truncated": self.snippet_truncated,
            },
        }


@dataclass(frozen=True)
class ValidationReport:
    dataset_id: str
    status: str  # valid | invalid | unsupported | not_checked
    path: str
    issues: tuple[Diagnostic, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset_id": self.dataset_id,
            "status": self.status,
            "path": self.path,
            "issues": [i.to_dict() for i in self.issues],
        }


@dataclass(frozen=True)
class WritePlan:
    dataset_id: str
    target_path: str
    new_content: str
    expected_hash: str | None
    new_hash: str
    basis: str
    validations: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset_id": self.dataset_id,
            "target_path": self.target_path,
            "expected_hash": self.expected_hash,
            "new_hash": self.new_hash,
            "basis": self.basis,
            "validations": list(self.validations),
        }
