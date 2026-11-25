"""Dataset validation: parse + schema + relation checks -> diagnostics."""

from __future__ import annotations

import difflib
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from todoc.adapters.filesystem.scanner import ScannedFile
from todoc.adapters.formats.csvfmt import parse_csv
from todoc.adapters.formats.jsonfmt import parse_json, validate_against_schema
from todoc.adapters.formats.markdown import parse_markdown, resolve_link_target
from todoc.domain.models import Diagnostic, SuggestedFix
from todoc.errors import ValidationError
from todoc.typing_system.descriptors import load_json_file, parse_heading_selector, schema_file
from todoc.typing_system.resolver import RESERVED_DIR_TYPES, resolve_type


def stable_id(*parts: Any) -> str:
    """Deterministic id for a finding.

    ``hash()`` is salted per process (PYTHONHASHSEED), so ids built from it
    change between two runs of the same command and cannot be stored, diffed
    or passed back to ``fix --diagnostic``.
    """
    payload = "\x1f".join(str(p) for p in parts).encode("utf-8")
    return "diag_" + hashlib.sha256(payload).hexdigest()[:12]


def _diag(dataset_id: str, path: str, code: str, message: str, severity: str = "error",
          location: dict[str, Any] | None = None, evidence: str = "", fixes: tuple[SuggestedFix, ...] = ()) -> Diagnostic:
    return Diagnostic(
        dataset_id=dataset_id,
        id=stable_id(path, code, message),
        code=code,
        severity=severity,
        path=path,
        message=message,
        location=location or {},
        evidence=evidence,
        suggested_fixes=fixes,
    )


def _basename_index(all_paths: set[str]) -> tuple[dict[str, list[str]], list[str]]:
    """Map basename/stem -> paths, plus the sorted basename universe for fuzzy match.

    Fuzzy matching runs over basenames only: comparing whole relative paths
    makes two unrelated files in the same folder look similar (``notes/runbok.md``
    vs ``notes/broken-demo.md`` scores 0.69) and produces misleading fixes.
    """
    index: dict[str, list[str]] = {}
    basenames: set[str] = set()
    for path in sorted(all_paths):
        index.setdefault(Path(path).name, []).append(path)
        index.setdefault(Path(path).stem, []).append(path)
        basenames.add(Path(path).name)
    return index, sorted(basenames)


def _wikilink_candidates(target: str, by_basename: dict[str, list[str]]) -> list[str]:
    candidates: list[str] = []
    for name in (target, f"{target}.md", f"{target}.json", f"{target}.csv"):
        for path in by_basename.get(name, ()):
            if path not in candidates:
                candidates.append(path)
    return candidates


FUZZY_CUTOFF = 0.8  # typos score 0.92+; unrelated names ("runbok.md" vs "okf.md") reach 0.67


def _fuzzy_candidates(basename: str, by_basename: dict[str, list[str]],
                      basenames: list[str]) -> list[str]:
    """Closest basename by difflib, only when it maps to exactly one path.

    Matching runs over basenames (not full relative paths) with a high cutoff:
    a suggestion that is not near-certain is worse than no suggestion, because
    ``fix --apply`` rewrites the user's file.
    """
    close = difflib.get_close_matches(basename, basenames, n=1, cutoff=FUZZY_CUTOFF)
    if not close:
        return []
    return by_basename.get(close[0], [])


def _link_diagnostic(dataset_id: str, scanned: ScannedFile, link: Any, candidates: list[str],
                     basename: str, by_basename: dict[str, list[str]], basenames: list[str]) -> Diagnostic:
    fixes: tuple[SuggestedFix, ...] = ()
    if len(candidates) == 1:
        fixes = (SuggestedFix(kind="replace_link_target", replacement=candidates[0],
                              basis="Найден единственный кандидат с совпадающим basename."),)
    else:
        fuzzy = _fuzzy_candidates(basename, by_basename, basenames)
        if len(fuzzy) == 1:
            fixes = (SuggestedFix(kind="replace_link_target", replacement=fuzzy[0],
                                  basis="Найден ближайший кандидат по имени файла."),)
    evidence = f"[[{link.target}]]" if link.is_wikilink else f"[{link.text}]({link.target})"
    return Diagnostic(
        dataset_id,
        stable_id(scanned.rel_path, link.line, link.target),
        "markdown.link.target_missing",
        "error",
        scanned.rel_path,
        "Локальная цель ссылки не найдена.",
        {"line": link.line, "column": link.column, "end_column": link.end_column, "is_wikilink": link.is_wikilink},
        evidence=evidence,
        suggested_fixes=fixes,
    )


