"""Dataset validation: parse + schema + relation checks -> diagnostics."""

from __future__ import annotations

import difflib
import hashlib
import json
import posixpath
import re
from pathlib import Path, PurePosixPath
from typing import Any

from todoc.adapters.filesystem.scanner import ScannedFile
from todoc.adapters.formats.csvfmt import parse_csv
from todoc.adapters.formats.jsonfmt import parse_json, validate_against_schema
from todoc.adapters.formats.markdown import (doc_from_payload, doc_to_payload, parse_markdown,
                                             resolve_link_target)
from todoc.application.registry import read_parse_cache, write_parse_cache
from todoc.application import temporal
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


def _link_replacement(candidate: str, source_rel_path: str, is_wikilink: bool) -> str:
    """Write a root-relative candidate the way the link itself must be written.

    An inline Markdown link resolves against the directory of the file that
    contains it, so a candidate taken from the root-relative basename index has
    to be re-based onto that directory. Without this, ``fix --apply`` rewrites
    ``[a](runbok.md)`` in ``notes/a.md`` into ``ops/runbook.md``, which the
    parser then looks for at ``notes/ops/runbook.md`` — the file stays broken
    and the diagnostic comes back on the next ``validate``.

    Wikilinks are the exception: they resolve by basename/stem anywhere in the
    root (``_wikilink_candidates``), so they must stay a bare stem.
    """
    if is_wikilink:
        return PurePosixPath(candidate).stem
    parent = PurePosixPath(source_rel_path).parent.as_posix()
    return posixpath.relpath(candidate, parent)


