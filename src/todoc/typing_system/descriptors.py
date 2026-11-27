"""Type descriptor loading and validation (all JSON, all versioned)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from todoc.errors import ValidationError


def load_json_file(path: Path) -> Any:
    """Load a JSON file, raising ValidationError on syntax errors."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValidationError(f"Cannot read {path}: {exc}", "config.unreadable") from exc
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValidationError(f"Invalid JSON in {path}: {exc}", "config.invalid_json") from exc


def require_schema_version(data: Any, path: Path) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValidationError(f"{path}: top-level value must be an object", "config.invalid_schema")
    if data.get("schema_version") != 1:
        raise ValidationError(
            f"{path}: schema_version must be 1, got {data.get('schema_version')!r}",
            "config.unsupported_version",
        )
    return data


class TypeRegistry:
    """In-memory registry of dir/doc/entity/relation type descriptors."""

    def __init__(self) -> None:
        self.dir_types: dict[str, dict[str, Any]] = {}
        self.doc_types: dict[str, dict[str, Any]] = {}
        self.entity_types: dict[str, dict[str, Any]] = {}
        self.relation_types: dict[str, dict[str, Any]] = {}

    def _load_dir(self, base: Path, kind: str, store: dict[str, dict[str, Any]]) -> None:
        if not base.is_dir():
            return
        for type_dir in sorted(base.iterdir()):
            if not type_dir.is_dir():
                continue
            type_file = type_dir / "type.json"
            if not type_file.is_file():
                continue
            data = require_schema_version(load_json_file(type_file), type_file)
            type_id = data.get("type_id")
            if not isinstance(type_id, str) or not type_id:
                raise ValidationError(f"{type_file}: type_id is required", "config.invalid_schema")
            if type_id in store:
                raise ValidationError(f"Duplicate {kind} type_id: {type_id}", "config.duplicate_type")
            store[type_id] = data

    def load(self, root: Path, dataset: dict[str, Any]) -> None:
        todoc_dir = root / ".todoc"
        self._load_dir(todoc_dir / dataset.get("directory_types", "dir_types"), "dir_type", self.dir_types)
        self._load_dir(todoc_dir / dataset.get("document_types", "doc_types"), "doc_type", self.doc_types)
        self._load_dir(todoc_dir / dataset.get("entity_types", "entity_types"), "entity_type", self.entity_types)
        self._load_dir(todoc_dir / dataset.get("relation_types", "relation_types"), "relation_type", self.relation_types)

    def validate_references(self, dir_rules: list[dict[str, Any]], doc_rules: list[dict[str, Any]]) -> None:
        """Every assigned dir_type/doc_type must exist in the registry."""
        for rule in dir_rules:
            assigned = (rule.get("assign") or {}).get("dir_type")
            if assigned is not None and assigned not in self.dir_types:
                raise ValidationError(
                    f"Rule {rule.get('id')}: unknown dir_type {assigned!r}",
                    "config.unknown_type",
                )
        for rule in doc_rules:
            assigned = (rule.get("assign") or {}).get("doc_type")
            if assigned is not None and assigned not in self.doc_types:
                raise ValidationError(
                    f"Rule {rule.get('id')}: unknown doc_type {assigned!r}",
                    "config.unknown_type",
                )


# ---------------------------------------------------------------------------
# Descriptor surface: templates, CRUD prompts, structure rules
# ---------------------------------------------------------------------------

#: Keys each descriptor kind accepts. Unknown keys are reported by
#: ``check-config`` instead of being silently ignored: a configuration that
#: quietly accepts a rule it never enforces is worse than one that refuses it.
KIND_FIELDS: dict[str, set[str]] = {
    "dir_type": {"schema_version", "type_id", "version", "kind", "description"},
    "doc_type": {"schema_version", "type_id", "version", "kind", "description", "format",
                 "template", "prompts", "required_sections", "section_rules",
                 "any_of_sections", "schema", "allowed_statuses", "generated"},
    "entity_type": {"schema_version", "type_id", "version", "kind", "description", "format",
                    "required_fields", "path_template", "views", "metric_fields",
                    "template", "prompts", "schema"},
    "relation_type": {"schema_version", "type_id", "version", "kind", "description", "endpoints"},
}

