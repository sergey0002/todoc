"""Dataset validation: parse + schema + relation checks -> diagnostics."""

from __future__ import annotations

import difflib
import json
from pathlib import Path
from typing import Any

from todoc.adapters.filesystem.scanner import ScannedFile
from todoc.adapters.formats.csvfmt import parse_csv
from todoc.adapters.formats.jsonfmt import parse_json, validate_against_schema
from todoc.adapters.formats.markdown import parse_markdown, resolve_link_target
from todoc.domain.models import Diagnostic, SuggestedFix
from todoc.errors import ValidationError
from todoc.typing_system.descriptors import load_json_file
from todoc.typing_system.resolver import RESERVED_DIR_TYPES, resolve_type


def _diag(dataset_id: str, path: str, code: str, message: str, severity: str = "error",
          location: dict[str, Any] | None = None, evidence: str = "", fixes: tuple[SuggestedFix, ...] = ()) -> Diagnostic:
    return Diagnostic(
        dataset_id=dataset_id,
        id=f"diag_{abs(hash((path, code, message))) % 100000:05d}",
        code=code,
        severity=severity,
        path=path,
        message=message,
        location=location or {},
        evidence=evidence,
        suggested_fixes=fixes,
    )


def _basename_index(all_paths: set[str]) -> dict[str, list[str]]:
    index: dict[str, list[str]] = {}
    for path in sorted(all_paths):
        index.setdefault(Path(path).name, []).append(path)
        index.setdefault(Path(path).stem, []).append(path)
    return index


def _wikilink_candidates(target: str, by_basename: dict[str, list[str]]) -> list[str]:
    candidates: list[str] = []
    for name in (target, f"{target}.md", f"{target}.json", f"{target}.csv"):
        for path in by_basename.get(name, ()):
            if path not in candidates:
                candidates.append(path)
    return candidates


def _link_diagnostic(dataset_id: str, scanned: ScannedFile, link: Any,
                     candidates: list[str], normalized: str, sorted_paths: list[str]) -> Diagnostic:
    fixes: tuple[SuggestedFix, ...] = ()
    if len(candidates) == 1:
        fixes = (SuggestedFix(kind="replace_link_target", replacement=candidates[0],
                              basis="Найден единственный кандидат с совпадающим basename."),)
    else:
        close = difflib.get_close_matches(normalized, sorted_paths, n=1, cutoff=0.6)
        if close:
            fixes = (SuggestedFix(kind="replace_link_target", replacement=close[0],
                                  basis="Найден ближайший кандидат по имени файла."),)
    evidence = f"[[{link.target}]]" if link.is_wikilink else f"[{link.text}]({link.target})"
    return Diagnostic(
        dataset_id,
        f"diag_{abs(hash((scanned.rel_path, link.line, link.target))) % 100000:05d}",
        "markdown.link.target_missing",
        "error",
        scanned.rel_path,
        "Локальная цель ссылки не найдена.",
        {"line": link.line, "column": link.column, "end_column": link.end_column, "is_wikilink": link.is_wikilink},
        evidence=evidence,
        suggested_fixes=fixes,
    )


def _check_markdown_links(dataset_id: str, scanned: ScannedFile, root: Path, all_paths: set[str],
                          by_basename: dict[str, list[str]] | None = None) -> list[Diagnostic]:
    """Report local links whose target is not in the scanned file set.

    Targets are normalized by ``resolve_link_target`` (same code path as the
    index/backlinks), so validator and index can never disagree about what a
    link points to. Wikilinks resolve by basename/stem anywhere in the root.
    """
    diags: list[Diagnostic] = []
    try:
        text = scanned.abs_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return [Diagnostic(dataset_id, f"diag_{abs(hash(scanned.rel_path)) % 100000:05d}", "markdown.unreadable", "error", scanned.rel_path, "Cannot read Markdown file.")]
    doc = parse_markdown(text)
    index = by_basename if by_basename is not None else _basename_index(all_paths)
    sorted_paths = sorted(all_paths)
    for link in doc.links:
        if link.is_wikilink:
            if not link.target:
                continue
            if _wikilink_candidates(link.target, index):
                continue
            diags.append(_link_diagnostic(dataset_id, scanned, link, [], link.target, sorted_paths))
            continue
        normalized = resolve_link_target(scanned.rel_path, link.target)
        if normalized is None or normalized in all_paths:
            continue
        candidates = _wikilink_candidates(Path(normalized).name, index)
        diags.append(_link_diagnostic(dataset_id, scanned, link, candidates, normalized, sorted_paths))
    return diags