def _link_diagnostic(dataset_id: str, scanned: ScannedFile, link: Any, candidates: list[str],
                     basename: str, by_basename: dict[str, list[str]], basenames: list[str]) -> Diagnostic:
    fixes: tuple[SuggestedFix, ...] = ()
    if len(candidates) == 1:
        fixes = (SuggestedFix(kind="replace_link_target",
                              replacement=_link_replacement(candidates[0], scanned.rel_path, link.is_wikilink),
                              basis="Найден единственный кандидат с совпадающим basename."),)
    else:
        fuzzy = _fuzzy_candidates(basename, by_basename, basenames)
        if len(fuzzy) == 1:
            fixes = (SuggestedFix(kind="replace_link_target",
                                  replacement=_link_replacement(fuzzy[0], scanned.rel_path, link.is_wikilink),
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


def _markdown_doc(root: Path, scanned: ScannedFile) -> Any:
    """Разбор Markdown из кэша парсинга либо None, если кэш не пригоден.

    Промахом считается всё, что не даёт разбор, идентичный повторному: нет записи,
    не совпал хеш содержимого, другая версия разбора, битый JSON или запись чужой
    формы. Тогда вызывающий читает и парсит файл сам и кладет результат в кэш.
    """
    cached = read_parse_cache(root, scanned.rel_path, scanned.hash)
    if cached is None:
        return None
    try:
        return doc_from_payload(cached)
    except (KeyError, IndexError, TypeError, ValueError):
        return None


def build_mentions(root: Path, scanned_files: list[ScannedFile], records: list[dict[str, Any]],
                   all_paths: set[str]) -> list[dict[str, Any]]:
    """Плоский индекс упоминаний md → цели (план entity-catalog З2, T8).

    Источник — кеш парсинга (P1-3): validate_dataset уже разобрал md и положил
    payload'ы; здесь они читаются без повторного парсинга. Цель: существующий
    record_id → target_kind "record"; существующий файл → "doc"; неоднозначные
    wikilink-цели пропускаются (нет ложных mention'ов).
    """
    by_basename, _ = _basename_index(all_paths)
    record_ids = {r["record_id"] for r in records}
    mentions: list[dict[str, Any]] = []
    for scanned in sorted(scanned_files, key=lambda f: f.rel_path):
        if scanned.format != "markdown":
            continue
        doc = _markdown_doc(root, scanned)
        if doc is None:
            try:
                doc = parse_markdown(scanned.abs_path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError):
                continue
        for link in doc.links:
            target_kind: str | None = None
            target: str | None = None
            if link.target in record_ids:
                target_kind, target = "record", link.target
            elif link.is_wikilink:
                candidates = [c for c in _wikilink_candidates(link.target, by_basename) if c in all_paths]
                if len(candidates) == 1:
                    target_kind, target = "doc", candidates[0]
            else:
                normalized = resolve_link_target(scanned.rel_path, link.target)
                if normalized is not None and normalized in all_paths:
                    target_kind, target = "doc", normalized
            if target is None:
                continue
            mentions.append({
                "source_file": scanned.rel_path, "source_line": link.line,
                "source_fragment": link.fragment, "target": target, "target_kind": target_kind,
            })
    return mentions


def _collect_record_ids(scanned_files: list[ScannedFile]) -> set[str]:
    """record_id всех json-записей прогона — дёшево, по regexp по тексту (план entity-catalog З1).

    Полный разбор записей делает _validate_records; здесь нужна только устойчивость
    md-линк-чека к record-целям, а не данные записей.
    """
    ids: set[str] = set()
    for scanned in scanned_files:
        if scanned.format != "json":
            continue
        try:
            text = scanned.abs_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        m = re.search(r'"record_id"\s*:\s*"([^"]+)"', text)
        if m:
            ids.add(m.group(1))
    return ids


def _check_link_targets(dataset_id: str, scanned_files: list[ScannedFile], parsed_docs: dict[str, Any],
                        records: list[dict[str, Any]], all_paths: set[str]) -> list[Diagnostic]:
    """Фрагменты и record-цели ссылок md (план entity-catalog З1, T7).

    Резолвинг цели по порядку: существующий record_id → JSON Pointer фрагмент;
    иначе md-файл → якорь против slug'ов заголовков цели. Битые фрагменты дают
    markdown.pointer_invalid / markdown.anchor_not_found; существующие — проходят.
    """
    from todoc.adapters.formats.jsonfmt import resolve_pointer
    from todoc.adapters.formats.markdown import parse_markdown as _parse_md

    diags: list[Diagnostic] = []
    records_by_id = {r["record_id"]: (r.get("data") or {}) for r in records}
    scanned_by_path = {f.rel_path: f for f in scanned_files}
    for rel_path, doc in sorted(parsed_docs.items()):
        scanned = scanned_by_path.get(rel_path)
        if scanned is None:
            continue
        root_ref = scanned.abs_path.parents[len(scanned.rel_path.rstrip("/").split("/"))]
        for link in doc.links:
            if link.target in records_by_id:
                if not link.fragment:
                    continue
                if not link.fragment.startswith("/"):
                    diags.append(_diag(dataset_id, rel_path, "markdown.pointer_invalid",
                                       "Фрагмент record-цели должен быть JSON Pointer'ом (начинаться с '/').",
                                       location={"line": link.line, "column": link.column}))
                    continue
                try:
                    resolve_pointer(records_by_id[link.target], link.fragment)
                except (KeyError, IndexError):  # IndexError: выход за длину массива
                    diags.append(_diag(dataset_id, rel_path, "markdown.pointer_invalid",
                                       f"JSON Pointer не резолвится в записи: {link.fragment}",
                                       location={"line": link.line, "column": link.column}))
                continue
            if not link.fragment:
                continue
            by_basename, _ = _basename_index(all_paths)
            if link.is_wikilink:
                candidates = _wikilink_candidates(link.target, by_basename)
            else:
                normalized = resolve_link_target(rel_path, link.target)
                if normalized is None or normalized not in all_paths:
                    continue  # битую цель уже отметил линк-чек
                candidates = [normalized]
            if len(candidates) != 1:
                continue  # неоднозначность не флагаем ложным якорем
            target_rel = candidates[0]
            target_scanned = scanned_by_path.get(target_rel)
            if target_scanned is None or target_scanned.format != "markdown":
                diags.append(_diag(dataset_id, rel_path, "markdown.anchor_not_found",
                                   f"Якорь на не-markdown цель: {link.fragment}",
                                   location={"line": link.line, "column": link.column}))
                continue
            target_doc = parsed_docs.get(target_rel)
            if target_doc is None:
                try:
                    target_doc = _parse_md(target_scanned.abs_path.read_text(encoding="utf-8"))
                    parsed_docs[target_rel] = target_doc
                except (OSError, UnicodeDecodeError):
                    continue
            anchors = {h.anchor.lower() for h in target_doc.headings}
            if link.fragment.lower() not in anchors:  # как в Obsidian: регистр якоря не важен
                diags.append(_diag(dataset_id, rel_path, "markdown.anchor_not_found",
                                   f"В цели нет раздела с якорем: {link.fragment}",
                                   location={"line": link.line, "column": link.column}))
    return diags


def _check_markdown_links(dataset_id: str, scanned: ScannedFile, root: Path, all_paths: set[str],
                          basename_index: tuple[dict[str, list[str]], list[str]] | None = None,
                          doc: Any = None, record_ids: set[str] | None = None) -> list[Diagnostic]:
    """Report local links whose target is not in the scanned file set.

    Targets are normalized by ``resolve_link_target`` (same code path as the
    index/backlinks), so validator and index can never disagree about what a
    link points to. Wikilinks resolve by basename/stem anywhere in the root.

    ``doc`` — уже готовый разбор: вызывающий, который только что разбирал файл,
    отдаёт его сюда, и файл не читается второй раз (P1-3).
    """
    diags: list[Diagnostic] = []
    if doc is None:
        try:
            text = scanned.abs_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return [Diagnostic(dataset_id, stable_id(scanned.rel_path, "markdown.unreadable"), "markdown.unreadable", "error", scanned.rel_path, "Cannot read Markdown file.")]
        doc = parse_markdown(text)
    by_basename, basenames = basename_index if basename_index is not None else _basename_index(all_paths)
    record_ids = record_ids or set()
    for link in doc.links:
        # план entity-catalog З1: цель — существующий record_id — не файл-ссылка;
        # фрагментные проверки (pointer/якорь) делает _check_link_targets.
        if link.target in record_ids:
            continue
        if link.is_wikilink:
            if not link.target:
                continue
            if _wikilink_candidates(link.target, by_basename):
                continue
            if ":" in link.target:
                # план entity-catalog З1: формой "type:slug" выглядят record-цели —
                # файлы с двоеточием в имени вне конвенции.
                diags.append(_diag(dataset_id, scanned.rel_path, "markdown.record_not_found",
                                   f"Запись не найдена: {link.target}",
                                   location={"line": link.line, "column": link.column}))
                continue
            diags.append(_link_diagnostic(dataset_id, scanned, link, [], link.target, by_basename, basenames))
            continue
        normalized = resolve_link_target(scanned.rel_path, link.target)
        if normalized is None or normalized in all_paths:
            continue
        if ":" in link.target and normalized is not None and normalized not in all_paths:
            diags.append(_diag(dataset_id, scanned.rel_path, "markdown.record_not_found",
                               f"Запись не найдена: {link.target}",
                               location={"line": link.line, "column": link.column}))
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


_TAG_RE = re.compile(r"^[a-z0-9\u0400-\u04ff]+(-[a-z0-9\u0400-\u04ff]+)*$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_WIKILINK_RE = re.compile(r"^\[\[[^\[\]]+\]\]$")


def _check_meta_fields(dataset_id: str, rel_path: str, front_matter: dict[str, Any]) -> list[Diagnostic]:
    """План doc-tags Задача 1: форма опциональных полей tags/created/updated/related.

    Поля опциональны (absence ≠ ошибка); пустой tags допустим; существование
    целей related в v1 не проверяется — только wikilink-форма "[[имя]]".
    """
    diags: list[Diagnostic] = []
    tags = front_matter.get("tags")
    if tags is not None:
        ok = isinstance(tags, list) and all(
            isinstance(x, str) and _TAG_RE.match(x) and 2 <= len(x) <= 32 for x in tags)
        if not ok or len(tags) > 8:
            diags.append(_diag(dataset_id, rel_path, "markdown.tags_invalid",
                               "tags: ожидаются 0–8 kebab-тегов (строки 2–32, [a-z0-9-], кириллица допустима)."))
    for key, code in (("created", "markdown.created_invalid"),
                      ("updated", "markdown.updated_invalid")):
        value = front_matter.get(key)
        if value is not None and (not isinstance(value, str) or not _DATE_RE.match(value)):
            diags.append(_diag(dataset_id, rel_path, code,
                               f"{key}: ожидалась дата YYYY-MM-DD, получено {value!r}."))
    related = front_matter.get("related")
    if related is not None:
        if not isinstance(related, list) or not all(
                isinstance(x, str) and _WIKILINK_RE.match(x) for x in related):
            diags.append(_diag(dataset_id, rel_path, "markdown.related_invalid",
                               "related: ожидаются wikilinks формы [[имя]] (существование цели в v1 не проверяется)."))
    return diags


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
    alternatives = [s for s in (descriptor.get("any_of_sections") or [])
                    if isinstance(s, str) and s.strip()]
    if alternatives:
        # «Хотя бы один из»: дельте достаточно любого из ADDED / MODIFIED / REMOVED.
        # required_sections здесь не подходит — оно потребовало бы все три сразу.
        selectors = [parse_heading_selector(s) for s in alternatives]
        if not any(_heading_matches(h, level, title) for level, title in selectors for h in headings):
            diags.append(_diag(
                dataset_id, rel_path, "markdown.section.missing",
                "None of the alternative sections present: " + ", ".join(alternatives),
                location={"line": 1, "column": 1},
                evidence=f"doc_type declares any_of_sections: {', '.join(alternatives)}",
                fixes=(SuggestedFix(kind="add_heading", replacement=alternatives[0],
                                    basis="doc_type.any_of_sections", autofixable=False),),
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
    parsed_docs: dict[str, Any] = {}  # план entity-catalog З1: разбор md одного прогона
    doc_info: dict[str, dict[str, Any]] = {}
    doc_type_descriptors: dict[str, Any] = {}
    if registry is not None:
        doc_type_descriptors = getattr(registry, "doc_types", None) or (
            registry.get("doc_types", {}) if isinstance(registry, dict) else {})
    doc_schemas = _load_schemas(root, registry, dataset, "doc_type", _doc_types_of)
    # план entity-catalog З1: record_id нужны md-циклу (skip record-целей) —
    # дешёвый regexp-сбор по тексту json-файлов (полный разбор записей — ниже).
    record_ids_known = _collect_record_ids(scanned_files)

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
        front_matter: dict[str, Any] = {}
        title = ""
        headings: list[Any] = []
        # Сквозной кэш парсинга (P1-3): при попадании файл не читается и не парсится.
        doc = _markdown_doc(root, scanned) if fmt == "markdown" else None
        if doc is not None:
            parsed_docs[scanned.rel_path] = doc  # план entity-catalog З1: кеш тоже в прогон
        if doc is None:
            try:
                text = scanned.abs_path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                diags.append(_diag(dataset_id, scanned.rel_path, "file.unreadable", "Cannot read file as UTF-8."))
                doc_info[scanned.rel_path] = {"doc_type": "unknown", "rule_source": "default", "front_matter": {}, "title": "", "format": fmt}
                continue
            if fmt == "markdown":
                doc = parse_markdown(text)
                write_parse_cache(root, scanned.rel_path, scanned.hash, doc_to_payload(doc))
                parsed_docs[scanned.rel_path] = doc
        if fmt == "markdown":
            front_matter = doc.front_matter
            title = doc.title
            headings = doc.headings
            for lineno, message in doc.warnings:
                diags.append(_diag(dataset_id, scanned.rel_path, "markdown.front_matter.yaml_unsafe",
                                   message, severity="warning", location={"line": lineno, "column": 1}))
            # Разбор уже в руках — второй раз файл не читается и не парсится.
            diags.extend(_check_markdown_links(dataset_id, scanned, root, all_paths, by_basename,
                                               doc=doc, record_ids=record_ids_known))
            diags.extend(_check_meta_fields(dataset_id, scanned.rel_path, front_matter))  # план doc-tags З1: только markdown
        elif fmt == "csv":
            csv_doc = parse_csv(text, max_rows=max_rows)
            for err in csv_doc.errors:
                code, _, rest = err.partition(": ")
                diags.append(_diag(dataset_id, scanned.rel_path, code, rest or err))
        elif fmt == "json":
            value, errors = parse_json(text, max_depth=max_depth)
            for err in errors:
                code, _, rest = err.partition(": ")
                # У JsonError позиция есть всегда (P1-8): её восстанавливает проход
                # по тексту, потому что стандартный json не сообщает смещений ни для
                # object_pairs_hook, ни для parse_constant.
                location: dict[str, Any] = ({"line": err.line, "column": err.column or 1}
                                            if err.line else {})
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
        loaded_schema = doc_schemas.get(doc_type)
        if loaded_schema and front_matter:
            # Front matter документов раньше не проверялся вообще; схема объявляется
            # в описателе doc_type и остаётся необязательной (план §19, вариант (a)).
            schema, evidence = loaded_schema
            for message in validate_against_schema(front_matter, schema):
                pointer, _, rest = message.partition(": ")
                diags.append(_diag(
                    dataset_id, scanned.rel_path, "document.schema_violation", rest or message,
                    location={"pointer": pointer, "doc_type": doc_type}, evidence=evidence,
                ))
        doc_info[scanned.rel_path] = {
            "doc_type": doc_type, "rule_source": source, "front_matter": front_matter, "title": title, "format": fmt,
        }

    # Record validation: JSON files with record_id/entity_type.
    records = _validate_records(dataset_id, root, scanned_files, doc_info, dataset, registry)
    diags.extend(_check_link_targets(dataset_id, scanned_files, parsed_docs, records[1], all_paths))
    diags.extend(records[0])
    diags.extend(_skills_diagnostics(dataset_id, root))
    diags.extend(_folder_configs_diagnostics(dataset_id, root))
    return diags, doc_info


def _folder_configs_diagnostics(dataset_id: str, root: Path) -> list[Diagnostic]:
    """Merge folder-config diagnostics (codes ``folder.*``) into a dataset run.

    Отсутствие конфигов — ноль диагностик и ноль стоимости сверх одного обхода
    папок; ошибки конфига не валидируются как JSON-документы (файл исключён из
    скана), только этими dedicated кодами.
    """
    from todoc.application.folder_config import validate_folder_configs

    out: list[Diagnostic] = []
    for d in validate_folder_configs(root):
        out.append(Diagnostic(
            dataset_id=dataset_id,
            id=stable_id(d["path"], d["code"], d["message"]),
            code=d["code"], severity=d["severity"], path=d["path"], message=d["message"],
            location=d["location"], evidence=d["evidence"],
            suggested_fixes=tuple(
                SuggestedFix(kind="manual", replacement=fix, basis="folder-config",
                             autofixable=False, requires_review=True)
                for fix in d["suggested_fixes"]),
        ))
    return out


def _skills_diagnostics(dataset_id: str, root: Path) -> list[Diagnostic]:
    """Merge skills-vault diagnostics into a dataset validate run.

    The vault is ``<root>/skills``; an absent vault contributes nothing. The
    scanner returns vault-relative dict diagnostics — here they become house
    Diagnostic objects with dataset binding and root-relative paths.
    """
    vault = root / "skills"
    if not vault.is_dir():
        return []
    from todoc.application.skills import scan_skills, validate_skills

    skills, vault_diags = scan_skills(vault)
    vault_diags.extend(validate_skills(vault, skills))
    out: list[Diagnostic] = []
    for d in vault_diags:
        path = f"skills/{d['path']}"
        out.append(Diagnostic(
            dataset_id=dataset_id,
            id=stable_id(path, d["code"], d["message"]),
            code=d["code"], severity=d["severity"], path=path, message=d["message"],
            location=d["location"], evidence=d["evidence"],
            suggested_fixes=tuple(
                SuggestedFix(kind="manual", replacement=fix, basis="skills standard",
                             autofixable=False, requires_review=True)
                for fix in d["suggested_fixes"]),
        ))
    return out


def _load_schemas(root: Path, registry: Any, dataset: dict[str, Any], kind: str,
                  types_of: Any) -> dict[str, tuple[dict[str, Any], str]]:
    """JSON Schema of every type of a kind, with the path it was loaded from.

    A schema lives in its type's folder, so the registry is the only way to find
    it — no top-level catalog is scanned. Returns ``{type_id: (schema, evidence)}``;
    keeping the path lets a violation name the exact file that rejected the value.
    Один механизм для записей и документов: различается только kind и источник типов.
    """
    schemas: dict[str, tuple[dict[str, Any], str]] = {}
    for type_id, descriptor in sorted(types_of(registry).items()):
        path = schema_file(root, dataset, kind, descriptor)
        if path is None or not path.is_file():
            continue
        try:
            data = load_json_file(path)
        except ValidationError:
            continue
        if isinstance(data, dict):
            schemas[type_id] = (data, f"schema: {_rel_to_root(root, path)}")
    return schemas


def _rel_to_root(root: Path, path: Path) -> str:
    """Path as the user writes it: relative to DATA_ROOT when it is inside it."""
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def _entity_types_of(registry: Any) -> dict[str, Any]:
    """Entity types of a loaded TypeRegistry (a plain mapping works too)."""
    entity_types = getattr(registry, "entity_types", None)
    if entity_types is None and isinstance(registry, dict):
        entity_types = registry.get("entity_types")
    return entity_types or {}


def _doc_types_of(registry: Any) -> dict[str, Any]:
    """Doc types of a loaded TypeRegistry (a plain mapping works too)."""
    doc_types = getattr(registry, "doc_types", None)
    if doc_types is None and isinstance(registry, dict):
        doc_types = registry.get("doc_types")
    return doc_types or {}


def _key_location(text: str, key: str) -> dict[str, Any]:
    r"""Line of the first occurrence of a JSON key, for record diagnostics.

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
    # BUG-010: ключ может быть записан unicode-escape ("\u006frder") — литерала в тексте нет
    pattern = re.compile('"' + "".join(f"(?:{re.escape(ch)}|\\\\u{ord(ch):04x})" for ch in key) + '"',
                         re.IGNORECASE)
    for lineno, line in enumerate(text.splitlines(), start=1):
        m = pattern.search(line)
        if m:
            return {"line": lineno, "column": m.start() + 1}
    return {}


def _validate_records(
    dataset_id: str, root: Path, scanned_files: list[ScannedFile], doc_info: dict[str, dict[str, Any]],
    dataset: dict[str, Any] | None = None, registry: Any = None,
) -> tuple[list[Diagnostic], list[dict[str, Any]]]:
    diags: list[Diagnostic] = []
    records: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    schemas = _load_schemas(root, registry, dataset, "entity_type", _entity_types_of)
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
        loaded = schemas.get(entity_type)
        if loaded:
            schema, evidence = loaded
            for message in validate_against_schema(value, schema):
                pointer, _, rest = message.partition(": ")
                location = {"pointer": pointer, "entity_type": entity_type}
                location.update(_key_location(text, pointer.rsplit("/", 1)[-1]))
                diags.append(_diag(
                    dataset_id, scanned.rel_path, "record.schema_violation", rest or message,
                    location=location, evidence=evidence,
                ))
        defect = temporal.interval_defect(value)
        if defect:
            code, message, field = defect
            location = {"pointer": f"/{field}", "entity_type": entity_type}
            location.update(_key_location(text, field))
            diags.append(_diag(dataset_id, scanned.rel_path, code, message, location=location))
        records.append({
            "record_id": record_id, "entity_type": entity_type, "dataset_id": dataset_id,
            "path": scanned.rel_path, "hash": scanned.hash, "data": value,
        })
    return diags, records


def _pointer_key(pointer: str) -> str:
    """Последний нечисловой сегмент pointer'а — ключ, по которому ищется строка."""
    for part in reversed(pointer.strip("/").split("/")):
        if part and not part.isdigit():
            return part
    return ""


def validate_relations(
    dataset_id: str,
    records: list[dict[str, Any]],
    known_relation_types: set[str],
    texts: dict[str, str] | None = None,
) -> list[Diagnostic]:
    """Check relations: declared type_id must exist, target must exist.

    ``known_relation_types`` is the registry's set of relation_type ids and is
    required: an unknown ``type_id`` is a defect, so there is no mode in which
    the check is skipped.

    ``texts`` (путь → текст записи) необязателен и нужен только для позиций: с ним
    диагностика несёт ``line``/``column`` по тому же соглашению, что и
    ``record.schema_violation`` — строка ключа плюс точный ``pointer``.
    """
    diags: list[Diagnostic] = []
    known = {r["record_id"] for r in records}
    for record in records:
        text = (texts or {}).get(record["path"], "")

        def located(pointer: str) -> dict[str, Any]:
            return {"pointer": pointer, **_key_location(text, _pointer_key(pointer))}

        relations = record["data"].get("relations")
        if not isinstance(relations, list):
            if relations is not None:
                diags.append(_diag(dataset_id, record["path"], "relation.malformed",
                                   "Field 'relations' must be a list of objects.",
                                   location=located("/relations")))
            continue
        for index, rel in enumerate(relations):
            # Exact structural address: relations live in a JSON record, so an
            # RFC 6901 pointer locates the offending entry without guessing a line.
            where = located(f"/relations/{index}")
            if not isinstance(rel, dict):
                diags.append(_diag(dataset_id, record["path"], "relation.malformed",
                                   "Relation entry must be an object.", location=where))
                continue
            type_id = str(rel.get("type_id", ""))
            if known_relation_types is not None and type_id not in known_relation_types:
                diags.append(_diag(dataset_id, record["path"], "relation.unknown_type",
                                   f"Unknown relation type_id: {type_id or '<empty>'}", location=where))
            target = (rel.get("target") or {}).get("id", "") if isinstance(rel.get("target"), dict) else ""
            if target and target not in known:
                diags.append(_diag(dataset_id, record["path"], "relation.dangling_target",
                                   f"Relation target not found: {target}",
                                   location=located(f"/relations/{index}/target/id")))
            elif not target:
                diags.append(_diag(dataset_id, record["path"], "relation.missing_target",
                                   f"Relation {type_id or '<empty>'} has no target.id.",
                                   location=located(f"/relations/{index}/target/id")))
            defect = temporal.interval_defect(rel)
            if defect:
                code, message, field = defect
                diags.append(_diag(dataset_id, record["path"], code, message,
                                   location=located(f"/relations/{index}/{field}")))
    return diags