#: Keys each ``metric_fields.<field>`` entry accepts.
#:
#: ``prompt`` is a natural-language description of the metric, not an expression:
#: the core aggregates by summing one numeric field and never evaluates anything, so a
#: declarative ``formula`` here would be config the core silently ignores. Derived
#: metrics (``reps × weight_kg``) are a stored field or the caller's arithmetic — the
#: prompt tells an agent what the number means and how to read it.
METRIC_FIELD_KEYS: set[str] = {"unit", "prompt"}

#: The four starter prompts every type may ship, one per CRUD operation.
PROMPT_OPERATIONS: tuple[str, ...] = ("read", "create", "edit", "delete")

#: Default layout inside a type folder: ``template.<ext>`` + ``prompts/<op>.md``.
DEFAULT_TEMPLATE_BASENAME = "template"
PROMPTS_DIRNAME = "prompts"

FORMAT_EXTENSIONS: dict[str, str] = {"markdown": "md", "json": "json", "csv": "csv"}

#: Placeholders a template may use. Values are plain strings, never evaluated.
TEMPLATE_PLACEHOLDERS: tuple[str, ...] = ("title", "slug", "date", "type_id", "id", "format")


def type_kind_dir(dataset: dict[str, Any], kind: str) -> str:
    """Dataset-configured directory name for a kind (falls back to defaults)."""
    key = {"dir_type": "directory_types", "doc_type": "document_types",
           "entity_type": "entity_types", "relation_type": "relation_types"}[kind]
    return str(dataset.get(key, {"dir_type": "dir_types", "doc_type": "doc_types",
                                 "entity_type": "entity_types",
                                 "relation_type": "relation_types"}[kind]))


def type_dir(root: Path, dataset: dict[str, Any], kind: str, type_id: str) -> Path:
    return root / ".todoc" / type_kind_dir(dataset, kind) / type_id


def template_file(root: Path, dataset: dict[str, Any], kind: str, descriptor: dict[str, Any]) -> Path | None:
    """Resolve the starter template of a type, or None when it declares none."""
    declared = descriptor.get("template")
    if declared is None:
        return None
    if not isinstance(declared, str) or not declared:
        return None
    base = type_dir(root, dataset, kind, str(descriptor.get("type_id", "")))
    return (base / declared) if not Path(declared).is_absolute() else Path(declared)


def schema_file(root: Path, dataset: dict[str, Any], kind: str, descriptor: dict[str, Any]) -> Path | None:
    """The JSON Schema of an entity type, kept in the type's own folder.

    ``schema.json`` beside ``type.json`` is the single location; a type may point
    elsewhere inside DATA_ROOT with an explicit ``schema`` field. There is no
    top-level schema catalog and no fallback: one type — one folder — one schema.
    """
    if kind not in ("entity_type", "doc_type"):
        # `schema` объявлен для записей и документов; у dir_type и relation_type
        # проверяемого тела нет, поэтому путь к схеме для них не разрешается.
        return None
    base = type_dir(root, dataset, kind, str(descriptor.get("type_id", "")))
    declared = descriptor.get("schema")
    if isinstance(declared, str) and declared:
        return Path(declared) if Path(declared).is_absolute() else base / declared
    own = base / "schema.json"
    return own if own.is_file() else None


def prompt_files(root: Path, dataset: dict[str, Any], kind: str, descriptor: dict[str, Any]) -> dict[str, Path]:
    """Resolve declared CRUD prompts; undeclared operations default to prompts/<op>.md."""
    base = type_dir(root, dataset, kind, str(descriptor.get("type_id", "")))
    declared = descriptor.get("prompts")
    declared = declared if isinstance(declared, dict) else {}
    out: dict[str, Path] = {}
    for operation in PROMPT_OPERATIONS:
        value = declared.get(operation)
        if isinstance(value, str) and value:
            out[operation] = (base / value) if not Path(value).is_absolute() else Path(value)
        else:
            # Undeclared or malformed: fall back to the conventional path rather
            # than dropping the operation from the result.
            out[operation] = base / PROMPTS_DIRNAME / f"{operation}.md"
    return out