def _check_markdown_links(dataset_id: str, scanned: ScannedFile, root: Path, all_paths: set[str],
                          basename_index: tuple[dict[str, list[str]], list[str]] | None = None) -> list[Diagnostic]:
    """Report local links whose target is not in the scanned file set.

    Targets are normalized by ``resolve_link_target`` (same code path as the
    index/backlinks), so validator and index can never disagree about what a
    link points to. Wikilinks resolve by basename/stem anywhere in the root.
    """
    diags: list[Diagnostic] = []
    try:
        text = scanned.abs_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return [Diagnostic(dataset_id, stable_id(scanned.rel_path, "markdown.unreadable"), "markdown.unreadable", "error", scanned.rel_path, "Cannot read Markdown file.")]
    doc = parse_markdown(text)
    by_basename, basenames = basename_index if basename_index is not None else _basename_index(all_paths)
    for link in doc.links:
        if link.is_wikilink:
            if not link.target:
                continue
            if _wikilink_candidates(link.target, by_basename):
                continue
            diags.append(_link_diagnostic(dataset_id, scanned, link, [], link.target, by_basename, basenames))
            continue
        normalized = resolve_link_target(scanned.rel_path, link.target)
        if normalized is None or normalized in all_paths:
            continue
        basename = Path(normalized).name
        candidates = _wikilink_candidates(basename, by_basename)
        diags.append(_link_diagnostic(dataset_id, scanned, link, candidates, basename, by_basename, basenames))
    return diags


def _normalize_heading(text: str) -> str:
    """Compare headings on plain text: inline markup carries no structural meaning.

    A parsed heading loses its markup (``## Пробел относительно `todoc` `` parses to
    ``Пробел относительно todoc``), so a selector written the way the author typed it
    in the file must still match.
    """
    return re.sub(r"\s+", " ", text.replace("`", "").replace("*", "").replace("_", "")).strip()


def _heading_matches(heading: Any, level: int | None, title: str) -> bool:
    if level is not None and heading.level != level:
        return False
    actual = _normalize_heading(heading.title)
    wanted = _normalize_heading(title)
    if wanted.endswith(":"):
        return actual.startswith(wanted)
    return actual == wanted


def _check_structure(dataset_id: str, rel_path: str, headings: list[Any],
                     descriptor: dict[str, Any]) -> list[Diagnostic]:
    """Enforce the structure a doc_type declares (required sections, section rules).

    Locations: a missing section is anchored at the document start (line 1) because
    there is no heading to point at; an empty section points at its own heading line.
    """
    diags: list[Diagnostic] = []
    for selector in descriptor.get("required_sections") or []:
        if not isinstance(selector, str) or not selector.strip():
            continue
        level, title = parse_heading_selector(selector)
        if not any(_heading_matches(h, level, title) for h in headings):
            diags.append(_diag(
                dataset_id, rel_path, "markdown.section.missing",
                f"Required section missing: {selector}",
                location={"line": 1, "column": 1},
                evidence=f"doc_type declares required_sections: {selector}",
                fixes=(SuggestedFix(kind="add_heading", replacement=selector,
                                    basis="doc_type.required_sections", autofixable=False),),
            ))
    for index, rule in enumerate(descriptor.get("section_rules") or []):
        if not isinstance(rule, dict):
            continue
        selector = str(rule.get("heading", ""))
        if not selector.strip():
            continue
        level, title = parse_heading_selector(selector)
        child_level = rule.get("child_level")
        min_children = int(rule.get("min_children", 1))
        severity = rule.get("severity") or "error"
        for heading in headings:
            if not _heading_matches(heading, level, title):
                continue
            wanted = int(child_level) if isinstance(child_level, int) else heading.level + 1
            found = sum(1 for child in heading.children if child.level == wanted)
            if found < min_children:
                diags.append(_diag(
                    dataset_id, rel_path, "markdown.section.empty",
                    f"Section {heading.title!r} needs at least {min_children} level-{wanted} "
                    f"subsection(s), found {found}.",
                    severity=severity,
                    location={"line": heading.line, "column": 1},
                    evidence=f"section_rules[{index}]: heading={selector}",
                    fixes=(SuggestedFix(kind="add_heading", replacement=f"level-{wanted} subsection",
                                        basis=f"doc_type.section_rules[{index}]", autofixable=False),),
                ))
    return diags


