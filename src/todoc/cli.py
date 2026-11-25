"""Click CLI: thin input layer over application services (constitution §8)."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import click

from todoc import __version__
from todoc.adapters.filesystem.scanner import atomic_write, file_hash
from todoc.adapters.formats.csvfmt import parse_csv
from todoc.adapters.formats.jsonfmt import parse_json, resolve_pointer
from todoc.adapters.formats.markdown import heading_path_for, parse_markdown
from todoc.application.query import aggregate_records, graph_neighbors, query_records
from todoc.application.search import search_documents
from todoc.application.validator import _load_record_schemas, stable_id
from todoc.application.write import (apply_edit_ops, apply_fix, apply_write_plan, create_document_plan,
                                   create_record_plan, load_input_record)
from todoc.config import init_dataset
from todoc.errors import EXIT_USAGE, AccessError, ConflictError, TodocError, ValidationError
from todoc.output.envelope import emit, make_envelope
from todoc.service import DatasetContext, resolve_roots
from todoc.typing_system.descriptors import (PROMPT_OPERATIONS, descriptor_diagnostics, prompt_files,
                                             schema_file, template_file, type_kind_dir)


def _emit_ok(data: dict[str, Any], output: str, out: str | None, diagnostics: list[dict[str, Any]] | None = None,
             next_actions: list[dict[str, Any]] | None = None) -> None:
    emit(make_envelope(True, data, diagnostics, next_actions), output, out)


def _emit_result(data: dict[str, Any], output: str, diagnostics: list[dict[str, Any]], failed: bool) -> None:
    """Emit a validation result whose envelope agrees with the exit code.

    Findings live in the envelope's ``diagnostics`` (not only inside ``data``),
    and ``ok`` is ``false`` whenever the call exits non-zero — a caller must not
    have to reconcile ``ok: true`` with exit code 3.
    """
    actions = [{"argv": ["todoc", "fix", "--diagnostic", str(diagnostics[0].get("id", "")), "--preview"],
                "purpose": "Показать план исправления первой диагностики"}] if diagnostics else []
    emit(make_envelope(not failed, data, diagnostics, actions), output, None)
    if failed:
        sys.exit(3)


SECTION_MAX_LINES = 40

_group_roots: tuple[str, ...] = ()
_group_output: str = "json"


def _effective_roots(roots: tuple[str, ...]) -> tuple[str, ...]:
    """Subcommand --root wins; otherwise fall back to group-level --root."""
    return roots or _group_roots


def _contexts(roots: tuple[str, ...]) -> list[DatasetContext]:
    return [DatasetContext(r) for r in resolve_roots(_effective_roots(roots))]


def _root_argv(roots: tuple[str, ...]) -> list[str]:
    argv: list[str] = ["todoc"]
    for r in _effective_roots(roots):
        argv += ["--root", r]
    return argv


def _record_schema(ctx: "DatasetContext", entity_type: str) -> dict[str, Any] | None:
    """The entity type's JSON Schema, when it has one, from that type's own folder."""
    loaded = _load_record_schemas(ctx.root, ctx.registry_types, ctx.dataset).get(entity_type)
    return loaded[0] if loaded else None


def _contained_out(root: Path, out: str) -> Path:
    """Resolve ``--out`` and refuse targets outside DATA_ROOT.

    Containment is checked on the resolved path, so symlinks and ``..`` cannot
    be used to write into the operator's home directory or the repository root.
    """
    candidate = Path(out)
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = candidate.resolve()
    base = Path(root).resolve()
    if base not in resolved.parents:
        raise AccessError(f"--out must stay inside DATA_ROOT ({base}): {resolved}", "access.outside_data_root")
    return resolved


def _parse_offset(cursor: str | None) -> int:
    """Opaque-but-validated cursor: an integer offset, never a Python traceback."""
    if cursor is None or cursor == "":
        return 0
    try:
        offset = int(cursor)
    except ValueError as exc:
        raise ValidationError(f"Invalid --cursor: {cursor!r} (expected a non-negative integer)",
                              "usage.invalid_cursor") from exc
    if offset < 0:
        raise ValidationError(f"Invalid --cursor: {cursor!r} (expected a non-negative integer)",
                              "usage.invalid_cursor")
    return offset


def _parse_line_range(line_range: str) -> tuple[int, int]:
    """Parse ``N`` or ``N-M`` into a 1-based inclusive range."""
    start_s, sep, end_s = line_range.partition("-")
    try:
        start = int(start_s)
        end = int(end_s) if sep and end_s else start
    except ValueError as exc:
        raise ValidationError(f"Invalid --line-range: {line_range!r} (expected N or N-M)",
                              "usage.invalid_line_range") from exc
    if start < 1 or end < start:
        raise ValidationError(f"Invalid --line-range: {line_range!r} (expected N or N-M, N >= 1, M >= N)",
                              "usage.invalid_line_range")
    return start, end


@click.group(invoke_without_command=True)
@click.option("--root", "roots", multiple=True, help="DATA_ROOT (repeatable). Or set TODOC_ROOT.")
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True, help="Non-interactive mode (never prompts).")
@click.version_option(__version__, prog_name="todoc")
@click.pass_context
def cli(ctx: click.Context, roots: tuple[str, ...], output: str, no_input: bool) -> None:
    """todoc — portable typed knowledge substrate (validator + bounded search/read)."""
    ctx.ensure_object(dict)
    global _group_roots, _group_output
    _group_roots = roots
    _group_output = output
    ctx.obj["roots"] = roots
    ctx.obj["output"] = output
    ctx.obj["no_input"] = no_input
    if ctx.invoked_subcommand is None:
        click.echo("todoc — portable typed knowledge substrate")
        click.echo("Commands: init, check, scan, check-config, validate, index, explain-path,")
        click.echo("  docs, records, relations, types, fix, doctor, status")
        click.echo("Use `todoc --help` for details. Pass --root <DATA_ROOT> (repeatable) or set TODOC_ROOT.")


@cli.command()
@click.option("--root", "root", required=True, help="DATA_ROOT to initialize.")
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
def init(root: str, output: str, no_input: bool) -> None:
    """Create portable .todoc/ control files (never scans/moves user data)."""
    dataset = init_dataset(Path(root))
    _emit_ok({"dataset_id": dataset["dataset_id"], "root": str(Path(root).resolve()), "created": ".todoc/"}, output, None)


@cli.command("check-config")
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
def check_config(roots: tuple[str, ...], output: str, no_input: bool) -> None:
    """Validate dataset configs before use.

    Reports unknown descriptor fields, malformed structure rules and declared
    template/prompt files that are missing on disk — a config that silently accepts
    a rule it never enforces is worse than one that refuses it.
    """
    results = []
    collected: list[dict[str, Any]] = []
    failed = False
    for ctx in _contexts(roots):
        findings: list[dict[str, Any]] = []
        for kind, store in (("dir_type", ctx.registry_types.dir_types), ("doc_type", ctx.registry_types.doc_types),
                            ("entity_type", ctx.registry_types.entity_types),
                            ("relation_type", ctx.registry_types.relation_types)):
            for type_id in sorted(store):
                rel = f".todoc/{type_kind_dir(ctx.dataset, kind)}/{type_id}/type.json"
                for item in descriptor_diagnostics(ctx.root, ctx.dataset, kind, store[type_id], rel):
                    findings.append({
                        "dataset_id": ctx.dataset_id, "id": stable_id(rel, item["code"], item["message"]),
                        "code": item["code"], "severity": item.get("severity", "error"),
                        "path": item["path"], "location": {},
                        "evidence": f"type_id: {type_id}", "message": item["message"], "suggested_fixes": [],
                    })
        collected.extend(findings)
        errors = [item for item in findings if item["severity"] == "error"]
        if errors:
            failed = True
        results.append({"dataset_id": ctx.dataset_id, "ok": not errors,
                        "warnings": len(findings) - len(errors),
                        "dir_types": len(ctx.registry_types.dir_types),
                        "doc_types": len(ctx.registry_types.doc_types),
                        "entity_types": len(ctx.registry_types.entity_types),
                        "relation_types": len(ctx.registry_types.relation_types),
                        "issues": len(findings)})
    _emit_result({"datasets": results}, output, collected, failed)


@cli.command()
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
@click.option("--strict", is_flag=True, help="Warnings become failures.")
def check(roots: tuple[str, ...], output: str, no_input: bool, strict: bool) -> None:
    """Short health summary + general diagnostics (multi-root isolated)."""
    reports = []
    collected: list[dict[str, Any]] = []
    has_error = False
    for ctx in _contexts(roots):
        _folders, documents, _records, _relations, diagnostics = ctx.scan_and_validate()
        errors = sum(1 for d in diagnostics if d.get("severity") == "error")
        warnings = sum(1 for d in diagnostics if d.get("severity") == "warning")
        if errors or (strict and warnings):
            has_error = True
        reports.append({"dataset_id": ctx.dataset_id, "documents": len(documents), "errors": errors,
                        "warnings": warnings, "status": "issues_found" if errors else "ok"})
        collected.extend(diagnostics)
    _emit_result({"datasets": reports}, output, collected, has_error)


@cli.command()
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
def scan(roots: tuple[str, ...], output: str, no_input: bool) -> None:
    """Deterministic traversal without writing indexes."""
    results = []
    for ctx in _contexts(roots):
        folders, documents, _r, _rel, diagnostics = ctx.scan_and_validate()
        results.append({"dataset_id": ctx.dataset_id, "folders": len(folders), "documents": len(documents),
                        "diagnostics": len(diagnostics)})
    _emit_ok({"datasets": results}, output, None)


@cli.command()
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
@click.option("--all", "all_", is_flag=True)
def validate(roots: tuple[str, ...], output: str, no_input: bool, all_: bool) -> None:
    """Detailed file/rule/location report."""
    reports = []
    collected: list[dict[str, Any]] = []
    has_error = False
    for ctx in _contexts(roots):
        _f, documents, _r, _rel, diagnostics = ctx.scan_and_validate()
        errors = [d for d in diagnostics if d.get("severity") == "error"]
        if errors:
            has_error = True
        reports.append({"dataset_id": ctx.dataset_id, "documents": len(documents), "diagnostics": diagnostics})
        collected.extend(diagnostics)
    _emit_result({"datasets": reports}, output, collected, has_error)


@cli.group()
@click.pass_context
def index(ctx: click.Context) -> None:
    """Index status/rebuild (derived, rebuildable)."""


@index.command("status")
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
def index_status(roots: tuple[str, ...], output: str, no_input: bool) -> None:
    results = []
    for ctx in _contexts(roots):
        gen = ctx.store.current_generation_id()
        results.append({"dataset_id": ctx.dataset_id, "generation_id": gen, "current": gen is not None})
    _emit_ok({"datasets": results}, output, None)


@index.command("rebuild")
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
def index_rebuild(roots: tuple[str, ...], output: str, no_input: bool) -> None:
    results = [ctx.rebuild_index() for ctx in _contexts(roots)]
    _emit_ok({"datasets": results}, output, None)


@cli.command("explain-path")
@click.argument("path")
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
def explain_path(path: str, roots: tuple[str, ...], output: str, no_input: bool) -> None:
    """Show resolved type/rule for a path."""
    for ctx in _contexts(roots):
        _f, documents, _r, _rel, _d = ctx.scan_and_validate()
        for doc in documents:
            if doc["path"] == path:
                _emit_ok({"dataset_id": ctx.dataset_id, "path": path, "doc_type": doc["doc_type"],
                          "format": doc["format"], "rule_source": doc["rule_source"], "document_id": doc["document_id"]},
                         output, None)
                return
    raise ValidationError(f"Path not found in dataset: {path}", "explain.path_not_found")


@cli.group()
@click.pass_context
def docs(ctx: click.Context) -> None:
    """Document operations."""


def _slugify(title: str) -> str:
    """Filesystem-safe slug from a title (letters, digits, dash, underscore)."""
    return "".join(c if c.isalnum() or c in "-_" else "-" for c in title.lower()).strip("-") or "untitled"


def _utc_date() -> str:
    """UTC calendar date for the ``{date}`` template placeholder (deterministic per day)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _resolve_document_template(ctx: DatasetContext, doc_type: str | None,
                               template: str | None) -> tuple[str | None, str | None, str]:
    """Resolve (doc_type_id, template_text, source) for `docs new`.

    ``--template`` accepts either a doc_type id (uses that type's ``template.<ext>``)
    or a path inside DATA_ROOT. A type that declares no template yields no text: the
    document starts as a bare title heading. A type that declares a template which is
    missing on disk is refused rather than silently degraded.
    """
    type_id = doc_type
    if template:
        if template in ctx.registry_types.doc_types:
            type_id = template
        else:
            path = _contained_out(ctx.root, template)
            if not path.is_file():
                raise ValidationError(f"Template not found: {template}", "types.template_missing")
            return type_id, path.read_text(encoding="utf-8"), template
    if type_id is not None and type_id not in ctx.registry_types.doc_types:
        raise ValidationError(f"Unknown doc_type: {type_id!r}", "types.unknown")
    if type_id is None:
        return None, None, "none"
    descriptor = ctx.registry_types.doc_types[type_id]
    declared = template_file(ctx.root, ctx.dataset, "doc_type", descriptor)
    if declared is None:
        return type_id, None, "type-without-template"
    if not declared.is_file():
        raise ValidationError(
            f"doc_type {type_id!r} declares template {declared.name}, which is missing",
            "types.template_missing")
    return type_id, declared.read_text(encoding="utf-8"), _rel_todoc(ctx.root, declared)