def validate_dataset(
    root: Path,
    dataset: dict[str, Any],
    scanned_files: list[ScannedFile],
    dir_rules: list[dict[str, Any]],
    doc_rules: list[dict[str, Any]],
    registry: dict[str, Any] | None = None,
) -> tuple[list[Diagnostic], dict[str, dict[str, Any]]]:
    """Validate all scanned files. Returns (diagnostics, doc_info).

    doc_info maps rel_path -> {doc_type, rule_source, front_matter, title, format}.
    """
    dataset_id = dataset["dataset_id"]
    limits = dataset.get("limits") or {}
    max_depth = int(limits.get("max_json_depth", 128))
    max_rows = int(limits.get("max_csv_rows", 1000000))
    all_paths = {f.rel_path for f in scanned_files}
    by_basename = _basename_index(all_paths)
    diags: list[Diagnostic] = []
    doc_info: dict[str, dict[str, Any]] = {}

    for scanned in scanned_files:
        fmt = scanned.format
        if fmt == "opaque":
            doc_info[scanned.rel_path] = {"doc_type": "unknown", "rule_source": "default", "front_matter": {}, "title": "", "format": fmt}
            continue
        if scanned.status == "unsupported":
            diags.append(_diag(dataset_id, scanned.rel_path, "file.unsupported", "File exceeds size limit or is unsupported."))
            doc_info[scanned.rel_path] = {"doc_type": "unknown", "rule_source": "default", "front_matter": {}, "title": "", "format": fmt}
            continue
        if scanned.status == "permission_denied":
            diags.append(_diag(dataset_id, scanned.rel_path, "file.permission_denied", "Cannot read file."))
            doc_info[scanned.rel_path] = {"doc_type": "unknown", "rule_source": "default", "front_matter": {}, "title": "", "format": fmt}
            continue
        try:
            text = scanned.abs_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            diags.append(_diag(dataset_id, scanned.rel_path, "file.unreadable", "Cannot read file as UTF-8."))
            doc_info[scanned.rel_path] = {"doc_type": "unknown", "rule_source": "default", "front_matter": {}, "title": "", "format": fmt}
            continue

        front_matter: dict[str, Any] = {}
        title = ""
        if fmt == "markdown":
            doc = parse_markdown(text)
            front_matter = doc.front_matter
            title = doc.title
            diags.extend(_check_markdown_links(dataset_id, scanned, root, all_paths, by_basename))
        elif fmt == "csv":
            csv_doc = parse_csv(text, max_rows=max_rows)
            for err in csv_doc.errors:
                code, _, rest = err.partition(": ")
                diags.append(_diag(dataset_id, scanned.rel_path, code, rest or err))
        elif fmt == "json":
            value, errors = parse_json(text, max_depth=max_depth)
            for err in errors:
                code, _, rest = err.partition(": ")
                diags.append(_diag(dataset_id, scanned.rel_path, code, rest or err))
            if isinstance(value, dict):
                front_matter = value

        basename = Path(scanned.rel_path).name
        doc_type, source, conflicts = resolve_type(
            doc_rules, scanned.rel_path, basename, front_matter or None, "doc_type", {}, "unknown"
        )
        for conflict_id in conflicts:
            diags.append(_diag(dataset_id, scanned.rel_path, "config.ambiguous_rule",
                               f"Ambiguous rules {conflicts} for {scanned.rel_path}.", severity="warning"))
        doc_info[scanned.rel_path] = {
            "doc_type": doc_type, "rule_source": source, "front_matter": front_matter, "title": title, "format": fmt,
        }

    # Record validation: JSON files with record_id/entity_type.
    records = _validate_records(dataset_id, root, scanned_files, doc_info)
    diags.extend(records[0])
    return diags, doc_info