def validate_dataset(
    root: Path,
    dataset: dict[str, Any],
    scanned_files: list[ScannedFile],
    dir_rules: list[dict[str, Any]],
    doc_rules: list[dict[str, Any]],
    registry: Any = None,
) -> tuple[list[Diagnostic], dict[str, dict[str, Any]]]:
    """Validate all scanned files. Returns (diagnostics, doc_info).

    doc_info maps rel_path -> {doc_type, rule_source, front_matter, title, format}.

    ``registry`` is the loaded ``TypeRegistry``; when given, doc types that declare
    ``required_sections``/``section_rules`` are enforced against the parsed headings.
    """
    dataset_id = dataset["dataset_id"]
    limits = dataset.get("limits") or {}
    max_depth = int(limits.get("max_json_depth", 128))
    max_rows = int(limits.get("max_csv_rows", 1000000))
    all_paths = {f.rel_path for f in scanned_files}
    by_basename = _basename_index(all_paths)
    diags: list[Diagnostic] = []
    doc_info: dict[str, dict[str, Any]] = {}
    doc_type_descriptors: dict[str, Any] = {}
    if registry is not None:
        doc_type_descriptors = getattr(registry, "doc_types", None) or (
            registry.get("doc_types", {}) if isinstance(registry, dict) else {})

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
        headings: list[Any] = []
        if fmt == "markdown":
            doc = parse_markdown(text)
            front_matter = doc.front_matter
            title = doc.title
            headings = doc.headings
            for lineno, message in doc.warnings:
                diags.append(_diag(dataset_id, scanned.rel_path, "markdown.front_matter.yaml_unsafe",
                                   message, severity="warning", location={"line": lineno, "column": 1}))
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
                location: dict[str, Any] = {}
                if getattr(err, "line", None):
                    location = {"line": err.line, "column": err.column or 1}
                diags.append(_diag(dataset_id, scanned.rel_path, code, rest or err, location=location))
            if isinstance(value, dict):
                front_matter = value

        basename = Path(scanned.rel_path).name
        doc_type, source, conflicts = resolve_type(
            doc_rules, scanned.rel_path, basename, front_matter or None, "doc_type", {}, "unknown"
        )
        for conflict_id in conflicts:
            diags.append(_diag(dataset_id, scanned.rel_path, "config.ambiguous_rule",
                               f"Ambiguous rules {conflicts} for {scanned.rel_path}.", severity="warning"))
        descriptor = doc_type_descriptors.get(doc_type)
        if descriptor and headings:
            diags.extend(_check_structure(dataset_id, scanned.rel_path, headings, descriptor))
        doc_info[scanned.rel_path] = {
            "doc_type": doc_type, "rule_source": source, "front_matter": front_matter, "title": title, "format": fmt,
        }

    # Record validation: JSON files with record_id/entity_type.
    records = _validate_records(dataset_id, root, scanned_files, doc_info, dataset, registry)
    diags.extend(records[0])
    return diags, doc_info


def _load_record_schemas(root: Path, registry: Any = None,
                         dataset: dict[str, Any] | None = None) -> dict[str, dict[str, Any]]:
    """Load the JSON Schema of every entity type (2020-12).

    Primary location is the type's own folder (``entity_types/<type>/schema.json``),
    so everything that belongs to a type lives with it. The legacy top-level catalog
    ``.todoc/schemas/records/<type>.json`` is still read for datasets created earlier,
    and loses to the type folder when both exist (``check-config`` reports the duplicate).
    """
    schemas: dict[str, dict[str, Any]] = {}
    legacy_dir = root / ".todoc" / "schemas" / "records"
    if legacy_dir.is_dir():
        for path in sorted(legacy_dir.glob("*.json")):
            try:
                data = load_json_file(path)
            except ValidationError:
                continue
            if isinstance(data, dict):
                schemas[path.stem] = data
    entity_types = _entity_types_of(registry)
    if entity_types:
        for type_id, descriptor in sorted(entity_types.items()):
            path = schema_file(root, dataset or {}, "entity_type", descriptor)
            if path is None or not path.is_file():
                continue
            try:
                data = load_json_file(path)
            except ValidationError:
                continue
            if isinstance(data, dict):
                schemas[type_id] = data
    return schemas