@docs.command("new")
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
@click.option("--title", required=True)
@click.option("--dir", "dir_", default="inbox")
@click.option("--path", "path_", default=None, help="Явный относительный путь вместо --dir + slug.")
@click.option("--type", "doc_type", default=None, help="Тип документа: шаблон и структура из папки типа.")
@click.option("--template", default=None, help="Тип документа или путь к файлу шаблона.")
def docs_new(roots: tuple[str, ...], output: str, no_input: bool, title: str, dir_: str, path_: str | None,
             doc_type: str | None, template: str | None) -> None:
    """Create a document from its type's starter template (create-only, no-overwrite)."""
    ctx = _contexts(roots)[0]
    slug = _slugify(title)
    rel = path_ or f"{dir_.strip('/')}/{slug}.md"
    target = _contained_out(ctx.root, rel)  # neither --dir nor --path may escape DATA_ROOT
    if target.exists():
        raise ConflictError(f"Target already exists: {rel}", "docs.target_exists")
    type_id, template_text, source = _resolve_document_template(ctx, doc_type, template)
    values = {"title": title, "slug": slug, "date": _utc_date(), "type_id": type_id or "",
              "id": f"doc:{rel}", "format": "markdown"}
    plan = create_document_plan(ctx.dataset, ctx.registry_types.doc_types, type_id, title, rel,
                                template_text, values)
    apply_write_plan(ctx.root, plan)
    ctx.rebuild_index()
    _emit_ok({"dataset_id": ctx.dataset_id, "path": rel, "title": title, "doc_type": type_id,
              "template": source, "hash": plan.new_hash}, output, None,
             next_actions=[{"argv": _root_argv(roots) + ["docs", "read", "--id", f"doc:{rel}"],
                            "purpose": "Прочитать созданный документ"},
                           {"argv": _root_argv(roots) + ["types", "prompt", type_id or "note", "--op", "edit"],
                            "purpose": "Взять стартовый промпт правки для этого типа"}])


