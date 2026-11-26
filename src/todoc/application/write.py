"""Review-first writes: WritePlan, create record, fix, edit (E9)."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from todoc.adapters.filesystem.scanner import atomic_write, file_hash
from todoc.adapters.formats.jsonfmt import parse_json, validate_against_schema
from todoc.application.registry import invalidate_parse_cache
from todoc.domain.models import WritePlan
from todoc.errors import ConflictError, ValidationError


def _sha(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


#: Characters a Windows file name cannot contain, plus the two path separators:
#: a ``/`` coming from an identifier would silently create a directory (or
#: escape the dataset), and separators belong to the template, not to the value.
_UNSAFE_NAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')

#: Device names Windows reserves regardless of extension.
_RESERVED_NAMES = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{i}" for i in range(1, 10)}
    | {f"LPT{i}" for i in range(1, 10)}
)


def portable_name(value: str) -> str:
    """Make a value substituted into a path template safe to create everywhere.

    ``record_id`` is an identifier, not a file name: ``workout:2026-11-25`` is a
    valid id, but ``:`` is illegal in a Windows file name, so the record could
    not be checked out there. Trailing dots and spaces are stripped for the same
    reason, and a reserved device name is prefixed rather than written as is.
    """
    cleaned = _UNSAFE_NAME_CHARS.sub("-", value).strip(" .")
    if cleaned.split(".")[0].upper() in _RESERVED_NAMES:
        cleaned = f"_{cleaned}"
    return cleaned or "_"


def _fill_path_template(template: str, record_id: str, slug: str) -> str:
    """Substitute ``{record_id}``/``{slug}`` in a single pass.

    One pass matters: substituting ``{record_id}`` first and ``{slug}`` second
    would expand a literal ``{slug}`` that happened to appear inside a record id.
    """
    values = {"record_id": portable_name(record_id), "slug": portable_name(slug)}
    return re.sub(r"\{(record_id|slug)\}", lambda m: values[m.group(1)], template)


def create_record_plan(dataset: dict[str, Any], entity_types: dict[str, Any], record: dict[str, Any],
                       existing_ids: set[str], existing_paths: set[str],
                       schema: dict[str, Any] | None = None) -> WritePlan:
    """Build a WritePlan for a new JSON record (create-only, no-overwrite).

    ``schema`` is the entity type's JSON Schema, when the dataset has one: it is
    enforced here so an invalid record cannot be written and only surface on the
    next ``validate``.
    """
    dataset_id = dataset["dataset_id"]
    entity_type = str(record.get("entity_type", ""))
    record_id = str(record.get("record_id", ""))
    if entity_type not in entity_types:
        raise ValidationError(f"Unknown entity_type: {entity_type!r}", "record.unknown_entity_type")
    if not record_id:
        raise ValidationError("Record has no record_id", "record.missing_id")
    if record_id in existing_ids:
        raise ConflictError(f"record_id already exists: {record_id}", "record.duplicate_id")
    descriptor = entity_types[entity_type]
    # Schema first: it reports every violation at once with pointers, which is more
    # actionable than the coarse "field is absent" pre-check that follows it.
    if schema:
        violations = validate_against_schema(record, schema)
        if violations:
            raise ValidationError("; ".join(violations), "record.schema_violation")
    for field_name in descriptor.get("required_fields") or []:
        if field_name not in record:
            raise ValidationError(f"Missing required field: {field_name}", "record.missing_field")
    path_template = str(descriptor.get("path_template") or f"records/{entity_type}/{{record_id}}.json")
    # "type:local-part" — split on the first colon only, so an id whose local
    # part itself contains one (``note:2026:11:25``) keeps all of it.
    slug = record_id.split(":", 1)[-1]
    target = _fill_path_template(path_template, record_id, slug)
    if target in existing_paths:
        raise ConflictError(f"Target already exists: {target}", "record.target_exists")
    if target.startswith("../") or "/../" in target or target.startswith("/"):
        raise ValidationError(f"Unsafe path_template result: {target}", "record.unsafe_path")
    content = json.dumps(record, indent=2, ensure_ascii=False) + "\n"
    return WritePlan(
        dataset_id=dataset_id,
        target_path=target,
        new_content=content,
        expected_hash=None,
        new_hash=_sha(content),
        basis=f"Create {entity_type} record {record_id}",
        validations=("schema", "relations", "no-overwrite"),
    )


def apply_write_plan(root: Path, plan: WritePlan, expected_hash: str | None = None,
                     history: Any | None = None) -> str:
    """Apply a WritePlan atomically. Returns new hash.

    ``history`` (a ``HistoryRecorder``) receives one journal event when given; passing None
    keeps the previous behaviour and is what tests that do not care about history use.
    """
    target = root / plan.target_path
    if plan.expected_hash is None:
        if target.exists():
            raise ConflictError(f"Target already exists: {plan.target_path}", "write.target_exists")
    else:
        if not target.is_file():
            raise ConflictError(f"Target does not exist: {plan.target_path}", "write.target_missing")
        current = file_hash(target)
        if current != plan.expected_hash:
            raise ConflictError(f"Hash mismatch for {plan.target_path}: expected {plan.expected_hash}, got {current}",
                                "write.hash_mismatch")
        if expected_hash is not None and expected_hash != plan.expected_hash:
            raise ConflictError("Caller expected_hash does not match plan", "write.hash_mismatch")
    before = target.read_bytes() if target.is_file() else None
    atomic_write(target, plan.new_content)
    # Кэш парсинга сбрасывается вместе с данными, которые он описывает (P1-3).
    invalidate_parse_cache(root, plan.target_path)
    if history is not None:
        # kind различает документ и запись по расширению цели: у WritePlan нет отдельного
        # флага формата, а список видов зафиксирован в плане (docs/plan/history-and-changes.md).
        prefix = "doc" if Path(plan.target_path).suffix.lower() == ".md" else "record"
        history.record(plan.target_path, before, plan.new_content.encode("utf-8"),
                       f"{prefix}.create" if before is None else f"{prefix}.edit",
                       plan.basis or f"WritePlan {plan.target_path}")
    return plan.new_hash


def apply_fix(root: Path, rel_path: str, old_target: str, new_target: str, expected_hash: str | None = None,
              history: Any | None = None) -> str:
    """Replace one link target in a Markdown file (review-first fix)."""
    target = root / rel_path
    if not target.is_file():
        raise ValidationError(f"File not found: {rel_path}", "fix.file_missing")
    current_hash = file_hash(target)
    if expected_hash is not None and current_hash != expected_hash:
        raise ConflictError(f"Hash mismatch for {rel_path}", "write.hash_mismatch")
    text = target.read_text(encoding="utf-8")
    if old_target not in text:
        raise ValidationError(f"Target {old_target!r} not found in {rel_path}", "fix.target_not_found")
    new_text = text.replace(old_target, new_target, 1)
    before = target.read_bytes()
    atomic_write(target, new_text)
    invalidate_parse_cache(root, rel_path)
    if history is not None:
        history.record(rel_path, before, new_text.encode("utf-8"), "doc.fix",
                       f"fix link {old_target!r} -> {new_target!r}")
    return _sha(new_text)


def apply_edit_ops(root: Path, rel_path: str, ops: list[dict[str, Any]], expected_hash: str | None = None,
                   history: Any | None = None, bump_updated: bool = False) -> tuple[str, bool]:
    r"""Apply line-based edit ops (BUG-004: не только замена).

    Формы op (применяются последовательно; номера строк относятся к состоянию
    файла после предыдущих op):
    - ``{"line": N, "text": "..."}`` — replace строки N (обратная совместимость,
      отсутствие поля ``op`` = replace);
    - ``{"op": "insert_after", "line": N, "text": str | [str, ...]}`` — вставка
      после строки N (N=0 — в начало файла, N=len(lines) — в конец);
    - ``{"op": "delete", "line": N[, "to": M]}`` — удаление строки N или диапазона N–M.
    """
    target = root / rel_path
    if not target.is_file():
        raise ValidationError(f"File not found: {rel_path}", "edit.file_missing")
    current_hash = file_hash(target)
    if expected_hash is not None and current_hash != expected_hash:
        raise ConflictError(f"Hash mismatch for {rel_path}", "write.hash_mismatch")
    lines = target.read_text(encoding="utf-8").splitlines()
    updated_bumped = False
    if bump_updated and lines and lines[0] == "---":
        # План doc-tags З3: бамп updated в той же атомарной записи (до записи файла).
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        for i in range(1, len(lines)):
            if lines[i] == "---":
                break  # конец fm
            if lines[i].startswith("updated:"):
                if lines[i] != f"updated: {today}":
                    lines[i] = f"updated: {today}"
                    updated_bumped = True
                break
    for op in ops:
        kind = op.get("op", "replace")
        if kind in ("replace", None):
            line_no = int(op.get("line", 0))
            if line_no < 1 or line_no > len(lines):
                raise ValidationError(f"Line out of range: {line_no}", "edit.line_out_of_range")
            lines[line_no - 1] = str(op.get("text", ""))
        elif kind == "insert_after":
            line_no = int(op.get("line", 0))
            if line_no < 0 or line_no > len(lines):
                raise ValidationError(f"Line out of range: {line_no}", "edit.line_out_of_range")
            texts = op.get("text", "")
            if isinstance(texts, str):
                texts = [texts]
            lines[line_no:line_no] = [str(x) for x in texts]
        elif kind == "delete":
            start = int(op.get("line", 0))
            end = int(op.get("to", start))
            if start < 1 or end < start or end > len(lines):
                raise ValidationError(f"Line out of range: {start}-{end}", "edit.line_out_of_range")
            del lines[start - 1:end]
        else:
            raise ValidationError(f"Unknown edit op: {kind}", "edit.op_unknown")
    new_text = "\n".join(lines) + "\n"
    before = target.read_bytes()
    atomic_write(target, new_text)
    invalidate_parse_cache(root, rel_path)
    if history is not None:
        history.record(rel_path, before, new_text.encode("utf-8"), "doc.edit",
                       f"docs edit {len(ops)} ops" + (" + bump updated" if updated_bumped else ""))
    return _sha(new_text), updated_bumped


def load_input_record(path: Path) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValidationError(f"Cannot read input file: {exc}", "record.unreadable_input") from exc
    value, errors = parse_json(text)
    if errors:
        raise ValidationError(f"Invalid JSON in input file: {errors[0]}", "record.invalid_json")
    if not isinstance(value, dict):
        raise ValidationError("Input record must be a JSON object", "record.invalid_input")
    return value


def create_document_plan(dataset: dict[str, Any], doc_types: dict[str, Any], doc_type_id: str,
                         title: str, target_path: str, template_text: str | None = None,
                         values: dict[str, str] | None = None,
                         existing_paths: set[str] | None = None) -> WritePlan:
    """Build a WritePlan for a new Markdown document from its type's starter template.

    ``template_text`` is the rendered source of ``<type>/template.<ext>``; when the
    type declares none, the document starts as a bare title heading. Placeholders
    are substituted as plain text (see ``render_template``), so a template cannot
    inject anything the caller did not supply.
    """
    from todoc.typing_system.descriptors import render_template

    dataset_id = dataset["dataset_id"]
    if doc_type_id is not None and doc_type_id not in doc_types:
        raise ValidationError(f"Unknown doc_type: {doc_type_id!r}", "types.unknown")
    if not title.strip():
        raise ValidationError("Document title must not be empty", "docs.empty_title")
    if target_path.startswith("../") or "/../" in target_path or target_path.startswith("/"):
        raise ValidationError(f"Unsafe target path: {target_path}", "docs.unsafe_path")
    if existing_paths is not None and target_path in existing_paths:
        raise ConflictError(f"Target already exists: {target_path}", "docs.target_exists")
    content = render_template(template_text, values or {}) if template_text else f"# {title}\n\n"
    if not content.endswith("\n"):
        content += "\n"
    # План doc-tags З3: движок — единственный писатель created/updated; docs new
    # строит front matter сам (шаблоны fm не содержат). Опциональные tags/related
    # оставляются агенту и миграции.
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    fm_lines = ["---", f'id: {(values or {}).get("id", f"doc:{target_path}")}',
                f'title: "{title.replace(chr(34), chr(92) + chr(34))}"']
    if doc_type_id:
        fm_lines.append(f"doc_type: {doc_type_id}")
    fm_lines += ["lang: ru", f"created: {today}", f"updated: {today}", "---", ""]
    content = "\n".join(fm_lines) + "\n" + content
    descriptor = doc_types.get(doc_type_id or "", {})
    # Review-first, as with records: a document whose own type forbids its shape is
    # refused before anything touches the disk, not reported after the fact.
    violations = structure_violations(content, descriptor)
    if violations:
        raise ValidationError("; ".join(violations), "types.template_invalid")
    return WritePlan(
        dataset_id=dataset_id,
        target_path=target_path,
        new_content=content,
        expected_hash=None,
        new_hash=_sha(content),
        basis=f"Create {doc_type_id or 'untitled'} document {title!r}",
        validations=("template", "structure" if descriptor.get("required_sections") else "none", "no-overwrite"),
    )


def structure_violations(content: str, descriptor: dict[str, Any]) -> list[str]:
    """Error-level structure findings for rendered Markdown against a doc_type.

    Used before a write so an invalid starter template cannot create a document
    that its own type would reject on the next ``validate``.
    """
    from todoc.adapters.formats.markdown import parse_markdown
    from todoc.application.validator import _check_structure

    if not descriptor.get("required_sections") and not descriptor.get("section_rules"):
        return []
    headings = parse_markdown(content).headings
    return [d.message for d in _check_structure("", "<new>", headings, descriptor) if d.severity == "error"]