def _entity_types_of(registry: Any) -> dict[str, Any]:
    """Entity types from a TypeRegistry or a plain mapping, else empty."""
    if registry is None:
        return {}
    return getattr(registry, "entity_types", None) or (
        registry.get("entity_types", {}) if isinstance(registry, dict) else {})


def _schema_evidence(root: Path, dataset: dict[str, Any], registry: Any, entity_type: str) -> str:
    """Where the applied schema actually came from, for the diagnostic's evidence."""
    descriptor = _entity_types_of(registry).get(entity_type)
    if descriptor is not None:
        path = schema_file(root, dataset, "entity_type", descriptor)
        if path is not None:
            try:
                return f"schema: {path.relative_to(root).as_posix()}"
            except ValueError:
                return f"schema: {path}"
    return f"schema: .todoc/schemas/records/{entity_type}.json"


def _key_location(text: str, key: str) -> dict[str, Any]:
    """Line of the first occurrence of a JSON key, for record diagnostics.

    A key position, not the value's exact offset: it opens the file at the right
    place while the ``pointer`` in the same location stays the precise address.
    Returns ``{}`` when the key is absent (e.g. a missing required field).
    """
    if not key:
        return {}
    needle = f'"{key}"'
    for lineno, line in enumerate(text.splitlines(), start=1):
        if needle in line:
            return {"line": lineno, "column": line.index(needle) + 1}
    return {}


def _validate_records(
    dataset_id: str, root: Path, scanned_files: list[ScannedFile], doc_info: dict[str, dict[str, Any]],
    dataset: dict[str, Any] | None = None, registry: Any = None,
) -> tuple[list[Diagnostic], list[dict[str, Any]]]:
    diags: list[Diagnostic] = []
    records: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    schemas = _load_record_schemas(root, registry, dataset)
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
            diags.append(_diag(dataset_id, scanned.rel_path, "record.duplicate_id",
                               f"Duplicate record_id: {record_id}", location=_key_location(text, "record_id")))
        seen_ids.add(record_id)
        if not entity_type:
            diags.append(_diag(dataset_id, scanned.rel_path, "record.missing_entity_type", "Record has no entity_type."))
        schema = schemas.get(entity_type)
        if schema:
            for message in validate_against_schema(value, schema):
                pointer, _, rest = message.partition(": ")
                location = {"pointer": pointer, "entity_type": entity_type}
                location.update(_key_location(text, pointer.rsplit("/", 1)[-1]))
                diags.append(_diag(
                    dataset_id, scanned.rel_path, "record.schema_violation", rest or message,
                    location=location,
                    evidence=_schema_evidence(root, dataset, registry, entity_type),
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
        for index, rel in enumerate(relations):
            # Exact structural address: relations live in a JSON record, so an
            # RFC 6901 pointer locates the offending entry without guessing a line.
            where = {"pointer": f"/relations/{index}"}
            if not isinstance(rel, dict):
                diags.append(_diag(dataset_id, record["path"], "relation.malformed",
                                   "Relation entry must be an object.", location=dict(where)))
                continue
            type_id = str(rel.get("type_id", ""))
            if known_relation_types is not None and type_id not in known_relation_types:
                diags.append(_diag(dataset_id, record["path"], "relation.unknown_type",
                                   f"Unknown relation type_id: {type_id or '<empty>'}", location=dict(where)))
            target = (rel.get("target") or {}).get("id", "") if isinstance(rel.get("target"), dict) else ""
            if target and target not in known:
                diags.append(_diag(dataset_id, record["path"], "relation.dangling_target",
                                   f"Relation target not found: {target}",
                                   location={**where, "pointer": f"/relations/{index}/target/id"}))
            elif not target:
                diags.append(_diag(dataset_id, record["path"], "relation.missing_target",
                                   f"Relation {type_id or '<empty>'} has no target.id.",
                                   location={**where, "pointer": f"/relations/{index}/target/id"}))
    return diags