@docs.command("search")
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
@click.option("--type", "doc_type", default=None)
@click.option("--query", required=True)
@click.option("--budget", type=int, default=None)
@click.option("--limit", type=int, default=10)
@click.option("--within", default=None)
@click.option("--cursor", default=None)
def docs_search(roots: tuple[str, ...], output: str, no_input: bool, doc_type: str | None, query: str,
                budget: int | None, limit: int, within: str | None, cursor: str | None) -> None:
    """Bounded lexical search with provenance."""
    ctx = _contexts(roots)[0]
    ctx.rebuild_index()
    payload = ctx.load_index()
    offset = _parse_offset(cursor)
    hits, total, truncated = search_documents(ctx.root, payload["documents"], query, doc_type, within, limit,
                                             budget, offset)
    next_cursor = str(offset + len(hits)) if truncated else None
    _emit_ok({"dataset_id": ctx.dataset_id, "total": total, "returned": len(hits), "truncated": truncated,
              "cursor": next_cursor, "items": [h.to_dict() for h in hits]}, output, None,
             next_actions=[{"argv": _root_argv(roots) + ["docs", "read", "--id", hits[0].id, "--output", "json"],
                            "purpose": "Прочитать выбранный документ"}] if hits else [])


@docs.command("read")
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
@click.option("--id", "doc_id", required=True)
@click.option("--section", default=None)
@click.option("--anchor", default=None)
@click.option("--line-range", default=None)
@click.option("--pointer", default=None)
@click.option("--columns", default=None)
@click.option("--rows", type=int, default=None)
@click.option("--where", default=None)
@click.option("--budget", type=int, default=None)
def docs_read(roots: tuple[str, ...], output: str, no_input: bool, doc_id: str, section: str | None,
              anchor: str | None, line_range: str | None, pointer: str | None, columns: str | None,
              rows: int | None, where: str | None, budget: int | None) -> None:
    """Bounded projection read (section/pointer/columns)."""
    ctx = _contexts(roots)[0]
    ctx.rebuild_index()
    payload = ctx.load_index()
    doc = next((d for d in payload["documents"] if d["document_id"] == doc_id), None)
    if doc is None:
        raise ValidationError(f"Document not found: {doc_id}", "docs.not_found")
    text = (ctx.root / doc["path"]).read_text(encoding="utf-8")
    data: dict[str, Any] = {"dataset_id": ctx.dataset_id, "id": doc_id, "path": doc["path"],
                            "format": doc["format"], "doc_type": doc["doc_type"], "hash": doc["hash"]}
    if doc["format"] == "markdown":
        md = parse_markdown(text)
        if section or anchor:
            wanted = section or anchor or ""
            selected = None
            selected_index = -1
            for i, h in enumerate(md.headings):
                if h.title == wanted or h.anchor == wanted:
                    selected = h
                    selected_index = i
                    break
            if selected is None:
                raise ValidationError(f"Section not found: {wanted}", "docs.section_not_found")
            lines = text.splitlines()
            end_line = len(lines)
            for h in md.headings[selected_index + 1:]:
                if h.level <= selected.level:
                    end_line = h.line - 1
                    break
            section_lines = lines[selected.line - 1:end_line]
            window = section_lines[:SECTION_MAX_LINES]
            data["section"] = selected.title
            data["heading_path"] = heading_path_for(md.headings, selected_index)
            data["line_start"] = selected.line
            data["line_end"] = selected.line + len(window) - 1
            data["lines"] = window
            data["truncated"] = len(section_lines) > len(window)
            data["text"] = "\n".join(window)
        elif line_range:
            start, end = _parse_line_range(line_range)
            lines = text.splitlines()
            data["lines"] = lines[start - 1:end]
            data["text"] = "\n".join(data["lines"])
        else:
            data["title"] = md.title
            data["headings"] = [{"title": h.title, "level": h.level, "line": h.line, "anchor": h.anchor} for h in md.headings]
            data["text"] = text[: budget or 4000]
    elif doc["format"] == "json":
        value, _errors = parse_json(text)
        if pointer:
            try:
                data["value"] = resolve_pointer(value, pointer)
            except (KeyError, IndexError, ValueError) as exc:
                raise ValidationError(f"Pointer not found: {pointer}: {exc}", "docs.pointer_not_found") from exc
        else:
            data["value"] = value
    elif doc["format"] == "csv":
        csv_doc = parse_csv(text)
        cols = [c.strip() for c in columns.split(",")] if columns else csv_doc.headers
        selected_rows = csv_doc.rows[: rows or len(csv_doc.rows)]
        if where:
            key, _, val = where.partition("=")
            selected_rows = [r for r in selected_rows if str(r.get(key.strip(), "")) == val.strip()]
        data["columns"] = cols
        data["rows"] = [{c: r.get(c, "") for c in cols} for r in selected_rows]
        data["total"] = len(csv_doc.rows)
    else:
        data["text"] = text[: budget or 4000]
    _emit_ok(data, output, None)