def descriptor_diagnostics(root: Path, dataset: dict[str, Any], kind: str,
                           descriptor: dict[str, Any], rel_config: str) -> list[dict[str, Any]]:
    """Structural diagnostics for one descriptor (unknown keys, shapes, missing files)."""
    out: list[dict[str, Any]] = []
    allowed = KIND_FIELDS.get(kind, set())
    for key in sorted(set(descriptor) - allowed):
        out.append({"code": "config.unknown_field", "path": rel_config,
                    "message": f"Unknown field {key!r} for {kind} (allowed: {', '.join(sorted(allowed))})."})
    template = descriptor.get("template")
    if template is not None and (not isinstance(template, str) or not template):
        out.append({"code": "config.invalid_schema", "path": rel_config,
                    "message": "template must be a non-empty relative file name."})
    prompts = descriptor.get("prompts")
    if prompts is not None:
        if not isinstance(prompts, dict):
            out.append({"code": "config.invalid_schema", "path": rel_config,
                        "message": "prompts must be an object of operation -> relative file name."})
        else:
            for operation in sorted(set(prompts) - set(PROMPT_OPERATIONS)):
                out.append({"code": "config.unknown_field", "path": rel_config,
                            "message": f"Unknown prompt operation {operation!r} "
                                       f"(allowed: {', '.join(PROMPT_OPERATIONS)})."})
            for operation, value in sorted(prompts.items()):
                if operation in PROMPT_OPERATIONS and (not isinstance(value, str) or not value):
                    out.append({"code": "config.invalid_schema", "path": rel_config,
                                "message": f"prompts.{operation} must be a non-empty relative file name."})
    allowed_statuses = descriptor.get("allowed_statuses")
    if allowed_statuses is not None:
        if (not isinstance(allowed_statuses, list) or not allowed_statuses
                or not all(isinstance(s, str) and s.strip() for s in allowed_statuses)):
            out.append({"code": "config.invalid_schema", "path": rel_config,
                        "message": "allowed_statuses must be a non-empty list of non-empty strings."})
    metric_fields = descriptor.get("metric_fields")
    if metric_fields is not None:
        if not isinstance(metric_fields, dict):
            out.append({"code": "config.invalid_schema", "path": rel_config,
                        "message": "metric_fields must be an object of field -> {unit, prompt}."})
        else:
            for field_name, spec in sorted(metric_fields.items()):
                if not isinstance(spec, dict):
                    out.append({"code": "config.invalid_schema", "path": rel_config,
                                "message": f"metric_fields.{field_name} must be an object "
                                           f"of {', '.join(sorted(METRIC_FIELD_KEYS))}."})
                    continue
                for key in sorted(set(spec) - METRIC_FIELD_KEYS):
                    out.append({"code": "config.unknown_field", "path": rel_config,
                                "message": f"metric_fields.{field_name}: unknown field {key!r} "
                                           f"(allowed: {', '.join(sorted(METRIC_FIELD_KEYS))})."})
                for key in ("unit", "prompt"):
                    if key in spec and (not isinstance(spec[key], str) or not spec[key].strip()):
                        out.append({"code": "config.invalid_schema", "path": rel_config,
                                    "message": f"metric_fields.{field_name}.{key} must be a "
                                               f"non-empty string."})
    if "generated" in descriptor and not isinstance(descriptor["generated"], bool):
        out.append({"code": "config.invalid_schema", "path": rel_config,
                    "message": "generated must be a boolean."})
    required = descriptor.get("required_sections")
    if required is not None:
        if not isinstance(required, list) or not all(isinstance(item, str) and item.strip() for item in required):
            out.append({"code": "config.invalid_schema", "path": rel_config,
                        "message": "required_sections must be a list of non-empty heading titles."})
    section_rules = descriptor.get("section_rules")
    if section_rules is not None:
        if not isinstance(section_rules, list):
            out.append({"code": "config.invalid_schema", "path": rel_config,
                        "message": "section_rules must be a list of objects."})
        else:
            for index, rule in enumerate(section_rules):
                if not isinstance(rule, dict) or not isinstance(rule.get("heading"), str) or not rule["heading"].strip():
                    out.append({"code": "config.invalid_schema", "path": rel_config,
                                "message": f"section_rules[{index}] needs a non-empty 'heading'."})
                    continue
                for key in sorted(set(rule) - {"heading", "min_children", "child_level", "severity"}):
                    out.append({"code": "config.unknown_field", "path": rel_config,
                                "message": f"section_rules[{index}]: unknown field {key!r}."})
                for key in ("min_children", "child_level"):
                    if key in rule and not isinstance(rule[key], int):
                        out.append({"code": "config.invalid_schema", "path": rel_config,
                                    "message": f"section_rules[{index}].{key} must be an integer."})
                if rule.get("severity") not in (None, "error", "warning"):
                    out.append({"code": "config.invalid_schema", "path": rel_config,
                                "message": f"section_rules[{index}].severity must be 'error' or 'warning'."})
    # Declared files must exist: a type that points at a missing template cannot
    # generate documents, and a prompt the agent cannot read is dead config.
    tpl = template_file(root, dataset, kind, descriptor)
    if tpl is not None and not tpl.is_file():
        out.append({"code": "config.template_missing", "path": rel_config,
                    "message": f"Declared template not found: {tpl.name}."})
    declared_schema = descriptor.get("schema")
    if declared_schema is not None and (not isinstance(declared_schema, str) or not declared_schema):
        out.append({"code": "config.invalid_schema", "path": rel_config,
                    "message": "schema must be a non-empty relative file name."})
    schema = schema_file(root, dataset, kind, descriptor)
    if schema is not None and not schema.is_file():
        out.append({"code": "config.schema_missing", "path": rel_config,
                    "message": f"Declared schema not found: {schema.name}."})
    if kind == "entity_type" and isinstance(declared_schema, str) and declared_schema:
        # An explicit `schema` that is not `schema.json` while `schema.json` also
        # exists is ambiguous: two files claim to be the schema of one type.
        base = type_dir(root, dataset, kind, str(descriptor.get("type_id", "")))
        own = base / "schema.json"
        if declared_schema != "schema.json" and own.is_file():
            out.append({"code": "config.duplicate_asset", "path": rel_config,
                        "message": f"Both {declared_schema} (declared) and schema.json exist; keep one."})
    for operation, path in prompt_files(root, dataset, kind, descriptor).items():
        if operation in (prompts if isinstance(prompts, dict) else {}) and not path.is_file():
            out.append({"code": "config.prompt_missing", "path": rel_config,
                        "message": f"Declared prompt for {operation!r} not found: {path.name}."})
    return out


def render_template(text: str, values: dict[str, str]) -> str:
    """Substitute ``{name}`` placeholders. Unknown placeholders are left verbatim.

    Values are inserted as plain text; nothing is evaluated, so a template can
    never execute or interpolate anything the caller did not provide.
    """
    out = text
    for name in TEMPLATE_PLACEHOLDERS:
        if name in values:
            out = out.replace("{" + name + "}", values[name])
    return out


def parse_heading_selector(selector: str) -> tuple[int | None, str]:
    """Split a section selector into (level, title).

    ``"## Purpose"`` -> ``(2, "Purpose")``; ``"Purpose"`` -> ``(None, "Purpose")``.
    A trailing ``:`` marks a prefix match, so ``"### Requirement:"`` selects every
    ``### Requirement: <name>`` heading.
    """
    match = re.match(r"^(#{1,6})\s+(.*)$", selector)
    if match:
        return len(match.group(1)), match.group(2).strip()
    return None, selector.strip()