def _load_record_schemas(root: Path) -> dict[str, dict[str, Any]]:
    """Load `.todoc/schemas/records/<entity_type>.json` (JSON Schema 2020-12)."""
    schemas: dict[str, dict[str, Any]] = {}
    schema_dir = root / ".todoc" / "schemas" / "records"
    if not schema_dir.is_dir():
        return schemas
    for schema_file in sorted(schema_dir.glob("*.json")):
        try:
            data = load_json_file(schema_file)
        except ValidationError:
            continue
        if isinstance(data, dict):
            schemas[schema_file.stem] = data
    return schemas


def _validate_records(
    dataset_id: str, root: Path, scanned_files: list[ScannedFile], doc_info: dict[str, dict[str, Any]]
) -> tuple[list[Diagnostic], list[dict[str, Any]]]:
    diags: list[Diagnostic] = []
    records: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    schemas = _load_record_schemas(root)
    for scanned in scanned_files:
        if scanned.format != "json" or scanned.status != "ok":
            continue
        try:
            text = scanned.abs_path.read_text(encoding="utf-8")
        except OSError:
            continue
        value, _ = parse_json(text)
        if not isinstance(value, dict) or "record_id" not in value:
            continue
        record_id = str(value.get("record_id"))
        entity_type = str(value.get("entity_type", ""))
        if record_id in seen_ids:
            diags.append(_diag(dataset_id, scanned.rel_path, "record.duplicate_id", f"Duplicate record_id: {record_id}"))
        seen_ids.add(record_id)
        if not entity_type:
            diags.append(_diag(dataset_id, scanned.rel_path, "record.missing_entity_type", "Record has no entity_type."))
        schema = schemas.get(entity_type)
        if schema:
            for message in validate_against_schema(value, schema):
                pointer, _, rest = message.partition(": ")
                diags.append(_diag(
                    dataset_id, scanned.rel_path, "record.schema_violation", rest or message,
                    location={"pointer": pointer, "entity_type": entity_type},
                    evidence=f"schema: .todoc/schemas/records/{entity_type}.json",
                ))
        records.append({
            "record_id": record_id, "entity_type": entity_type, "dataset_id": dataset_id,
            "path": scanned.rel_path, "hash": scanned.hash, "data": value,
        })
    return diags, records


def validate_relations(
    dataset_id: str,
    records: list[dict[str, Any]],
    known_relation_types: set[str] | None = None,
) -> list[Diagnostic]:
    """Check relations: declared type_id must exist, target must exist.

    ``known_relation_types=None`` disables the type check (backwards
    compatible); pass the registry's relation_type ids to enable it.
    """
    diags: list[Diagnostic] = []
    known = {r["record_id"] for r in records}
    for record in records:
        relations = record["data"].get("relations")
        if not isinstance(relations, list):
            if relations is not None:
                diags.append(_diag(dataset_id, record["path"], "relation.malformed",
                                   "Field 'relations' must be a list of objects."))
            continue
        for rel in relations:
            if not isinstance(rel, dict):
                diags.append(_diag(dataset_id, record["path"], "relation.malformed",
                                   "Relation entry must be an object."))
                continue
            type_id = str(rel.get("type_id", ""))
            if known_relation_types is not None and type_id not in known_relation_types:
                diags.append(_diag(dataset_id, record["path"], "relation.unknown_type",
                                   f"Unknown relation type_id: {type_id or '<empty>'}"))
            target = (rel.get("target") or {}).get("id", "") if isinstance(rel.get("target"), dict) else ""
            if target and target not in known:
                diags.append(_diag(dataset_id, record["path"], "relation.dangling_target",
                                   f"Relation target not found: {target}"))
            elif not target:
                diags.append(_diag(dataset_id, record["path"], "relation.missing_target",
                                   f"Relation {type_id or '<empty>'} has no target.id."))
    return diags