@docs.command("tree")
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
@click.option("--within", default=None)
@click.option("--max-depth", type=int, default=3)
def docs_tree(roots: tuple[str, ...], output: str, no_input: bool, within: str | None, max_depth: int) -> None:
    """Compact derived outline (folders + documents)."""
    ctx = _contexts(roots)[0]
    ctx.rebuild_index()
    payload = ctx.load_index()
    folders = payload["folders"]
    documents = payload["documents"]
    if within:
        folders = [f for f in folders if f["path"] == within or f["path"].startswith(within.rstrip("/") + "/")]
        documents = [d for d in documents if d["path"] == within or d["path"].startswith(within.rstrip("/") + "/")]
    _emit_ok({"dataset_id": ctx.dataset_id, "folders": folders[:50], "documents": documents[:50],
              "total_folders": len(folders), "total_documents": len(documents), "max_depth": max_depth}, output, None)


@docs.command("edit")
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
@click.option("--id", "doc_id", required=True)
@click.option("--patch-file", required=True)
@click.option("--if-hash", default=None)
@click.option("--preview", is_flag=True)
@click.option("--apply", "apply_", is_flag=True)
def docs_edit(roots: tuple[str, ...], output: str, no_input: bool, doc_id: str, patch_file: str,
              if_hash: str | None, preview: bool, apply_: bool) -> None:
    """Review-first patch edit (preview default, --apply to write)."""
    ctx = _contexts(roots)[0]
    ctx.rebuild_index()
    payload = ctx.load_index()
    doc = next((d for d in payload["documents"] if d["document_id"] == doc_id), None)
    if doc is None:
        raise ValidationError(f"Document not found: {doc_id}", "docs.not_found")
    patch_text = Path(patch_file).read_text(encoding="utf-8")
    try:
        patch = json.loads(patch_text)
    except json.JSONDecodeError as exc:
        raise ValidationError(f"Invalid patch file: {exc}", "edit.invalid_patch") from exc
    if not isinstance(patch, dict):
        raise ValidationError('Patch file must be a JSON object: {"ops": [{"line": N, "text": "..."}]}',
                              "edit.invalid_patch")
    ops = patch.get("ops") or []
    if not isinstance(ops, list) or any(not isinstance(op, dict) for op in ops):
        raise ValidationError('Patch "ops" must be a list of {"line": N, "text": "..."} objects',
                              "edit.invalid_patch")
    if not apply_:
        _emit_ok({"dataset_id": ctx.dataset_id, "id": doc_id, "path": doc["path"], "preview": True, "ops": ops}, output, None)
        return
    new_hash = apply_edit_ops(ctx.root, doc["path"], ops, expected_hash=if_hash)
    ctx.rebuild_index()
    _emit_ok({"dataset_id": ctx.dataset_id, "id": doc_id, "path": doc["path"], "applied": True, "new_hash": new_hash}, output, None)


@cli.group()
@click.pass_context
def records(ctx: click.Context) -> None:
    """Typed records operations."""


@records.command("create")
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
@click.option("--type", "entity_type", required=True)
@click.option("--input-file", required=True)
@click.option("--preview", is_flag=True)
@click.option("--apply", "apply_", is_flag=True)
@click.option("--if-hash-new", is_flag=True)
def records_create(roots: tuple[str, ...], output: str, no_input: bool, entity_type: str, input_file: str,
                   preview: bool, apply_: bool, if_hash_new: bool) -> None:
    """Create-only new JSON record (preview default)."""
    ctx = _contexts(roots)[0]
    ctx.rebuild_index()
    payload = ctx.load_index()
    record = load_input_record(Path(input_file))
    if record.get("entity_type") != entity_type:
        record["entity_type"] = entity_type
    existing_ids = {r["record_id"] for r in payload["records"]}
    existing_paths = {d["path"] for d in payload["documents"]}
    schema = _record_schema(ctx, entity_type)
    plan = create_record_plan(ctx.dataset, ctx.registry_types.entity_types, record, existing_ids, existing_paths,
                              schema)
    if not apply_:
        _emit_ok({"dataset_id": ctx.dataset_id, "preview": True, "plan": plan.to_dict()}, output, None)
        return
    new_hash = apply_write_plan(ctx.root, plan)
    ctx.rebuild_index()
    _emit_ok({"dataset_id": ctx.dataset_id, "created": plan.target_path, "new_hash": new_hash}, output, None)


@records.command("list")
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
@click.option("--type", "entity_type", default=None)
@click.option("--since", default=None)
@click.option("--until", default=None)
@click.option("--relation", default=None)
@click.option("--limit", type=int, default=200)
def records_list(roots: tuple[str, ...], output: str, no_input: bool, entity_type: str | None, since: str | None,
                 until: str | None, relation: str | None, limit: int) -> None:
    """List records with optional filters."""
    ctx = _contexts(roots)[0]
    ctx.rebuild_index()
    payload = ctx.load_index()
    filters: dict[str, Any] = {}
    if since:
        filters["date"] = {"$gte": since}
    items, total, truncated = query_records(payload["records"], entity_type, filters, limit)
    if until:
        items = [r for r in items if str((r.get("data") or {}).get("date", "")) <= until]
    if relation:
        rel_type, _, target = relation.partition("=")
        items = [r for r in items if any(rel.get("type_id") == rel_type and (rel.get("target") or {}).get("id") == target
                                         for rel in ((r.get("data") or {}).get("relations") or []))]
    if until or relation:
        total = len(items)
        truncated = False
    _emit_ok({"dataset_id": ctx.dataset_id, "total": total, "returned": len(items), "truncated": truncated,
              "items": items}, output, None)


@records.command("query")
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
@click.option("--query-file", required=True)
def records_query(roots: tuple[str, ...], output: str, no_input: bool, query_file: str) -> None:
    """Run a saved declarative QuerySpec."""
    ctx = _contexts(roots)[0]
    ctx.rebuild_index()
    payload = ctx.load_index()
    try:
        spec = json.loads(Path(query_file).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValidationError(f"Invalid query file: {exc}", "query.invalid_file") from exc
    items, total, truncated = query_records(payload["records"], spec.get("entity_type"),
                                            spec.get("filters"), int(spec.get("limit", 200)))
    _emit_ok({"dataset_id": ctx.dataset_id, "total": total, "truncated": truncated, "items": items}, output, None)


@records.command("aggregate")
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
@click.option("--metric", required=True)
@click.option("--group-by", default=None)
@click.option("--type", "entity_type", default=None)
def records_aggregate(roots: tuple[str, ...], output: str, no_input: bool, metric: str,
                      group_by: str | None, entity_type: str | None) -> None:
    """Aggregate with units/formula/provenance."""
    ctx = _contexts(roots)[0]
    ctx.rebuild_index()
    payload = ctx.load_index()
    result = aggregate_records(payload["records"], entity_type or "workout", metric, group_by)
    result["dataset_id"] = ctx.dataset_id
    _emit_ok(result, output, None)


@records.command("read")
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
@click.option("--id", "record_id", required=True)
@click.option("--view", default=None)
def records_read(roots: tuple[str, ...], output: str, no_input: bool, record_id: str, view: str | None) -> None:
    """Read one record (optional view projection)."""
    ctx = _contexts(roots)[0]
    ctx.rebuild_index()
    payload = ctx.load_index()
    record = next((r for r in payload["records"] if r["record_id"] == record_id), None)
    if record is None:
        raise ValidationError(f"Record not found: {record_id}", "records.not_found")
    data = dict(record["data"])
    if view:
        descriptor = ctx.registry_types.entity_types.get(record["entity_type"], {})
        fields = (descriptor.get("views") or {}).get(view)
        if fields:
            data = {k: data[k] for k in fields if k in data}
    _emit_ok({"dataset_id": ctx.dataset_id, "record_id": record_id, "path": record["path"], "data": data}, output, None)


@cli.group()
@click.pass_context
def relations(ctx: click.Context) -> None:
    """Typed relations."""


@relations.command("graph")
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
@click.option("--from", "from_id", required=True)
@click.option("--type", "type_id", default=None)
@click.option("--depth", type=int, default=1)
@click.option("--limit", type=int, default=100)
def relations_graph(roots: tuple[str, ...], output: str, no_input: bool, from_id: str,
                    type_id: str | None, depth: int, limit: int) -> None:
    """Typed edges + brief neighbours (BFS, bounded)."""
    ctx = _contexts(roots)[0]
    ctx.rebuild_index()
    payload = ctx.load_index()
    edges = graph_neighbors(payload["relations"], from_id, type_id, depth, limit)
    _emit_ok({"dataset_id": ctx.dataset_id, "from": from_id, "edges": edges, "total": len(edges)}, output, None)


@cli.group()
@click.pass_context
def types(ctx: click.Context) -> None:
    """Type catalog."""


@types.command("list")
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
def types_list(roots: tuple[str, ...], output: str, no_input: bool) -> None:
    ctx = _contexts(roots)[0]
    _emit_ok({"dataset_id": ctx.dataset_id,
              "dir_types": sorted(ctx.registry_types.dir_types),
              "doc_types": sorted(ctx.registry_types.doc_types),
              "entity_types": sorted(ctx.registry_types.entity_types),
              "relation_types": sorted(ctx.registry_types.relation_types)}, output, None)


def _type_bundle(ctx: DatasetContext, kind: str, descriptor: dict[str, Any]) -> dict[str, Any]:
    """Template + CRUD prompt locations of a type, with existence flags.

    A path the agent cannot open is reported as ``exists: false`` instead of being
    omitted, so a caller can tell "type has no prompts" from "prompts are missing".
    """
    if kind not in ("doc_type", "entity_type"):
        return {"template": None, "prompts": {}, "schema": None}
    kind_dir = type_kind_dir(ctx.dataset, kind)
    type_id = str(descriptor.get("type_id", ""))
    path = template_file(ctx.root, ctx.dataset, kind, descriptor)
    template = None
    if path is not None:
        template = {"path": _rel_todoc(ctx.root, path), "exists": path.is_file()}
    prompts = {
        operation: {"path": f".todoc/{kind_dir}/{type_id}/{path.relative_to(_type_base(ctx, kind, type_id)).as_posix()}",
                            "exists": path.is_file()}
        for operation, path in prompt_files(ctx.root, ctx.dataset, kind, descriptor).items()
    }
    schema = schema_file(ctx.root, ctx.dataset, kind, descriptor)
    return {"template": template, "prompts": prompts,
            "schema": ({"path": _rel_todoc(ctx.root, schema), "exists": schema.is_file()}
                       if schema is not None else None)}


def _rel_todoc(root: Path, path: Path) -> str:
    """Path as the user sees it: ``.todoc/...`` when inside DATA_ROOT, else absolute."""
    try:
        return f".todoc/{path.relative_to(root / '.todoc').as_posix()}"
    except ValueError:
        return str(path)


def _type_base(ctx: DatasetContext, kind: str, type_id: str) -> Path:
    return ctx.root / ".todoc" / type_kind_dir(ctx.dataset, kind) / type_id


@types.command("show")
@click.argument("type_id")
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
def types_show(type_id: str, roots: tuple[str, ...], output: str, no_input: bool) -> None:
    ctx = _contexts(roots)[0]
    for kind, store in (("dir_type", ctx.registry_types.dir_types), ("doc_type", ctx.registry_types.doc_types),
                        ("entity_type", ctx.registry_types.entity_types),
                        ("relation_type", ctx.registry_types.relation_types)):
        if type_id in store:
            bundle = _type_bundle(ctx, kind, store[type_id])
            _emit_ok({"dataset_id": ctx.dataset_id, "kind": kind, "type": store[type_id],
                      "template": bundle["template"], "prompts": bundle["prompts"],
                      "schema": bundle["schema"]}, output, None,
                     next_actions=[{"argv": _root_argv(roots) + ["types", "prompt", type_id, "--op", "create"],
                                    "purpose": "Взять стартовый промпт создания документа этого типа"}]
                     if bundle["prompts"] else [])
            return
    raise ValidationError(f"Unknown type: {type_id}", "types.unknown")


@types.command("prompt")
@click.argument("type_id")
@click.option("--op", "operation", type=click.Choice(list(PROMPT_OPERATIONS)), default="create", show_default=True)
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
def types_prompt(type_id: str, operation: str, roots: tuple[str, ...], output: str, no_input: bool) -> None:
    """Starter prompt of a type for one CRUD operation (read/create/edit/delete)."""
    ctx = _contexts(roots)[0]
    for kind, store in (("doc_type", ctx.registry_types.doc_types), ("entity_type", ctx.registry_types.entity_types)):
        if type_id in store:
            paths = prompt_files(ctx.root, ctx.dataset, kind, store[type_id])
            path = paths.get(operation)
            if path is None or not path.is_file():
                raise ValidationError(
                    f"No {operation!r} prompt for type {type_id!r} "
                    f"(expected {path.name if path is not None else 'prompts/'}",
                    "types.prompt_missing")
            text = path.read_text(encoding="utf-8")
            _emit_ok({"dataset_id": ctx.dataset_id, "type_id": type_id, "kind": kind, "operation": operation,
                      "path": f".todoc/{type_kind_dir(ctx.dataset, kind)}/{type_id}/prompts/{operation}.md",
                      "prompt": text, "chars": len(text)}, output, None)
            return
    raise ValidationError(f"Unknown type: {type_id}", "types.unknown")


@types.command("guide")
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
@click.option("--format", "fmt", type=click.Choice(["markdown", "json"]), default="markdown")
@click.option("--out", default=None)
def types_guide(roots: tuple[str, ...], output: str, no_input: bool, fmt: str, out: str | None) -> None:
    """Generated type reference (stdout or --out)."""
    ctx = _contexts(roots)[0]
    if fmt == "json":
        text = json.dumps({"dataset_id": ctx.dataset_id,
                           "dir_types": ctx.registry_types.dir_types,
                           "doc_types": ctx.registry_types.doc_types,
                           "entity_types": ctx.registry_types.entity_types,
                           "relation_types": ctx.registry_types.relation_types}, indent=2, ensure_ascii=False)
    else:
        lines = [f"# Type system for {ctx.dataset_id}", ""]
        for kind, store in (("dir_type", ctx.registry_types.dir_types), ("doc_type", ctx.registry_types.doc_types),
                            ("entity_type", ctx.registry_types.entity_types), ("relation_type", ctx.registry_types.relation_types)):
            lines.append(f"## {kind}")
            for type_id in sorted(store):
                lines.append(f"- `{type_id}`: {store[type_id].get('description', '')}")
            lines.append("")
        text = "\n".join(lines)
    if out:
        out_path = _contained_out(ctx.root, out)
        atomic_write(out_path, text + "\n")
        _emit_ok({"dataset_id": ctx.dataset_id, "written": str(out_path)}, output, None)
    elif output == "json" and fmt == "markdown":
        _emit_ok({"dataset_id": ctx.dataset_id, "guide": text}, output, None)
    else:
        sys.stdout.write(text + "\n")


@cli.command("fix")
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
@click.option("--diagnostic", required=True)
@click.option("--preview", is_flag=True)
@click.option("--apply", "apply_", is_flag=True)
@click.option("--if-hash", default=None)
def fix(roots: tuple[str, ...], output: str, no_input: bool, diagnostic: str, preview: bool,
        apply_: bool, if_hash: str | None) -> None:
    """Preview/apply a supported fix (review-first)."""
    ctx = _contexts(roots)[0]
    _f, _d, _r, _rel, diagnostics = ctx.scan_and_validate()
    target = next((d for d in diagnostics if d.get("id") == diagnostic), None)
    if target is None:
        raise ValidationError(f"Diagnostic not found: {diagnostic}", "fix.diagnostic_not_found")
    fixes = target.get("suggested_fixes") or []
    if not fixes:
        raise ValidationError(f"Diagnostic {diagnostic} has no suggested fixes", "fix.no_fixes")
    fix0 = fixes[0]
    if not apply_:
        _emit_ok({"dataset_id": ctx.dataset_id, "diagnostic": diagnostic, "preview": True, "fix": fix0}, output, None)
        return
    rel_path = str(target.get("path", ""))
    evidence = str(target.get("evidence", ""))
    # Evidence is rendered by the validator as either ``[text](target)`` for an
    # inline link or ``[[target]]`` for an Obsidian wikilink; both have to yield
    # the target, otherwise a wikilink fix can never be applied.
    if evidence.startswith("[[") and evidence.endswith("]]"):
        old_target = evidence[2:-2]
    else:
        old_target = evidence.split("](")[-1].rstrip(")") if "](" in evidence else ""
    new_target = str(fix0.get("replacement", ""))
    if not old_target or not new_target:
        raise ValidationError("Cannot derive link targets from diagnostic", "fix.cannot_apply")
    new_hash = apply_fix(ctx.root, rel_path, old_target, new_target, expected_hash=if_hash)
    ctx.rebuild_index()
    _emit_ok({"dataset_id": ctx.dataset_id, "diagnostic": diagnostic, "applied": True, "new_hash": new_hash}, output, None)


@cli.command("doctor")
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
@click.option("--check", default=None, help="Comma-separated check ids.")
@click.option("--scope", default=None)
@click.option("--fix", "fix_", is_flag=True, help="Separate repair mode (dry-run by default).")
def doctor(roots: tuple[str, ...], output: str, no_input: bool, check: str | None, scope: str | None, fix_: bool) -> None:
    """Read-only environment diagnostics (stable IDs, never auto-repairs)."""
    wanted = {c.strip() for c in check.split(",")} if check else None
    reports = []
    for ctx in _contexts(roots):
        checks = [
            ("config", True, "Dataset config loads."),
            ("index", ctx.store.current_generation_id() is not None, "Index generation is current."),
            ("python", True, f"Python {sys.version.split()[0]}."),
        ]
        if wanted:
            checks = [c for c in checks if c[0] in wanted]
        passed = sum(1 for _id, ok, _msg in checks if ok)
        reports.append({"dataset_id": ctx.dataset_id, "checks_total": len(checks), "passed": passed,
                        "checks": [{"id": cid, "status": "pass" if ok else "fail", "message": msg} for cid, ok, msg in checks],
                        "fix_mode": bool(fix_)})
    _emit_ok({"datasets": reports}, output, None)


@cli.command("status")
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
def status(roots: tuple[str, ...], output: str, no_input: bool) -> None:
    """Quick state snapshot (distinct from doctor)."""
    reports = []
    for ctx in _contexts(roots):
        payload = ctx.store.load_current()
        reports.append({"dataset_id": ctx.dataset_id,
                        "generation_id": payload.get("generation_id") if payload else None,
                        "documents": len(payload["documents"]) if payload else 0,
                        "records": len(payload["records"]) if payload else 0})
    _emit_ok({"datasets": reports}, output, None)


def _emit_error(code: str, message: str, exit_code: int) -> None:
    """Failures are envelopes too: one valid JSON per invocation, plus a human line.

    Callers (agents, scripts, MCP) parse stdout; a bare text line on stderr is
    not a machine-readable result, so the same fact is also emitted as
    ``ok: false`` with a diagnostic carrying the stable ``code``.
    """
    diagnostic = {"dataset_id": "", "id": stable_id(code, message), "code": code, "severity": "error",
                  "path": "", "location": {}, "evidence": "", "message": message, "suggested_fixes": []}
    emit(make_envelope(False, {}, [diagnostic],
                       [{"argv": ["todoc", "--help"], "purpose": "Показать список команд и опций"}]),
         _group_output, None)
    sys.stderr.write(f"Error [{code}]: {message}\n")
    sys.exit(exit_code)


def main() -> None:
    try:
        cli(standalone_mode=False)
    except TodocError as exc:
        _emit_error(exc.code, exc.message, exc.exit_code)
    except click.ClickException as exc:
        _emit_error("usage.error", exc.format_message(), EXIT_USAGE)


if __name__ == "__main__":
    main()
