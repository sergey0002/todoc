"""Click CLI: thin input layer over application services (constitution §8)."""

from __future__ import annotations

import difflib
import json
import hashlib
import re
import shutil
import sys
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

import click

from todoc import __version__
from todoc.adapters.filesystem.scanner import atomic_write, file_hash, is_within_root, read_verified_text
from todoc.adapters.formats.csvfmt import parse_csv
from todoc.adapters.formats.jsonfmt import parse_json, resolve_pointer
from todoc.adapters.formats.markdown import (heading_path_for, parse_markdown,
                                           resolve_link_target)
from todoc.application.history import (add_tag, blame as history_blame, content_at, diff_texts,
                                       gc as history_gc_run,
                                       adopt as history_adopt_run,
                                       log as history_log, resolve_rev,
                                       revert_plan, show as history_show)
from todoc.application.changes import (TRANSLIT, apply_change, archive_change, change_id_for,
                                       collect_deltas, list_change_entries, load_change,
                                       open_change, record_path, revert_change,
                                       validate_change, verify_change)
from todoc.application.flow_view import build_flow_view
from todoc.application.interop import (anchor_for, build_export_doc, flow_to_asl,
                                       related_flow_id, rule_to_dmn, terms_to_rasa)
from todoc.application.context import build_context
from todoc.application.documents import (FIELDS as DOCUMENT_LIST_FIELDS, folder_tree, list_documents,
                                         matching_documents, normalize_scope, select_document_attributes, within_depth)
from todoc.application.metadata_patch import plan_metadata_patch, rewrite_markdown_attributes
from todoc.application.paging import cursor_offset, next_page_cursor, page, selection_key
from todoc.application.filters import OPERATORS, compile_conditions, matches_conditions, split_values, tag_matches
from todoc.application.query import (aggregate_records, build_tree, graph_neighbors, query_records,
                                     slice_relation_tree)
from todoc.application.folder_config import load_folder_configs, score_folder_configs
from todoc.application.state import get_var, load_state, set_var, unset_var
from todoc.application.search import search_documents
from todoc.application.skills import scan_skills
from todoc.application.staleness import check_all, collect_owners, current_hashes, fragment_hash, plan_ack
from todoc.application.temporal import InvalidInstant, timeline as build_timeline
from todoc.domain.models import WritePlan
from todoc.application.validator import (_basename_index, _check_meta_fields, _doc_types_of, _entity_types_of,
                                         _load_schemas, _wikilink_candidates, stable_id)
from todoc.application.sync import sync_files
from todoc.application.write import (apply_undo_relation, apply_write_plan,
                                     create_document_plan, create_record_plan, load_input_record,
                                     plan_edit_ops, plan_undo_relation)
from todoc.config import init_dataset
from todoc.errors import (EXIT_CONFLICT, EXIT_INCOMPLETE, EXIT_OPERATION, EXIT_USAGE, EXIT_VALIDATION,
                          AccessError, ConflictError, IncompleteError, TodocError, ValidationError)
from todoc.output.envelope import Envelope, emit
from todoc.output.guidance import guidance_for
from todoc.output.capabilities import (UnifiedCommand, command_name, command_preferences, group_discovery,
                                       resolved_output)
from todoc.output.filter_options import AttributeFilterCommand
from todoc.output.views import mermaid_graph, project_fields, selected_fields
from todoc.service import DatasetContext, resolve_roots
from todoc.typing_system.document_metadata import (SCHEMA_PATH, default_metadata_schema, load_metadata_schema,
                                                 metadata_errors, normalize_markdown_attributes)
from todoc.typing_system.descriptors import (PROMPT_OPERATIONS, descriptor_diagnostics,
                                             load_json_file, prompt_files, schema_file,
                                             template_file, type_kind_dir)


def _emit_result(data: dict[str, Any], output: str, diagnostics: list[dict[str, Any]], failed: bool) -> None:
    """Emit a dataset report with one diagnostics list and the matching exit code."""
    command = command_name(click.get_current_context())
    roots = [report["root"] for report in data["datasets"]]
    response = Envelope.result({"command": command, "scope": {"roots": roots}}, data, diagnostics=diagnostics)
    response.ok = not failed
    if diagnostics:
        first = diagnostics[0]
        if any(fix.get("autofixable") for fix in first.get("suggested_fixes", [])):
            response.next_actions = [
                {"argv": ["todoc", "fix", "--root", first["root"], "--diagnostic", first["id"], "--preview"],
                 "purpose": "Показать план исправления"}
            ]
        else:
            response.next_actions = [
                {"argv": ["todoc", *command.split(), "--help"], "purpose": "Посмотреть инструкции команды"}
            ]
    emit(response, output)
    if failed:
        raise click.exceptions.Exit(EXIT_VALIDATION)


def _scan_sources(ctx: DatasetContext):
    try:
        return ctx.scan_and_validate(ctx.scan(strict=True), write_cache=False)
    except OSError as exc:
        raise IncompleteError(f"Could not read dataset {ctx.root}: {exc}") from exc


SECTION_MAX_LINES = 40


def _effective_roots(roots: tuple[str, ...]) -> tuple[str, ...]:
    """Select the nearest explicit roots, respecting repeats at that level."""
    ctx = click.get_current_context(silent=True)
    return roots or (command_preferences(ctx).get("roots", ()) if ctx is not None else ())


def _contexts(roots: tuple[str, ...]) -> list[DatasetContext]:
    return [DatasetContext(r) for r in resolve_roots(_effective_roots(roots))]


def _root_argv(roots: tuple[str, ...]) -> list[str]:
    argv: list[str] = ["todoc"]
    for r in _effective_roots(roots):
        argv += ["--root", r]
    return argv


def _record_schema(ctx: "DatasetContext", entity_type: str) -> dict[str, Any] | None:
    """The entity type's JSON Schema, when it has one, from that type's own folder."""
    loaded = _load_schemas(ctx.root, ctx.registry_types, ctx.dataset,
                           "entity_type", _entity_types_of).get(entity_type)
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


def _check_line_start(start: int, total: int, line_range: str) -> None:
    """A range starting after the last line is a bad selector, not an empty success."""
    if start > total:
        raise ValidationError(
            f"Invalid --line-range: {line_range!r} starts after the file end ({total} lines).",
            "usage.invalid_line_range")


class DiscoverableGroup(click.Group):
    group_class = type

    def __init__(self, *args, **kwargs) -> None:
        kwargs.setdefault("invoke_without_command", True)
        super().__init__(*args, **kwargs)
        if not any(param.name == "roots" for param in self.params):
            self.params.extend((
                click.Option(["--root", "roots"], multiple=True, help="Dataset root (repeatable)."),
                click.Option(["--output"], type=click.Choice(["json", "table", "markdown"])),
                click.Option(["--no-input"], is_flag=True),
            ))

    def invoke(self, ctx: click.Context):
        if ctx.parent is None:
            return super().invoke(ctx)
        ctx.obj = command_preferences(ctx.parent)
        for name in ("roots", "output", "no_input"):
            value = ctx.params.pop(name)
            if value:
                ctx.obj[name] = value
        result = super().invoke(ctx)
        if ctx.invoked_subcommand is None:
            _emit_group_discovery(self, ctx, ctx.obj["output"])
        return result


def _emit_group_discovery(group: click.Group, ctx: click.Context, output: str) -> None:
    names = []
    while ctx.parent is not None:
        names.append(ctx.info_name or "")
        ctx = ctx.parent
    name = " ".join(reversed(names)) or "todoc"
    emit(Envelope(
        True, group_discovery(group, name), schema_version=2,
        guidance={"profile": "ru", "mode": "compact", "items": []},
    ), output)


@click.group(cls=DiscoverableGroup, invoke_without_command=True)
@click.option("--root", "roots", multiple=True, help="DATA_ROOT (repeatable). Or set TODOC_ROOT.")
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True, help="Non-interactive mode (never prompts).")
@click.version_option(__version__, prog_name="todoc")
@click.pass_context
def cli(ctx: click.Context, roots: tuple[str, ...], output: str, no_input: bool) -> None:
    """todoc — portable typed knowledge substrate (validator + bounded search/read)."""
    ctx.ensure_object(dict)
    ctx.obj["roots"] = roots
    ctx.obj["output"] = output
    ctx.obj["no_input"] = no_input
    if ctx.invoked_subcommand is None:
        _emit_group_discovery(cli, ctx, output)


@cli.command(cls=UnifiedCommand)
@click.option("--root", "root", required=True, help="DATA_ROOT to initialize.")
@click.option("--dataset-id", default=None,
              help="Идентификатор датасета. По умолчанию случаен; явное значение делает "
                   "демо-датасет и фикстуры воспроизводимыми.")
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
@click.option("--document-metadata", is_flag=True, help="Install the shared schema for managed documents.")
@click.option("--preview", is_flag=True)
@click.option("--apply", "apply_", is_flag=True)
@click.option("--if-plan-hash")
def init(root: str, dataset_id: str | None, output: str, no_input: bool, document_metadata: bool,
         preview: bool, apply_: bool, if_plan_hash: str | None) -> None:
    """Create portable .todoc/ control files (never scans/moves user data)."""
    _check_action_flags(preview, apply_)
    target = Path(root).resolve()
    control = target / ".todoc"
    if control.is_symlink():
        raise AccessError(f"Dataset control path is a symlink: {control}", "access.outside_data_root")
    if document_metadata and (target / SCHEMA_PATH).exists():
        raise ValidationError(f"Metadata schema already exists at {target / SCHEMA_PATH}", "metadata.schema_exists")
    if (control / "dataset.json").is_file():
        raise ValidationError(f"Dataset already initialized at {target}", "config.already_initialized")
    if dataset_id is not None:
        dataset_id = dataset_id.strip()
        if not dataset_id:
            raise ValidationError("dataset_id must be a non-empty string", "config.invalid_schema")
    plan_hash = selection_key([str(target), dataset_id, document_metadata])
    if if_plan_hash is not None and if_plan_hash != plan_hash:
        raise ConflictError("The initialization plan is stale.", "write.hash_mismatch")
    if apply_:
        dataset_id = init_dataset(target, dataset_id, document_metadata=document_metadata)["dataset_id"]
    emit(Envelope.result({"command": "init", "scope": {"root": str(target)}},
                         {"dataset_id": dataset_id, "root": str(target), "path": ".todoc/",
                          "created": ".todoc/" if apply_ else None, "applied": apply_,
                          "document_metadata": document_metadata, "plan_hash": plan_hash}), output)


@cli.command("check-config", cls=UnifiedCommand)
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
        load_metadata_schema(ctx.root)
        findings: list[dict[str, Any]] = []
        for kind, store in (("dir_type", ctx.registry_types.dir_types), ("doc_type", ctx.registry_types.doc_types),
                            ("entity_type", ctx.registry_types.entity_types),
                            ("relation_type", ctx.registry_types.relation_types)):
            for type_id in sorted(store):
                rel = f".todoc/{type_kind_dir(ctx.dataset, kind)}/{type_id}/type.json"
                for item in descriptor_diagnostics(ctx.root, ctx.dataset, kind, store[type_id], rel):
                    findings.append({
                        "dataset_id": ctx.dataset_id, "root": str(ctx.root), "id": stable_id(rel, item["code"], item["message"]),
                        "code": item["code"], "severity": item.get("severity", "error"),
                        "path": item["path"], "location": {},
                        "evidence": f"type_id: {type_id}", "message": item["message"], "suggested_fixes": [],
                    })
        collected.extend(findings)
        errors = [item for item in findings if item["severity"] == "error"]
        if errors:
            failed = True
        results.append({"dataset_id": ctx.dataset_id, "root": str(ctx.root), "ok": not errors,
                        "warnings": len(findings) - len(errors),
                        "dir_types": len(ctx.registry_types.dir_types),
                        "doc_types": len(ctx.registry_types.doc_types),
                        "entity_types": len(ctx.registry_types.entity_types),
                        "relation_types": len(ctx.registry_types.relation_types),
                        "issues": len(findings)})
    _emit_result({"datasets": results}, output, collected, failed)


@cli.command("check", cls=UnifiedCommand)
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
        _folders, documents, _records, _relations, diagnostics = _scan_sources(ctx)
        errors = sum(1 for d in diagnostics if d.get("severity") == "error")
        warnings = sum(1 for d in diagnostics if d.get("severity") == "warning")
        bad = bool(errors or (strict and warnings))
        has_error |= bad
        reports.append({"dataset_id": ctx.dataset_id, "root": str(ctx.root), "documents": len(documents), "errors": errors,
                        "warnings": warnings, "status": "issues_found" if bad else "ok"})
        collected.extend({**item, "root": str(ctx.root)} for item in diagnostics)
    _emit_result({"datasets": reports}, output, collected, has_error)


@cli.command("scan", cls=UnifiedCommand)
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
def scan(roots: tuple[str, ...], output: str, no_input: bool) -> None:
    """Deterministic traversal without writing indexes."""
    results = []
    for ctx in _contexts(roots):
        folders, documents, _r, _rel, diagnostics = _scan_sources(ctx)
        results.append({"dataset_id": ctx.dataset_id, "root": str(ctx.root), "folders": len(folders), "documents": len(documents),
                        "diagnostics": len(diagnostics)})
    _emit_result({"datasets": results}, output, [], False)


@cli.command("validate", cls=UnifiedCommand)
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
        _f, documents, _r, _rel, diagnostics = _scan_sources(ctx)
        errors = [d for d in diagnostics if d.get("severity") == "error"]
        if errors:
            has_error = True
        reports.append({"dataset_id": ctx.dataset_id, "root": str(ctx.root), "documents": len(documents), "diagnostic_count": len(diagnostics)})
        collected.extend({**item, "root": str(ctx.root)} for item in diagnostics)
    _emit_result({"datasets": reports}, output, collected, has_error)


@cli.group()
@click.pass_context
def index(ctx: click.Context) -> None:
    """Index status/rebuild (derived, rebuildable)."""


@index.command("status", cls=UnifiedCommand)
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
def index_status(roots: tuple[str, ...], output: str, no_input: bool) -> None:
    results = []
    for ctx in _contexts(roots):
        snapshot = ctx.index_status()
        meta = snapshot.meta or {}
        results.append({"dataset_id": ctx.dataset_id, "root": str(ctx.root),
                        "generation_id": meta.get("generation_id"), "current": snapshot.state == "valid",
                        "state": snapshot.state, "freshness": None, "corpus_digest": meta.get("corpus_digest"),
                        "created_at": meta.get("created_at")})
    _emit_result({"datasets": results}, output, [], False)


@index.command("rebuild", cls=UnifiedCommand)
@click.option("--root", "roots", multiple=True)
@click.option("--force", is_flag=True, help="Recompute even when the corpus digest is unchanged.")
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
@click.option("--preview", is_flag=True)
@click.option("--apply", "apply_", is_flag=True)
def index_rebuild(roots: tuple[str, ...], force: bool, output: str, no_input: bool,
                  preview: bool, apply_: bool) -> None:
    """Preview or publish a rebuilt index."""
    _check_action_flags(preview, apply_)
    results = []
    for ctx in _contexts(roots):
        if apply_:
            report = ctx.rebuild_index(force=force)
        else:
            snapshot = ctx.read_index(sections=("records",))
            report = {"documents": len(snapshot["documents"]), "records": len(snapshot["records"]),
                      "corpus_digest": snapshot["corpus_digest"], "force": force}
        results.append({"dataset_id": ctx.dataset_id, **report, "root": str(ctx.root), "applied": apply_})
    _emit_result({"datasets": results}, output, [], False)


@cli.group()
def skills() -> None:
    """Skills vault (open Agent Skills standard): tree/read/attach/import."""


@skills.command("tree", cls=UnifiedCommand)
@click.option("--root", "roots", multiple=True)
@click.option("--vault", default="skills", show_default=True, help="Vault dir relative to DATA_ROOT.")
@click.option("--within", default=None, help="Срез раздела: префикс пути секции (напр. coding/git).")
@click.option("--query", default=None, help="Lowercase-подстрока по name+description+пути (кириллица работает).")
@click.option("--all", "show_all", is_flag=True, help="Показать мьютнутые (!-папки) с пометкой [!].")
@click.option("--limit", type=click.IntRange(1, 1000), default=100, show_default=True, help="Bounded output (P7).")
@click.option("--max-depth", "--depth", type=click.IntRange(min=0), default=6, show_default=True, help="Глубина печатаемого дерева.")
@click.option("--view", default="tree", show_default=True)
@click.option("--fields", "include")
@click.option("--exclude-fields", "exclude")
@click.option("--cursor")
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
def skills_tree(roots: tuple[str, ...], vault: str, within: str | None, query: str | None,
                show_all: bool, limit: int, max_depth: int, view: str, include: str | None,
                exclude: str | None, cursor: str | None, output: str, no_input: bool) -> None:
    """Оглавление хранилища скилов на лету (live-scan, без индекса — P1)."""
    meta = _collection_meta("skills tree", view)
    actual_view = view if view in ("tree", "flat") else "tree"
    meta["actual_view"] = actual_view
    fields = selected_fields(
        ("id", "path", "name", "section", "description", "muted", "refs", "scripts", "assets"),
        include, exclude, structural=("id", "path"),
    )
    ctx = _single_context(roots, "skills")
    vault_root = _contained_out(ctx.root, vault)
    scope = normalize_scope(within or ".")
    meta["scope"] = {"dataset_id": ctx.dataset_id, "vault": vault, "within": scope}
    skills_list, scan_diags = scan_skills(vault_root)
    if not vault_root.is_dir():
        raise TodocError(f"Хранилище скилов не найдено: {vault}/ (DATA_ROOT: {ctx.root})",
                         EXIT_OPERATION, "skills.not_found")
    if len(skills_list) > 500:  # порог идеи: живой скан всегда, предупреждение вместо индекса
        sys.stderr.write(f"warning: {len(skills_list)} skills in vault — live scan may be slow\n")
    shown = [s for s in skills_list if show_all or not s.muted]
    shown = [skill for skill in shown if within_depth(skill.path, scope, max_depth)]
    vault_configs, config_diags = load_folder_configs(vault_root)
    section_meta = {rel: {"title": fc.title, "description": fc.description, "order": fc.order}
                    for rel, fc in vault_configs.items()}
    if query:
        q = query.lower()
        matched_sections = {rel for rel, fc in vault_configs.items()
                            if q in " ".join([fc.title, fc.description, "|".join(fc.aliases),
                                              " ".join(fc.tags)]).lower()}
        shown = [s for s in shown
                 if q in s.name.lower() or q in s.description.lower() or q in s.path.lower()
                 or any(s.section == ms or s.section.startswith(ms + "/") for ms in matched_sections)]

    items = [{"id": f"skill:{skill.path}", "name": skill.name, "path": skill.path,
              "section": skill.section, "description": skill.description, "muted": skill.muted,
              "refs": skill.refs, "scripts": skill.scripts, "assets": skill.assets}
             for skill in shown]
    relevant_findings = [
        finding for finding in scan_diags
        if within_depth(PurePosixPath(finding["path"]).parent.as_posix(), scope, max_depth)
    ]
    lost_source = [finding for finding in relevant_findings
                   if finding["code"] in ("skills.missing_front_matter", "access.outside_data_root")]
    if lost_source:
        emit(Envelope.collection(meta, [], diagnostics=lost_source), output)
        raise click.exceptions.Exit(EXIT_INCOMPLETE)
    rows, next_cursor = page(
        items, [2, "skills tree", ctx.dataset_id, vault, scope, query, show_all, max_depth,
                items, section_meta], limit, cursor,
    )
    truncated = next_cursor is not None
    meta.update(complete=True, total=len(items), returned=len(rows),
                truncated=truncated, next_cursor=next_cursor, max_depth=max_depth)
    projected = [project_fields(item, fields) for item in rows]
    visible_paths = {item["path"] for item in rows}
    visible_section_meta = {
        path: value for path, value in section_meta.items()
        if path in visible_paths or any(found.startswith(path + "/") for found in visible_paths)
    }
    data = {
        "dataset_id": ctx.dataset_id,
        "vault": vault,
        "counts": {"skills": len(skills_list),
                   "sections": len({s.section.split("/")[0] for s in skills_list if s.section}),
                   "muted": sum(1 for s in skills_list if s.muted)},
        "section_meta": visible_section_meta,
        "truncated": truncated,
    }
    if actual_view == "flat":
        data["items"] = projected
    else:
        data["skills"] = projected
        data["root"] = folder_tree(
            scope, [{**item, "kind": "skill"} for item in projected], folder_metadata=visible_section_meta,
        )
        if output != "json":
            data["tree_text"] = _skills_tree_text(rows, data["counts"], truncated, visible_section_meta, fields)
    diagnostics = (config_diags + [{**finding, "severity": "warning"} for finding in relevant_findings])
    if actual_view != view:
        diagnostics.append({"code": "view.fallback", "severity": "info", "path": "",
                            "message": f"Requested view {view!r}; returned {actual_view!r}."})
    response = Envelope.result(meta, data, diagnostics=diagnostics)
    if rows:
        response.next_actions = [
            {"argv": _root_argv(roots) + ["skills", "read", "--vault", vault, "--path", rows[0]["path"]],
             "purpose": "Прочитать SKILL.md выбранного скила"}
        ]
    emit(response, output)


def _skills_tree_text(shown: list[dict[str, Any]], counts: dict[str, int],
                      truncated: bool, sec_meta: dict[str, dict[str, Any]],
                      fields: tuple[str, ...]) -> str:
    """ASCII-дерево как в образце идеи: описания в stdout, [!] для мьюта."""
    lines = [f"skills/  ({counts['skills']} skills, {counts['sections']} sections, "
             f"{counts['muted']} muted){' [truncated]' if truncated else ''}"]
    sections: dict[str, list[dict[str, Any]]] = {}
    for s in shown:
        sections.setdefault(s["section"], []).append(s)

    children: dict[str, set[str]] = {}
    for section in sections.keys() - {""}:
        parts = section.split("/")
        for i in range(len(parts)):
            children.setdefault("/".join(parts[:i]), set()).add("/".join(parts[: i + 1]))

    def _sec_key(section: str) -> tuple[int, str]:
        order = (sec_meta.get(section) or {}).get("order")
        return (order if isinstance(order, int) else 10**9, section)

    def _render(node: str, depth: int) -> None:
        # глубина ограничена пре-фильтром shown (_depth < max_depth, P7):
        # узлы строятся только из префиксов показанных секций — отсечка не нужна
        own = sorted(sections.get(node, []), key=lambda x: x["path"].lstrip("!"))
        meta = sec_meta.get(node) or {}
        # BUG-008: счётчик раздела каскадный — own + все скилы подразделов; узел с
        # непустым поддеревом печатается, даже если собственных скилов/конфига нет
        cascade = sum(len(v) for k, v in sections.items()
                      if k == node or k.startswith(node + "/"))
        if node and (own or meta or cascade):
            label = f"{node.split('/')[-1]}/"
            if meta.get("title"):
                label += f" — {meta['title']}" + (f": {meta['description']}" if meta.get("description") else "")
            lines.append("  " * depth + f"{label} ({cascade})")
        for s in own:
            details = project_fields(s, fields)
            label = details.get("name", details["path"])
            if details.get("muted"):
                label = f"[!] {label}"
            description = details.get("description", "")
            lines.append("  " * (depth + 1) + f"{label}  {description}")
        for child in sorted(children.get(node, set()), key=_sec_key):
            _render(child, depth + 1)

    _render("", 0)
    return "\n".join(lines)


@skills.command("read", cls=UnifiedCommand)
@click.option("--root", "roots", multiple=True)
@click.option("--vault", default="skills", show_default=True)
@click.option("--path", "p", help="Skill folder or relative path to SKILL.md.")
@click.option("--line-range", help="Inclusive line range A-B.")
@click.option("--budget", type=click.IntRange(min=1), default=4000,
              help="Maximum Unicode characters of skill content.", show_default=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json")
@click.option("--no-input", is_flag=True)
def skills_read(roots: tuple[str, ...], vault: str, p: str | None, line_range: str | None,
                budget: int, output: str, no_input: bool) -> None:
    """Read one bounded skill source and its metadata."""
    meta = {"command": "skills read", "scope": None}
    if p is None:
        emit(Envelope(True, {"meta": meta, "executed": False, "result": {"input": "Pass --path."}},
                      schema_version=2, guidance=guidance_for([])), output)
        return
    ctx = _single_context(roots, "skills")
    vault = normalize_scope(vault)
    vault_root = _contained_out(ctx.root, vault)
    scope = normalize_scope(p)
    if scope.startswith(vault + "/"):
        scope = scope[len(vault) + 1:]
    if Path(scope).name == "SKILL.md":
        scope = Path(scope).parent.as_posix()
    skills_list, findings = scan_skills(vault_root)
    skill = next((item for item in skills_list if item.path in (scope, f"!{scope}")), None)
    if skill is None:
        issue = next((item for item in findings
                      if item["path"] in (f"{scope}/SKILL.md", "SKILL.md" if scope == "." else "")), None)
        if issue is not None:
            raise IncompleteError(issue["message"], issue["code"])
        raise TodocError(f"Skill not found: {p}", EXIT_OPERATION, "skills.not_found")
    target = vault_root / skill.skill_md
    if not is_within_root(vault_root, target):
        raise AccessError("Skill source is outside its vault.", "access.outside_data_root")
    try:
        expected = file_hash(target)
        source = read_verified_text(vault_root, skill.skill_md, expected)
    except OSError as exc:
        raise IncompleteError(f"Could not read skill file: {p}", "file.unreadable") from exc
    attributes = parse_markdown(source).front_matter
    name = str(attributes.get("name") or "")
    description = str(attributes.get("description") or "")
    if (name, description) != (skill.name, skill.description):
        raise IncompleteError(f"Skill metadata changed while reading: {p}", "read.changed")
    if line_range:
        start, end = _parse_line_range(line_range)
        lines = source.splitlines(keepends=True)
        _check_line_start(start, len(lines), line_range)
        source = "".join(lines[start - 1:end])
    content = source[:budget]
    meta["scope"] = {"dataset_id": ctx.dataset_id, "vault": vault, "path": skill.skill_md}
    response = Envelope.result(meta, {
        "path": skill.skill_md, "name": name, "description": description,
        "muted": skill.muted, "content": content, "hash": expected, "truncated": len(content) < len(source),
    })
    if len(content) < len(source):
        args = _root_argv(roots) + ["skills", "read", "--vault", vault, "--path", skill.path,
                                    "--budget", str(len(source))]
        if line_range:
            args += ["--line-range", line_range]
        response.next_actions = [{"argv": args, "purpose": "Дочитать содержимое с увеличенным лимитом"}]
    emit(response, output)


@skills.command("attach", cls=UnifiedCommand)
@click.option("--to", "to_dir", required=True,
              help="Каталог скилов платформы (.claude/skills/, .agents/skills/, .cursor/skills/, ...).")
@click.option("--root", "roots", multiple=True, help="DATA_ROOT, вшиваемый в тело диспетчера ({ROOT}).")
@click.option("--force", is_flag=True, help="Перезаписать существующий скил todoc.")
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
@click.option("--preview", is_flag=True)
@click.option("--apply", "apply_", is_flag=True)
@click.option("--if-plan-hash")
def skills_attach(roots: tuple[str, ...], to_dir: str, force: bool, output: str, no_input: bool,
                  preview: bool, apply_: bool, if_plan_hash: str | None) -> None:
    """Диспетчер-скил todoc → одна точка входа для любого агента.

    Копирует пакетную папку `todoc/` в платформенный каталог скилов, подставляя
    DATA_ROOT вместо {ROOT}. Витрина скилов в платформу НЕ монтируется —
    L1-контекст несёт ровно один скил (~100 токенов) при vault любого размера.
    """
    from importlib import resources

    _check_action_flags(preview, apply_)
    effective_roots = _effective_roots(roots)
    if len(effective_roots) != 1:
        raise TodocError("Укажите один --root DATA_ROOT.", EXIT_USAGE, "usage.error")
    root_resolved = Path(effective_roots[0]).resolve()
    dest = Path(to_dir).resolve() / "todoc"
    if dest.is_symlink() or (dest.exists() and not force):
        raise TodocError(f"{dest} уже существует; обновление — с --force.",
                         EXIT_CONFLICT, "attach.exists")
    pkg = resources.files("todoc") / "data" / "agent-skill" / "todoc"
    files = {}
    manifest = []
    with resources.as_file(pkg) as src_dir:
        for src in sorted(Path(src_dir).rglob("*")):
            if not src.is_file():
                continue
            rel = src.relative_to(src_dir).as_posix()
            target = dest / rel
            if target.is_symlink() or not is_within_root(dest, target):
                raise AccessError(f"Target is outside the dispatcher directory: {rel}", "access.outside_data_root")
            content = (src.read_text(encoding="utf-8").replace("{ROOT}", str(root_resolved)).encode("utf-8")
                       if src.name == "SKILL.md" else src.read_bytes())
            before = file_hash(target) if target.is_file() else None
            digest = "sha256:" + hashlib.sha256(content).hexdigest()
            files[rel] = (content, before)
            manifest.append({"path": rel, "source_hash": digest, "expected_hash": before})
    plan_hash = selection_key([str(root_resolved), str(dest), manifest])
    if if_plan_hash is not None and if_plan_hash != plan_hash:
        raise ConflictError("The dispatcher install plan is stale.", "write.hash_mismatch")
    if apply_:
        dest.mkdir(parents=True, exist_ok=force)
        for rel, (content, expected) in files.items():
            target = dest / rel
            if target.is_symlink() or not is_within_root(dest, target):
                raise AccessError(f"Target is outside the dispatcher directory: {rel}", "access.outside_data_root")
            if expected is not None and (not target.is_file() or file_hash(target) != expected):
                raise ConflictError(f"Dispatcher target changed: {target}", "write.hash_mismatch")
            try:
                atomic_write(target, content, exclusive=expected is None)
            except FileExistsError as exc:
                raise ConflictError(f"Dispatcher target already exists: {target}", "attach.exists") from exc
    envelope = Envelope.result({"command": "skills attach", "scope": {"root": str(root_resolved)}},
                               {"installed": str(dest / "SKILL.md") if apply_ else None,
                                "path": str(dest), "files": len(files), "manifest": manifest,
                                "root_embedded": str(root_resolved), "applied": apply_, "plan_hash": plan_hash})
    emit(envelope, output)


@skills.command("import", cls=UnifiedCommand)
@click.option("--root", "roots", multiple=True)
@click.option("--src", "src_dir", required=True, help="Локальная папка-скил или репо-пакет (**/SKILL.md).")
@click.option("--skill", "skill_filter", default=None, help="Копировать один скил (по имени папки).")
@click.option("--into", "section", required=True, help="Раздел vault, куда класть (напр. coding/review).")
@click.option("--vault", default="skills", show_default=True)
@click.option("--dry-run", "--preview", "dry_run", is_flag=True, help="Показать план без записи.")
@click.option("--adopt", is_flag=True, help="Источник уже в vault: валидировать и отчитаться без копии.")
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
@click.option("--apply", "apply_", is_flag=True)
@click.option("--if-plan-hash")
def skills_import(roots: tuple[str, ...], src_dir: str, skill_filter: str | None, section: str,
                  vault: str, dry_run: bool, adopt: bool, output: str, no_input: bool,
                  apply_: bool, if_plan_hash: str | None) -> None:
    """Офлайн-импорт чужих скилов: папки со SKILL.md, обвязка пакетов не переносится."""
    from todoc.application.skills import scan_skills, validate_skills, effective_name

    _check_action_flags(dry_run or adopt, apply_)
    ctx = _single_context(roots, "skills")
    vault = normalize_scope(vault)
    section = normalize_scope(section)
    vault_root = _contained_out(ctx.root, vault)
    section_root = _contained_out(vault_root, section)
    src = Path(src_dir).resolve()
    if not src.is_dir():
        raise TodocError(f"Источник не найден: {src}", EXIT_OPERATION, "skills.not_found")
    src_md = src / "SKILL.md"
    folders = [src] if src_md.is_file() else sorted(p.parent for p in src.rglob("SKILL.md"))
    if skill_filter:
        folders = [f for f in folders if effective_name(f.name) == skill_filter]
        if adopt and not folders:
            folders = [vault_root / section / skill_filter]
    if not folders:
        raise TodocError(f"В {src} нет SKILL.md"
                         + (f" (фильтр --skill {skill_filter})" if skill_filter else ""),
                         EXIT_OPERATION, "skills.not_found")

    imported: list[dict[str, str]] = []
    adopted: list[str] = []
    skipped: list[dict[str, str]] = []
    targets = []
    manifest = []
    for folder in folders:
        name = effective_name(folder.name)
        if adopt:
            dest = _contained_out(section_root, name)
            if not (dest / "SKILL.md").is_file():
                raise TodocError(f"Скил «{name}» не найден в vault: {section}/{name}/SKILL.md. "
                                 f"Скопируй папку в vault и повтори --adopt.",
                                 EXIT_OPERATION, "skills.not_found")
            adopted.append(name)
            continue
        dest = section_root / folder.name
        if dest.is_symlink() or not is_within_root(section_root, dest):
            raise AccessError(f"Destination is outside the skill section: {dest}", "access.outside_data_root")
        if (dest / "SKILL.md").exists() or (dest.exists() and any(dest.iterdir())):
            skipped.append({"name": name, "path": str(dest)})
            continue
        files = []
        for source in sorted(folder.rglob("*")):
            if source.is_symlink() or not is_within_root(folder, source):
                raise AccessError(f"Skill source contains a symlink: {source}", "access.outside_data_root")
            if source.is_dir():
                continue
            if not source.is_file():
                raise AccessError(f"Unsupported skill source: {source}", "skills.unsupported_source")
            files.append({"path": source.relative_to(folder).as_posix(), "hash": file_hash(source),
                          "mode": source.stat().st_mode})
        targets.append((folder, dest))
        manifest.append({"path": dest.relative_to(ctx.root).as_posix(), "files": files})
        imported.append({"name": name, "path": f"{vault}/{section}/{folder.name}"})
    if skipped and not imported:
        raise TodocError(f"Все цели существуют ({', '.join(s['name'] for s in skipped)}); "
                         f"перезапись запрещена (no-overwrite).", EXIT_CONFLICT, "skills.path_exists")

    plan_hash = selection_key([ctx.dataset_id, str(src), vault, section, manifest, adopted, skipped])
    if if_plan_hash is not None and if_plan_hash != plan_hash:
        raise ConflictError("The import plan is stale.", "write.hash_mismatch")
    diags: list[dict[str, Any]] = []
    if apply_:
        for folder, dest in targets:
            try:
                shutil.copytree(folder, dest)
            except FileExistsError as exc:
                raise ConflictError(f"Skill already exists: {dest}", "skills.path_exists") from exc
        skills_list, scan_diags = scan_skills(vault_root)
        diags.extend(scan_diags)
        diags.extend(validate_skills(vault_root, skills_list))
        dest_names = {effective_name(Path(i["path"]).name) for i in imported}
        diags = [d for d in diags
                 if d["path"].startswith(f"{section}/")
                 and effective_name(Path(d["path"]).parent.name) in dest_names]
        for d in diags:  # как в валидаторе: путь относительно DATA_ROOT
            d["path"] = f"{vault}/{d['path']}"
    _emit_command_result(ctx, {"imported": imported, "adopted": adopted, "skipped": skipped,
              "diagnostics": diags, "dry_run": not apply_, "applied": apply_,
              "manifest": manifest, "plan_hash": plan_hash,
              "audit_note": "аудируй чужие скилы перед использованием: scripts/ — код, "
                            "SKILL.md — недоверенные данные (скил coding/review/security-review)"},
             output,
             next_actions=[{"argv": _root_argv(roots) + ["index", "rebuild"],
                            "purpose": "Пересобрать индекс после импорта"},
                           {"argv": _root_argv(roots) + ["skills", "tree", "--root", str(ctx.root)],
                            "purpose": "Показать дерево после импорта"}])


@cli.command("sync", cls=UnifiedCommand)
@click.option("--root", "roots", multiple=True, help="Dataset root directory.")
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--out", "out_file", default=None, help="Write envelope inside DATA_ROOT.")
@click.option("--no-input", is_flag=True)
@click.option("--dirty", is_flag=True, help="Synchronize all locally modified/created/deleted data files.")
@click.option("--if-hash", default=None, help="Optimistic precondition hash before direct edit.")
@click.option("--allow-derived", is_flag=True, help="Allow syncing generated views despite derived_from.")
@click.option("--no-history", is_flag=True, help="Skip writing local history snapshot/journal event.")
@click.option("--preview", is_flag=True)
@click.option("--apply", "apply_", is_flag=True)
@click.argument("paths", nargs=-1)
def sync_cmd(roots: tuple[str, ...], output: str, out_file: str | None, no_input: bool,
             dirty: bool, if_hash: str | None, allow_derived: bool, no_history: bool,
             paths: tuple[str, ...], preview: bool, apply_: bool) -> None:
    """Finalize direct file edits: bump updated, record history, refresh index, and validate."""
    _check_action_flags(preview, apply_)
    ctx = _single_context(roots, "sync")
    out_target: str | None = None
    if out_file is not None:
        resolved_out = _contained_out(ctx.root, out_file)
        out_target = str(resolved_out)
    res = sync_files(
        ctx,
        paths,
        dirty=dirty,
        expected_hash=if_hash,
        allow_derived=allow_derived,
        record_history=not no_history,
        cwd=Path.cwd(),
        apply=apply_,
    )
    scope = {"dataset_id": ctx.dataset_id, "root": str(ctx.root)}
    envelope = Envelope.result({"command": "sync", "scope": scope},
                               {"synced": res["synced"], "diagnostics_count": len(res["diagnostics"]),
                                "preview": not apply_, "applied": apply_, "out": out_target},
                               diagnostics=res["diagnostics"])
    if res["guidance"] is not None:
        envelope.guidance["items"].append(res["guidance"])
    if apply_ and out_target is not None:
        Path(out_target).parent.mkdir(parents=True, exist_ok=True)
    emit(envelope, output, out_target if apply_ else None)
    if not res["ok"]:
        raise click.exceptions.Exit(EXIT_VALIDATION)


@cli.command("stale", cls=UnifiedCommand)
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
@click.option("--path", default=None, help="Only this owner document/record.")
@click.option("--severity", default=None, help="Filter diagnostics by severity.")
@click.option("--ack", "ack_path", default=None, help="Acknowledge staleness of this owner.")
@click.option("--reason", default=None, help="Why the drift is not relevant (required with --ack).")
@click.option("--preview", is_flag=True)
@click.option("--apply", "apply_ack", is_flag=True, help="Write the acknowledgement (default: preview).")
@click.option("--expected-hash", default=None)
def stale(roots: tuple[str, ...], output: str, no_input: bool, path: str | None, severity: str | None,
          ack_path: str | None, reason: str | None, preview: bool, apply_ack: bool, expected_hash: str | None) -> None:
    """Report documents whose dependencies drifted, or acknowledge a drift."""
    _check_action_flags(preview, apply_ack)
    if apply_ack and not ack_path:
        raise TodocError("--apply requires --ack.", EXIT_USAGE, "usage.error")
    ctx = _single_context(roots, "stale")
    payload = ctx.read_index(sections=("records",))
    if ack_path:
        _stale_ack(ctx, ack_path, reason, apply_ack, expected_hash, output, payload)
        return
    diagnostics = check_all(ctx.dataset_id, ctx.root, payload, only_path=path)
    if severity:
        diagnostics = [d for d in diagnostics if d.severity == severity]
    _emit_command_result(ctx, {"path": path, "stale": len(diagnostics)}, output,
             [d.to_dict() for d in diagnostics])


def _stale_ack(ctx: DatasetContext, ack_path: str, reason: str | None, apply_ack: bool,
               expected_hash: str | None, output: str, payload: dict[str, Any]) -> None:
    if not reason:
        raise TodocError("--ack requires --reason: an acknowledgement without a reason is not reviewable",
                       EXIT_USAGE, "usage.error")
    owners = {o["path"]: o for o in collect_owners(ctx.root, payload)}
    owner = owners.get(ack_path)
    if owner is None:
        raise TodocError(f"No dependencies declared in {ack_path}", EXIT_OPERATION, "staleness.owner_not_found")
    if owner["kind"] != "document":
        raise TodocError("--ack writes markdown front matter; records are edited directly",
                         EXIT_OPERATION, "staleness.ack_unsupported")
    current = current_hashes(ctx.root, owner)
    if not current:
        raise TodocError(f"No resolvable dependencies in {ack_path}", EXIT_OPERATION, "staleness.ack_unsupported")
    source_hash = file_hash(ctx.root / ack_path)
    if expected_hash is not None and source_hash != expected_hash:
        raise ConflictError("The acknowledgement plan is stale.", "write.hash_mismatch")
    new_text = plan_ack(ctx.root, ack_path, reason, datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), current)
    if not apply_ack:
        _emit_command_result(ctx, {"path": ack_path, "applied": False,
                  "reason": reason, "acknowledged_hashes": current, "expected_hash": source_hash}, output)
        return
    new_hash = _write_whole(ctx, ack_path, new_text, source_hash,
                            history=ctx.history_recorder(), basis="stale --ack")
    ctx.ensure_index()
    _emit_command_result(ctx, {"path": ack_path, "applied": True, "new_hash": new_hash,
              "reason": reason, "acknowledged_hashes": current}, output)


# --- история: журнал, откат, метки -------------------------------------------


@cli.command("log", cls=UnifiedCommand)
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
@click.option("--path", default=None)
@click.option("--section", default=None, help="Только события, пересекающие этот заголовок.")
@click.option("--change", "change_id", default=None)
@click.option("--history-tag", "--tag", "tag", default=None)
@click.option("--kind", default=None)
@click.option("--since", default=None)
@click.option("--until", default=None)
@click.option("--limit", type=click.IntRange(1, 1000), default=20)
@click.option("--cursor", default=None)
@click.option("--fields", "include")
@click.option("--exclude-fields", "exclude")
@click.option("--view", default="flat")
def log_cmd(roots: tuple[str, ...], output: str, no_input: bool, path: str | None, section: str | None,
            change_id: str | None, tag: str | None, kind: str | None, since: str | None, until: str | None,
            limit: int, cursor: str | None, include: str | None, exclude: str | None, view: str) -> None:
    """List matching history events in reverse journal order."""
    if section and not path:
        raise TodocError("--section требует --path: раздел ищется внутри файла", EXIT_USAGE, "usage.error")
    meta = _collection_meta("log")
    meta["requested_view"] = view
    try:
        resolved = resolve_roots(_effective_roots(roots))
        if len(resolved) != 1:
            raise TodocError("Choose exactly one DATA_ROOT.", EXIT_USAGE, "history.multiple_roots")
        ctx = DatasetContext(resolved[0])
        if path is not None:
            path = normalize_scope(path)
            _contained_out(ctx.root, path)
        meta["scope"] = {"dataset_id": ctx.dataset_id, "path": path}
        entries = ctx.history_store.read_events(strict=True)
        refs = ctx.history_store.read_refs() if tag else {}
        text_hash = None
        if section and path:
            target = ctx.root / path
            try:
                text_hash = file_hash(target)
            except OSError as exc:
                raise IncompleteError(f"Could not read {path}.", "history.source_unreadable") from exc
        fields = ("rev", "schema_version", "at", "kind", "actor", "change_id", "paths", "basis")
        extra_fields = {key for event in entries for key in event if key not in fields}
        fields = selected_fields(fields + tuple(sorted(extra_fields)), include, exclude, structural=("rev",))
        events, total, _ = history_log(ctx.root, path=path, section=section, kind=kind,
                                       change_id=change_id, tag=tag, since=since, until=until,
                                       limit=len(entries), events=entries, refs=refs)
        if section and path:
            try:
                if file_hash(ctx.root / path) != text_hash:
                    raise IncompleteError(f"Source changed while reading {path}.", "history.source_changed")
            except OSError as exc:
                raise IncompleteError(f"Could not read {path}.", "history.source_unreadable") from exc
        cursor_args = [2, "log", ctx.dataset_id, entries, refs, path, section,
                       change_id, tag, kind, since, until, text_hash]
        selected, next_cursor = page(events, cursor_args, limit, cursor)
    except TodocError as exc:
        _emit_collection_error(meta, exc.code, exc.message, output)
        raise click.exceptions.Exit(exc.exit_code) from exc
    meta.update(complete=True, total=total, returned=len(selected),
                truncated=next_cursor is not None, next_cursor=next_cursor)
    emit(Envelope.collection(meta, [project_fields(event, fields) for event in selected],
                            diagnostics=_view_diagnostics(meta)), output)


def _check_action_flags(preview: bool, apply_: bool) -> None:
    if preview and apply_:
        raise TodocError("--apply cannot be combined with --preview.", EXIT_USAGE, "usage.error")


def _emit_command_result(ctx: DatasetContext, result: dict[str, Any], output: str,
                         diagnostics: list[dict[str, Any]] | None = None, *,
                         next_actions: list[dict[str, Any]] | None = None) -> None:
    scope = {"dataset_id": ctx.dataset_id, "root": str(ctx.root)}
    envelope = Envelope.result({"command": command_name(click.get_current_context()), "scope": scope},
                               result, diagnostics=diagnostics)
    if next_actions is not None:
        envelope.next_actions = next_actions
    emit(envelope, output)


@cli.command("show", cls=UnifiedCommand)
@click.argument("rev", required=False, default=None)
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
@click.option("--path", required=True)
@click.option("--budget", type=click.IntRange(min=1), default=None)
def show_cmd(rev: str | None, roots: tuple[str, ...], output: str, no_input: bool, path: str,
             budget: int | None) -> None:
    """Содержимое файла на ревизии (или текущее, если rev не задан)."""
    ctx = _single_context(roots, "history")
    path = normalize_scope(path)
    _contained_out(ctx.root, path)
    resolved = resolve_rev(ctx.root, rev, refs=ctx.history_store.read_refs()) if rev else None
    text, status = history_show(ctx.root, resolved, path, backend=ctx.history_recorder().backend,
                                store=ctx.history_store)
    if text is None:
        raise _history_unavailable(status, path)
    content = text[:budget]
    _emit_command_result(ctx, {"path": path, "rev": resolved, "content": content,
                               "truncated": len(content) < len(text)}, output)


@cli.command("diff", cls=UnifiedCommand)
@click.argument("rev_a", required=False, default=None)
@click.argument("rev_b", required=False, default=None)
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
@click.option("--path", required=True)
@click.option("--context", "ctx_lines", type=click.IntRange(min=0), default=3)
@click.option("--budget", type=click.IntRange(min=1), default=None)
def diff_cmd(rev_a: str | None, rev_b: str | None, roots: tuple[str, ...], output: str, no_input: bool,
             path: str, ctx_lines: int, budget: int | None) -> None:
    """Разница между двумя ревизиями файла; без rev_b — против текущего состояния."""
    ctx = _single_context(roots, "history")
    path = normalize_scope(path)
    _contained_out(ctx.root, path)
    backend = ctx.history_recorder().backend
    refs = ctx.history_store.read_refs() if rev_a or rev_b else {}
    left, status_a = history_show(ctx.root, resolve_rev(ctx.root, rev_a, refs=refs) if rev_a else None, path, backend=backend,
                                   store=ctx.history_store)
    right, status_b = history_show(ctx.root, resolve_rev(ctx.root, rev_b, refs=refs) if rev_b else None, path, backend=backend,
                                   store=ctx.history_store)
    if left is None:
        raise _history_unavailable(status_a, path)
    if right is None:
        raise _history_unavailable(status_b, path)
    lines = diff_texts(left, right, context=ctx_lines)
    text = "\n".join(lines)
    excerpt = text[:budget]
    returned = excerpt.split("\n") if excerpt else []
    _emit_command_result(ctx, {"path": path, "rev_a": rev_a, "rev_b": rev_b,
                               "changed": bool(lines), "lines": len(returned), "diff": returned,
                               "truncated": len(excerpt) < len(text)}, output)


@cli.command("blame", cls=UnifiedCommand)
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
@click.option("--path", required=True)
@click.option("--section", default=None)
@click.option("--fields", "include")
@click.option("--exclude-fields", "exclude")
@click.option("--limit", type=click.IntRange(1, 1000), default=50, show_default=True)
@click.option("--cursor")
@click.option("--view", default="flat")
def blame_cmd(roots: tuple[str, ...], output: str, no_input: bool, path: str, section: str | None,
              include: str | None, exclude: str | None, limit: int, cursor: str | None, view: str) -> None:
    """List changes to a file or one of its sections."""
    ctx = _single_context(roots, "history")
    path = normalize_scope(path)
    _contained_out(ctx.root, path)
    entries = history_blame(ctx.root, path, section, store=ctx.history_store)
    fields = selected_fields(("rev", "at", "kind", "actor", "change_id", "ranges"), include, exclude,
                             structural=("rev",))
    meta = _collection_meta("blame")
    scope = {"dataset_id": ctx.dataset_id, "path": path, "section": section}
    meta.update(scope=scope, requested_view=view)
    _emit_flat_page(meta, entries, [2, "blame", scope, entries], fields, limit, cursor, output)


@cli.command("timeline", cls=UnifiedCommand)
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
@click.option("--as-of", "as_of", default=None, help="Состояние на этот момент (ISO-8601).")
@click.option("--path", default=None, help="Только события и факты этого файла.")
@click.option("--limit", type=click.IntRange(0, 1000), default=200, show_default=True)
@click.option("--cursor")
@click.option("--fields", "include")
@click.option("--exclude-fields", "exclude")
@click.option("--view", default="flat")
def timeline_cmd(roots: tuple[str, ...], output: str, no_input: bool, as_of: str | None,
                 path: str | None, limit: int, cursor: str | None, include: str | None,
                 exclude: str | None, view: str) -> None:
    """List journal events and fact intervals in chronological order."""
    ctx = _single_context(roots, "history")
    if path is not None:
        path = normalize_scope(path)
        _contained_out(ctx.root, path)
    payload = ctx.read_index(sections=("records", "relations"))
    events = ctx.history_store.read_events(strict=True)
    try:
        result = build_timeline(ctx.root, payload["records"], payload["relations"],
                                as_of=as_of, path=path, limit=None, events=events)
    except InvalidInstant as exc:
        raise ValidationError(str(exc), "temporal.invalid_instant") from exc
    scope = {"dataset_id": ctx.dataset_id, "as_of": result["as_of"], "path": path}
    meta = _collection_meta("timeline")
    meta.update(scope=scope, requested_view=view)
    fields = selected_fields(("kind", "entry", "at", "path", "rev", "change_id", "valid_from",
                              "valid_to", "observed_at", "superseded_at", "source_id", "target_id", "type_id"),
                             include, exclude, structural=("entry", "path"))
    selection = [2, "timeline", scope, payload["corpus_digest"], events]
    _emit_flat_page(meta, result["entries"], selection, fields, limit, cursor, output)


@cli.command("revert", cls=UnifiedCommand)
@click.argument("rev")
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
@click.option("--path", required=True)
@click.option("--preview", is_flag=True)
@click.option("--apply", "apply_revert", is_flag=True)
@click.option("--expected-hash", default=None)
def revert_cmd(rev: str, roots: tuple[str, ...], output: str, no_input: bool, path: str,
               preview: bool, apply_revert: bool, expected_hash: str | None) -> None:
    """Откат файла к ревизии. Без --apply — только план (review-first)."""
    if preview and apply_revert:
        raise TodocError("--apply cannot be combined with --preview.", EXIT_USAGE, "usage.error")
    ctx = _single_context(roots, "history")
    path = normalize_scope(path)
    _contained_out(ctx.root, path)
    recorder = ctx.history_recorder()
    resolved = resolve_rev(ctx.root, rev, refs=ctx.history_store.read_refs())
    plan = revert_plan(ctx.root, resolved, path, backend=recorder.backend, store=ctx.history_store)
    if plan["status"] != "ok":
        raise _history_unavailable(plan["status"], path)
    # Файл менялся после этой ревизии: откат сотрёт более поздние правки. Не ошибка
    # (решение за пользователем), но и не молчаливое действие — предупреждение в конверте.
    warnings: list[dict[str, Any]] = []
    if plan.get("range_conflict"):
        warnings.append({
            "dataset_id": ctx.dataset_id, "id": f"history.range_conflict:{path}:{rev}",
            "code": "history.range_conflict", "severity": "warning", "path": path,
            "message": f"Файл {path} изменён после {rev}: откат сотрёт более поздние правки",
            "location": {}, "evidence": f"текущий хеш {plan['current_hash'][:19]}…",
            "suggested_fixes": [],
        })
    if not apply_revert:
        _emit_command_result(ctx, {"path": path, "rev": rev, "applied": False,
                  "current_hash": plan["current_hash"], "new_hash": plan["new_hash"],
                  "range_conflict": bool(plan.get("range_conflict"))}, output, warnings)
        return
    if expected_hash is not None and expected_hash != plan["current_hash"]:
        raise ConflictError(f"Hash mismatch for {path}", "write.hash_mismatch")
    new_hash = _write_whole(ctx, path, plan["content"], plan["current_hash"], history=recorder,
                            basis=f"revert {rev}")
    ctx.ensure_index()
    _emit_command_result(ctx, {"path": path, "rev": rev, "applied": True,
              "new_hash": new_hash, "range_conflict": bool(plan.get("range_conflict"))},
             output, warnings)


@cli.command("tag", cls=UnifiedCommand)
@click.argument("name")
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
@click.option("--rev", default=None, help="По умолчанию — последнее событие журнала.")
@click.option("--message", default="")
@click.option("--preview", is_flag=True)
@click.option("--apply", "apply_", is_flag=True)
@click.option("--if-plan-hash")
def tag_cmd(name: str, roots: tuple[str, ...], output: str, no_input: bool, rev: str | None,
            message: str, preview: bool, apply_: bool, if_plan_hash: str | None) -> None:
    """Метка на ревизии: привязка истории к релизу."""
    if preview and apply_:
        raise TodocError("--apply cannot be combined with --preview.", EXIT_USAGE, "usage.error")
    ctx = _single_context(roots, "history")
    store = ctx.history_store
    events = store.read_events(strict=True)
    refs = store.read_refs()
    target = resolve_rev(ctx.root, rev, refs=refs) if rev else (events[-1]["rev"] if events else None)
    if target is None or not any(event["rev"] == target for event in events):
        raise IncompleteError("Нет события для этой метки.", "history.revision_unknown")
    plan_hash = selection_key([ctx.dataset_id, refs, name, target, message])
    if if_plan_hash is not None and if_plan_hash != plan_hash:
        raise ConflictError("The tag plan is stale.", "write.hash_mismatch")
    entry = {"rev": target, "message": message}
    if apply_:
        entry = add_tag(ctx.root, name, target, message, store=store, expected_refs=refs)
    _emit_command_result(ctx, {"tag": name, **entry, "plan_hash": plan_hash, "applied": apply_}, output)


@cli.group()
@click.pass_context
def history(ctx: click.Context) -> None:
    """Обслуживание истории: сборка мусора, миграция, бэкап."""


@history.command("gc", cls=UnifiedCommand)
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
@click.option("--keep-objects", type=click.IntRange(min=0), default=None)
@click.option("--purge-before", default=None)
@click.option("--dry-run", "--preview", "dry_run", is_flag=True, help="Preview without modifying history.")
@click.option("--apply", "apply_", is_flag=True, help="Apply history cleanup.")
@click.option("--if-plan-hash")
def history_gc(roots: tuple[str, ...], output: str, no_input: bool, keep_objects: int | None,
               purge_before: str | None, dry_run: bool, apply_: bool, if_plan_hash: str | None) -> None:
    """Удаляет события и снимки согласно плану очистки."""
    if dry_run and apply_:
        raise TodocError("--apply cannot be combined with --preview.", EXIT_USAGE, "usage.error")
    ctx = _single_context(roots, "history")
    store = ctx.history_store
    events = store.read_events(strict=True)
    refs = store.read_refs()
    manifest = store.backup_manifest()
    snapshots = store.list_snapshots()
    limits = ctx.dataset.get("limits") or {}
    plan_hash = selection_key([ctx.dataset_id, manifest, snapshots, keep_objects, purge_before, limits])
    if if_plan_hash is not None and if_plan_hash != plan_hash:
        raise ConflictError("The cleanup plan is stale.", "write.hash_mismatch")
    result = history_gc_run(ctx.root, keep_objects=keep_objects, purge_before=purge_before,
                            dry_run=not apply_, limits=limits, events=events, refs=refs,
                            store=store, snapshots=snapshots)
    _emit_command_result(ctx, {**result, "plan_hash": plan_hash, "applied": apply_}, output)


@history.command("adopt", cls=UnifiedCommand)
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
@click.option("--preview", is_flag=True)
@click.option("--apply", "apply_", is_flag=True)
@click.option("--if-plan-hash")
def history_adopt(roots: tuple[str, ...], output: str, no_input: bool,
                  preview: bool, apply_: bool, if_plan_hash: str | None) -> None:
    """Миграция: снимок текущего состояния как базовая линия журнала."""
    if preview and apply_:
        raise TodocError("--apply cannot be combined with --preview.", EXIT_USAGE, "usage.error")
    ctx = _single_context(roots, "history")
    payload = ctx.read_index(sections=())
    if _document_read_failures(payload, "."):
        raise IncompleteError("The dataset has unreadable source files.", "history.source_unreadable")
    files = [{"path": doc["path"], "hash": doc["hash"]} for doc in payload["documents"]]
    store = ctx.history_store
    history_basis = store.read_events(strict=True), store.read_refs()
    plan_hash = selection_key([ctx.dataset_id, payload["corpus_digest"], *history_basis])
    if if_plan_hash is not None and if_plan_hash != plan_hash:
        raise ConflictError("The adoption plan is stale.", "write.hash_mismatch")
    if apply_:
        result = history_adopt_run(ctx.root, files, store=store, expected_history=history_basis)
    else:
        result = {"paths": len(files)}
    _emit_command_result(ctx, {**result, "plan_hash": plan_hash, "applied": apply_}, output)


@history.command("export", cls=UnifiedCommand)
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
@click.option("--to", "destination", required=True)
@click.option("--preview", is_flag=True)
@click.option("--apply", "apply_", is_flag=True)
@click.option("--if-plan-hash")
def history_export(roots: tuple[str, ...], output: str, no_input: bool, destination: str,
                   preview: bool, apply_: bool, if_plan_hash: str | None) -> None:
    """Preview a backup manifest and export it into a new directory."""
    if preview and apply_:
        raise TodocError("--apply cannot be combined with --preview.", EXIT_USAGE, "usage.error")
    ctx = _single_context(roots, "history")
    target = _contained_out(ctx.root, destination)
    store = ctx.history_store
    store.check_backup_destination(target)
    if target.exists():
        raise ConflictError(f"Backup already exists: {target}", "write.target_exists")
    store.read_events(strict=True)
    store.read_refs()
    manifest = store.backup_manifest()
    plan_hash = selection_key([ctx.dataset_id, target.relative_to(ctx.root).as_posix(), manifest])
    if if_plan_hash is not None and if_plan_hash != plan_hash:
        raise ConflictError("The export plan is stale.", "write.hash_mismatch")
    exported = store.write_backup(target, manifest) if apply_ else 0
    _emit_command_result(ctx, {"to": str(target), "files": len(manifest), "exported": exported,
                               "plan_hash": plan_hash, "applied": apply_}, output)


@cli.group()
@click.pass_context
def change(ctx: click.Context) -> None:
    """Записи изменений: жизненный цикл, проверка применимости, bundle-применение."""


def _descriptor_lookup(ctx: Any):
    """Описатель doc_type для пробной проверки структуры после применения дельты."""
    payload = ctx.read_index(sections=())

    def lookup(front_matter: dict[str, Any], rel_path: str) -> dict[str, Any] | None:
        # Тип документа объявлен в его front matter; индекс хранит результат
        # маршрутизации и для большинства файлов даёт "unknown". Читать только индекс
        # означало бы никогда не проверять структуру после применения дельты.
        doc_type = str((front_matter or {}).get("doc_type") or "")
        if not doc_type:
            for doc in payload.get("documents") or []:
                if doc.get("path") == rel_path:
                    doc_type = str(doc.get("doc_type") or "")
                    break
        if not doc_type or doc_type == "unknown":
            return None
        descriptor = dict(getattr(ctx.registry_types, "doc_types", {}).get(doc_type) or {})
        if not descriptor:
            return None
        schema_path = schema_file(ctx.root, ctx.dataset, "doc_type", descriptor)
        if schema_path is not None and schema_path.is_file():
            try:
                loaded = load_json_file(schema_path)
            except ValidationError:
                loaded = None
            if isinstance(loaded, dict):
                descriptor["schema_data"] = loaded
        return descriptor

    return lookup


_CHANGE_FIELDS = ("record_id", "path", "entity_type", "title", "status", "created_at",
                  "applied_at", "archived_at", "reverted_at", "artifacts", "relations")


@change.command("list", cls=UnifiedCommand)
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
@click.option("--status", "statuses", multiple=True)
@click.option("--view", default="flat")
@click.option("--fields", "include")
@click.option("--exclude-fields", "exclude")
@click.option("--limit", type=click.IntRange(1, 1000), default=50, show_default=True)
@click.option("--cursor")
def change_list(roots: tuple[str, ...], output: str, no_input: bool, statuses: tuple[str, ...],
                view: str, include: str | None, exclude: str | None, limit: int, cursor: str | None) -> None:
    """List active and archived changes, with filters applied before pagination."""
    ctx = _single_context(roots, "change")
    wanted = split_values(statuses)
    entries = list_change_entries(ctx.root)
    items = [{key: value for key, value in item.items() if key != "baseline"}
             for item in entries if not wanted or item.get("status") in wanted]
    extra = {key for item in items for key in item.keys() - set(_CHANGE_FIELDS)}
    fields = selected_fields(_CHANGE_FIELDS + tuple(sorted(extra)), include, exclude,
                             structural=("record_id", "path"))
    meta = _collection_meta("change list")
    meta.update(scope={"dataset_id": ctx.dataset_id, "statuses": wanted}, requested_view=view)
    _emit_flat_page(meta, items, [2, "change list", ctx.dataset_id, wanted, entries],
                    fields, limit, cursor, output)


@change.command("open", cls=UnifiedCommand)
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
@click.option("--title", required=True)
@click.option("--blocked-by", multiple=True)
@click.option("--artifact", multiple=True)
@click.option("--preview", is_flag=True)
@click.option("--apply", "apply_", is_flag=True)
@click.option("--if-plan-hash")
def change_open(roots: tuple[str, ...], output: str, no_input: bool, title: str,
                blocked_by: tuple[str, ...], artifact: tuple[str, ...], preview: bool,
                apply_: bool, if_plan_hash: str | None) -> None:
    """Открывает изменение и снимает базовую линию."""
    _check_action_flags(preview, apply_)
    ctx = _single_context(roots, "change")
    change_id = change_id_for(title)
    path = record_path(ctx.root, change_id)
    if path.exists():
        raise ConflictError(f"Изменение уже существует: {change_id}", "change.id_invalid")
    artifacts = tuple(_contained_out(ctx.root, raw).relative_to(ctx.root).as_posix() for raw in artifact)
    _folders, _docs, _records, _relations, diagnostics = ctx.scan_and_validate(write_cache=False)
    baseline = {"artifacts": {item: file_hash(ctx.root / item) if (ctx.root / item).is_file() else ""
                              for item in artifacts},
                "diagnostics": sorted(f"{d['code']}:{d['path']}" for d in diagnostics)}
    plan_hash = selection_key([ctx.dataset_id, change_id, title, blocked_by, artifacts, baseline])
    if if_plan_hash is not None and if_plan_hash != plan_hash:
        raise ConflictError("The change plan is stale.", "write.hash_mismatch")
    if apply_:
        open_change(ctx.root, title, blocked_by=blocked_by, artifacts=artifacts,
                    baseline=baseline, history=ctx.history_recorder(change_id))
    _emit_command_result(ctx, {"change_id": change_id, "path": path.relative_to(ctx.root).as_posix(),
                               "status": "proposed", "artifacts": list(artifacts), "baseline": baseline,
                               "plan_hash": plan_hash, "applied": apply_, "preview": not apply_}, output)


@change.command("show", cls=UnifiedCommand)
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
@click.argument("change_id")
def change_show(roots: tuple[str, ...], output: str, no_input: bool, change_id: str) -> None:
    """Запись изменения и её дельты."""
    ctx = _single_context(roots, "change")
    record = load_change(ctx.root, change_id)
    if record is None:
        raise TodocError(f"Изменение не найдено: {change_id}", EXIT_INCOMPLETE, "change.not_found")
    deltas = collect_deltas(ctx.root, change_id)
    _emit_command_result(ctx, {"record": record,
              "deltas": [{"path": d["path"], "target": d["target"], "base_hash": d["base_hash"],
                          "order": d["order"],
                          "ops": [{"op": o["op"], "anchor": o["anchor"]} for o in d["ops"]]}
                         for d in deltas]}, output)


@change.command("validate", cls=UnifiedCommand)
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
@click.argument("change_id")
def change_validate(roots: tuple[str, ...], output: str, no_input: bool, change_id: str) -> None:
    """Применимость дельт к живому состоянию: цель, якорь, base_hash, структура после."""
    ctx = _single_context(roots, "change")
    diagnostics = validate_change(ctx.root, change_id, ctx.dataset_id, _descriptor_lookup(ctx))
    errors = [d for d in diagnostics if d.severity == "error"]
    _emit_command_result(ctx, {"change_id": change_id,
              "applicable": not errors, "errors": len(errors),
              "warnings": len(diagnostics) - len(errors)}, output,
             diagnostics=[d.to_dict() for d in diagnostics])
    if errors:
        raise click.exceptions.Exit(EXIT_VALIDATION)


@change.command("verify", cls=UnifiedCommand)
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
@click.argument("change_id")
def change_verify(roots: tuple[str, ...], output: str, no_input: bool, change_id: str) -> None:
    """Completeness / correctness / coherence — детерминированно, без модели."""
    ctx = _single_context(roots, "change")
    result = verify_change(ctx.root, change_id)
    if not result.get("found"):
        raise TodocError(f"Изменение не найдено: {change_id}", EXIT_INCOMPLETE, "change.not_found")
    _emit_command_result(ctx, result, output)


@change.command("apply", cls=UnifiedCommand)
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
@click.argument("change_id")
@click.option("--preview", is_flag=True)
@click.option("--apply", "apply_", is_flag=True)
@click.option("--if-hash", multiple=True, help="PATH=sha256:… — отказ, если файл ушёл.")
def change_apply(roots: tuple[str, ...], output: str, no_input: bool, change_id: str,
                 preview: bool, apply_: bool, if_hash: tuple[str, ...]) -> None:
    """Bundle-транзакция: без --apply показывает план, с --apply пишет всё или ничего."""
    _check_action_flags(preview, apply_)
    ctx = _single_context(roots, "change")
    expected: dict[str, str] = {}
    for item in if_hash:
        key, _, value = item.partition("=")
        if not value:
            raise TodocError(f"--if-hash ожидает PATH=sha256:…, получено {item!r}",
                             EXIT_USAGE, "usage.error")
        expected[key] = value
    # Рекодер получает change_id: без него события применения не связаны с задачей
    # и `log --change <id>` возвращает пустоту (§2, §5.1).
    result = apply_change(ctx.root, change_id, apply=apply_,
                          history=ctx.history_recorder(change_id),
                          dataset_id=ctx.dataset_id, descriptor_lookup=_descriptor_lookup(ctx),
                          expected_hashes=expected, parse_cache=ctx.parse_cache)
    if result.get("applied"):
        ctx.ensure_index()
    # Диагностики плана обязаны попасть в конверт: без них отказ «applied: false»
    # необъясним, и агент не узнает, что именно мешает применить изменение.
    diagnostics = [d for d in (result.get("diagnostics") or []) if isinstance(d, dict)]
    _emit_command_result(ctx, {k: v for k, v in result.items() if k != "diagnostics"}, output,
                         diagnostics=diagnostics)
    if any(item["severity"] == "error" for item in diagnostics):
        raise click.exceptions.Exit(EXIT_VALIDATION)


@change.command("archive", cls=UnifiedCommand)
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
@click.argument("change_id")
@click.option("--tag", default=None)
@click.option("--preview", is_flag=True)
@click.option("--apply", "apply_", is_flag=True)
@click.option("--if-plan-hash")
def change_archive(roots: tuple[str, ...], output: str, no_input: bool, change_id: str,
                   tag: str | None, preview: bool, apply_: bool, if_plan_hash: str | None) -> None:
    """Показывает план архивации и применяет его по --apply."""
    _check_action_flags(preview, apply_)
    ctx = _single_context(roots, "change")
    record = load_change(ctx.root, change_id)
    if record is None:
        raise IncompleteError(f"Изменение не найдено: {change_id}", "change.not_found")
    scope = record_path(ctx.root, change_id).relative_to(ctx.root).as_posix()
    plan_hash = selection_key([ctx.dataset_id, scope, record, tag])
    if if_plan_hash is not None and if_plan_hash != plan_hash:
        raise ConflictError("The archive plan is stale.", "write.hash_mismatch")
    result = {"change_id": change_id, "status": "archived", "tag": tag, "path": scope}
    if apply_:
        result = archive_change(ctx.root, change_id, tag, ctx.root,
                                history=ctx.history_recorder(change_id), store=ctx.history_store)
    _emit_command_result(ctx, {**result, "preview": not apply_, "applied": apply_, "plan_hash": plan_hash}, output)


@change.command("revert", cls=UnifiedCommand)
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
@click.argument("change_id")
@click.option("--preview", is_flag=True)
@click.option("--apply", "apply_", is_flag=True)
def change_revert(roots: tuple[str, ...], output: str, no_input: bool, change_id: str,
                  preview: bool, apply_: bool) -> None:
    """Откат применения к базовой линии изменения. Без --apply — только план."""
    _check_action_flags(preview, apply_)
    ctx = _single_context(roots, "change")
    result = revert_change(ctx.root, change_id, apply=apply_,
                           history=ctx.history_recorder(change_id), store=ctx.history_store,
                           parse_cache=ctx.parse_cache)
    if result.get("applied"):
        ctx.ensure_index()
    _emit_command_result(ctx, result, output)


@cli.command("context", cls=UnifiedCommand)
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
@click.option("--change", "change_id", default=None)
@click.option("--tag", default=None)
@click.option("--budget", type=click.IntRange(min=1), default=8000, show_default=True)
@click.option("--with-diff", is_flag=True)
def context_cmd(roots: tuple[str, ...], output: str, no_input: bool, change_id: str | None,
                tag: str | None, budget: int, with_diff: bool) -> None:
    """Весь контекст задачи одним вызовом, в пределах бюджета в символах."""
    ctx = _single_context(roots, "change")
    if not change_id and not tag:
        raise TodocError("Нужен --change или --tag", EXIT_USAGE, "usage.error")
    limits = ctx.dataset.get("limits") or {}
    max_diff_lines = limits.get("max_diff_lines")
    result = build_context(ctx.root, ctx.dataset_id, change_id=change_id, tag=tag,
                           budget=budget, with_diff=with_diff, store=ctx.history_store,
                           backend=ctx.history_recorder().backend,
                           max_diff_lines=max_diff_lines if isinstance(max_diff_lines, int) else None)
    if result.get("error"):
        raise IncompleteError(f"Изменение не найдено: {change_id}", result["error"])
    _emit_command_result(ctx, result, output)


def _history_unavailable(status: str, path: str) -> TodocError:
    """Ошибка чтения истории: текст говорит, что именно произошло, код — из списка плана (§8)."""
    if status == "object_missing":
        return TodocError(f"Снимок содержимого для {path} утрачен: нужна пересборка истории",
                          EXIT_INCOMPLETE, "history.object_missing")
    if status == "no_before":
        return TodocError(f"У события нет состояния «до» для {path}: это создание файла или базовая "
                          f"линия — откатывать некуда", EXIT_INCOMPLETE, "history.revision_unknown")
    if status == "unreadable":
        return TodocError(f"Содержимое {path} не читается как текст", EXIT_INCOMPLETE,
                          "history.journal_unreadable")
    return TodocError(f"Содержимое для {path} на этой ревизии недоступно ({status})",
                      EXIT_INCOMPLETE, "history.revision_unknown")


def _write_whole(ctx: DatasetContext, rel_path: str, text: str, expected_hash: str, *,
                 history: Any, basis: str) -> str:
    """Publish a reviewed full-file edit through the same storage path as line edits."""
    digest = "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()
    plan = WritePlan(dataset_id=ctx.dataset_id, target_path=rel_path, new_content=text,
                     expected_hash=expected_hash or None, new_hash=digest, basis=basis)
    return apply_write_plan(ctx.root, plan, history=history, parse_cache=ctx.parse_cache, event_kind="doc.edit")


@cli.command("explain-path", cls=UnifiedCommand)
@click.argument("path")
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
def explain_path(path: str, roots: tuple[str, ...], output: str, no_input: bool) -> None:
    """Show resolved type/rule for a path — документы И папки (с .config.json-метой предка)."""
    path = normalize_scope(path)
    for ctx in _contexts(roots):
        payload = ctx.read_index(sections=("folders",))
        folders, documents = payload["folders"], payload["documents"]
        folder_configs, _cfg_diags = load_folder_configs(ctx.root)

        def _ancestor_fields(p: str) -> dict[str, Any]:
            cur = Path(p)  # папка — с самой себя; документ — с его папки
            while str(cur) != ".":
                fc = folder_configs.get(cur.as_posix())
                if fc:
                    return {"title": fc.title, "description": fc.description, "order": fc.order}
                cur = cur.parent
            return {"title": None, "description": None, "order": None}

        folder_map = {f["path"]: f for f in folders}
        fm = folder_map.get(path)
        if fm is not None:
            _emit_command_result(ctx, {"path": path, "folder": True,
                      "dir_type": fm["dir_type"], "rule_source": fm["rule_source"],
                      **_ancestor_fields(path)}, output)
            return
        for doc in documents:
            if doc["path"] == path:
                _emit_command_result(ctx, {"path": path, "doc_type": doc["doc_type"],
                          "format": doc["format"], "rule_source": doc["rule_source"], "document_id": doc["document_id"],
                          **_ancestor_fields(path)},
                         output)
                return
    raise ValidationError(f"Path not found in dataset: {path}", "explain.path_not_found")


@cli.group()
@click.pass_context
def docs(ctx: click.Context) -> None:
    """Document operations."""


def _slugify(title: str) -> str:
    """Слаг файла из заголовка (BUG-006): транслитерация кириллицы, [a-z0-9-], латиница."""
    lowered = title.strip().lower()
    translit = "".join(TRANSLIT.get(ch, ch) for ch in lowered)
    slug = re.sub(r"[^a-z0-9]+", "-", translit).strip("-")
    return slug or "untitled"


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


@docs.command("new", cls=UnifiedCommand)
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
@click.option("--title", required=True)
@click.option("--dir", "dir_", default="inbox")
@click.option("--path", "path_", default=None, help="Явный относительный путь вместо --dir + slug.")
@click.option("--type", "doc_type", default=None, help="Тип документа: шаблон и структура из папки типа.")
@click.option("--template", default=None, help="Тип документа или путь к файлу шаблона.")
@click.option("--attributes-file", help="JSON object with custom document metadata.")
@click.option("--preview", is_flag=True, help="Show the write plan without creating the file.")
@click.option("--apply", "apply_", is_flag=True)
@click.option("--if-plan-hash")
def docs_new(roots: tuple[str, ...], output: str, no_input: bool, title: str, dir_: str, path_: str | None,
             doc_type: str | None, template: str | None, attributes_file: str | None,
             preview: bool, apply_: bool, if_plan_hash: str | None) -> None:
    """Create a document from its type's starter template (create-only, no-overwrite)."""
    _check_action_flags(preview, apply_)
    ctx = _single_context(roots, "docs")
    slug = _slugify(title)
    rel = path_ or f"{dir_.strip('/')}/{slug}.md"
    target = _contained_out(ctx.root, rel)
    if (ctx.root / rel).is_symlink():
        raise ConflictError(f"Target already exists: {rel}", "docs.target_exists")
    rel = target.relative_to(ctx.root).as_posix()
    if target.exists():
        raise ConflictError(f"Target already exists: {rel}", "docs.target_exists")
    is_json = target.suffix.casefold() == ".json"
    if is_json and not title.strip():
        raise ValidationError("Document title must not be empty", "docs.empty_title")
    type_id, template_text, source = _resolve_document_template(ctx, doc_type, template)
    extra = _load_patch_file(attributes_file) if attributes_file is not None else {}
    if set(extra) & {"id", "title", "doc_type", "created", "updated", "record_id", "entity_type"}:
        raise ValidationError("--attributes-file cannot override generated identity or dates.", "metadata.protected")
    today = _utc_date()
    common = load_metadata_schema(ctx.root)
    typed = _load_schemas(ctx.root, ctx.registry_types, ctx.dataset, "doc_type", _doc_types_of)
    schemas = [(common, SCHEMA_PATH)] if common is not None else []
    if type_id in typed:
        schemas.append(typed[type_id])
    if is_json:
        metadata = {"id": f"doc:{rel}", "title": title, "lang": "ru", "created": today, "updated": today}
        if type_id is not None:
            metadata["doc_type"] = type_id
        metadata.update(extra)
        body: Any = {}
        if template is not None and template not in ctx.registry_types.doc_types:
            body, errors = parse_json(template_text or "")
            if errors:
                raise ValidationError("The JSON document template must contain valid JSON.", "types.template_invalid")
        content = json.dumps({"meta": metadata, "body": body}, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
        plan = WritePlan(dataset_id=ctx.dataset_id, target_path=rel, new_content=content,
                         expected_hash=None, new_hash="sha256:" + hashlib.sha256(content.encode("utf-8")).hexdigest(),
                         basis="Create JSON document")
    else:
        values = {"title": title, "slug": slug, "date": today, "type_id": type_id or "",
                  "id": f"doc:{rel}", "format": "markdown"}
        plan = create_document_plan(ctx.dataset, ctx.registry_types.doc_types, type_id, title, rel,
                                    template_text, values)
        original = parse_markdown(plan.new_content).front_matter
        metadata = normalize_markdown_attributes(original, schemas)
        if extra:
            metadata.update(extra)
            content = rewrite_markdown_attributes(plan.new_content, original, metadata)
            if normalize_markdown_attributes(parse_markdown(content).front_matter, schemas) != metadata:
                raise ValidationError("Some attributes cannot be represented in Markdown.", "metadata.invalid_patch")
            plan = replace(plan, new_content=content,
                           new_hash="sha256:" + hashlib.sha256(content.encode("utf-8")).hexdigest())
    descriptor = ctx.registry_types.doc_types.get(type_id, {})
    statuses = descriptor.get("allowed_statuses") or []
    if "status" in metadata and statuses and metadata["status"] not in statuses:
        raise ValidationError(f"status must be one of {statuses}.", "docs.status_not_allowed")
    findings = [f"{pointer}: {message}" for schema, _ in schemas
                for pointer, message in metadata_errors(metadata, schema, "/meta" if is_json else "")]
    if findings:
        raise ValidationError("; ".join(findings), "document.schema_violation")
    if extra and common is None:
        issues = _check_meta_fields(ctx.dataset_id, rel, metadata)
        if issues:
            raise ValidationError(issues[0].message, issues[0].code)
    plan_hash = selection_key([ctx.dataset_id, plan.to_dict()])
    if if_plan_hash is not None and if_plan_hash != plan_hash:
        raise ConflictError("The document creation plan is stale.", "write.hash_mismatch")
    if not apply_:
        _emit_command_result(ctx, {"plan": plan.preview_dict(), "plan_hash": plan_hash,
                                   "preview": True, "applied": False, "attributes": metadata}, output)
        return
    apply_write_plan(ctx.root, plan, history=ctx.history_recorder(), parse_cache=ctx.parse_cache)
    ctx.ensure_index()
    _emit_command_result(ctx, {"path": rel, "title": title, "doc_type": type_id, "template": source,
                               "hash": plan.new_hash, "applied": True, "plan_hash": plan_hash}, output,
                         next_actions=[{"argv": _root_argv(roots) + ["docs", "read", "--id", f"doc:{rel}"],
                                        "purpose": "Прочитать созданный документ"},
                                       {"argv": _root_argv(roots) + ["types", "prompt", type_id or "note", "--op", "edit"],
                                        "purpose": "Взять стартовый промпт правки для этого типа"}])


@docs.command("list", cls=AttributeFilterCommand)
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json")
@click.option("--no-input", is_flag=True)
@click.option("--type", "types", multiple=True, help="Effective document type; separate alternatives by |.")
@click.option("--within", default=".")
@click.option("--tag")
@click.option("--tag-in", multiple=True, help="Match at least one tag, separated by |.")
@click.option("--tag-all", multiple=True, help="Match every tag, separated by |.")
@click.option("--file-format", type=click.Choice(["markdown", "json", "csv", "opaque"]))
@click.option("--attribute", "attributes", type=(str, str), multiple=True, hidden=True)
@click.option("--filter-file", type=click.Path(dir_okay=False, path_type=Path))
@click.option("--filter-fields", is_flag=True, help="List declared and observed metadata fields in this scope.")
@click.option("--status", "statuses", multiple=True)
@click.option("--status-missing", is_flag=True)
@click.option("--origin", type=click.Choice(["document", "record"]),
              help="Authored documents or JSON mirrors under records/.")
@click.option("--fields", "include")
@click.option("--exclude-fields", "exclude")
@click.option("--fields-help", is_flag=True)
@click.option("--view", default="flat")
@click.option("--limit", type=click.IntRange(1, 1000), default=50, show_default=True)
@click.option("--cursor")
def docs_list(roots: tuple[str, ...], output: str, no_input: bool,
              types: tuple[str, ...], within: str, tag: str | None, tag_in: tuple[str, ...],
              tag_all: tuple[str, ...], file_format: str | None,
              attributes: tuple[tuple[str, str], ...], filter_file: Path | None,
              filter_fields: bool, statuses: tuple[str, ...], status_missing: bool,
              origin: str | None,
              include: str | None, exclude: str | None, fields_help: bool,
              view: str, limit: int, cursor: str | None) -> None:
    """List current document metadata. Filter with --attr-NAME 'value1|value2'."""
    meta = _collection_meta()
    if fields_help:
        emit(Envelope(
            True, {"meta": {"command": "docs list", "scope": None}, "executed": False,
                   "result": {"fields": DOCUMENT_LIST_FIELDS + ("attributes",),
                              "structural": ["id", "path"]}},
            schema_version=2, guidance={"profile": "ru", "mode": "compact", "items": []},
        ), output)
        return
    meta["requested_view"] = view
    try:
        within = normalize_scope(within)
        allowed = DOCUMENT_LIST_FIELDS + ("attributes",)
        fields = selected_fields(allowed, include, exclude, structural=("id", "path"))
        if include is None:
            fields = tuple(field for field in fields if field != "attributes")
        doc_types = split_values(types)
        any_tags = split_values(part.casefold() for part in tag_in)
        all_tags = split_values(part.casefold() for part in tag_all)
        resolved = resolve_roots(_effective_roots(roots))
        if len(resolved) != 1:
            raise TodocError("Choose exactly one DATA_ROOT.", EXIT_USAGE, "docs.multiple_roots")
        ctx = DatasetContext(resolved[0])
        meta["scope"] = {"dataset_id": ctx.dataset_id, "within": within}
        payload = ctx.read_index(sections=())
        known_types = set(ctx.registry_types.doc_types) | {"unknown"}
        known_types.update(doc["doc_type"] for doc in payload["documents"])
        unknown_types = sorted(set(doc_types) - known_types)
        if unknown_types:
            raise TodocError(
                f"Unknown document types: {', '.join(unknown_types)}. See types list.",
                EXIT_USAGE, "docs.unknown_type")
        known_statuses = {status for descriptor in ctx.registry_types.doc_types.values()
                          for status in (descriptor.get("allowed_statuses") or [])}
        known_statuses.update(doc.get("lifecycle_status") for doc in payload["documents"]
                              if doc.get("lifecycle_status"))
        unknown_statuses = sorted(set(statuses) - known_statuses)
        if unknown_statuses:
            raise TodocError(
                f"Unknown document statuses: {', '.join(unknown_statuses)}.",
                EXIT_USAGE, "docs.unknown_status")
        if failures := _document_read_failures(payload, within):
            emit(Envelope.collection(meta, [], diagnostics=failures), output)
            raise click.exceptions.Exit(EXIT_INCOMPLETE)
        declared = _document_filter_fields(ctx, doc_types)
        if filter_fields:
            candidates = matching_documents(payload["documents"], within, doc_types, file_format)
            observed = {key for doc in candidates for key in doc["attributes"] if isinstance(key, str)}
            emit(Envelope(True, {"meta": meta, "executed": False,
                                 "result": {"fields": sorted(observed | declared.keys()),
                                            "operators": OPERATORS, "declared": declared}},
                          schema_version=2, guidance=guidance_for([])), output)
            return
        items, total, next_cursor = list_documents(
            payload, types=doc_types, within=within, tag=tag, any_tags=any_tags, all_tags=all_tags,
            file_format=file_format, statuses=statuses, status_missing=status_missing,
            attributes=attributes, filter_file=filter_file, declared=declared, limit=limit, cursor=cursor,
            origin=origin,
        )
    except TodocError as exc:
        _emit_collection_error(meta, exc.code, exc.message, output)
        raise click.exceptions.Exit(exc.exit_code) from exc
    meta.update(complete=True, total=total, returned=len(items),
                truncated=next_cursor is not None, next_cursor=next_cursor)
    diagnostics = []
    if view != "flat":
        diagnostics.append({"code": "view.fallback", "severity": "info", "path": "",
                            "message": "The available view for docs list is flat."})
    emit(Envelope.collection(meta, [project_fields(item, fields) for item in items],
                             diagnostics=diagnostics), output)


def _document_read_failures(payload: dict[str, Any], within: str) -> list[dict[str, Any]]:
    codes = {"file.unsupported", "file.permission_denied", "file.unreadable",
             "markdown.front_matter.yaml_unsafe"}
    return [
        {**item, "severity": "error"} for item in payload["diagnostics"]
        if item["code"] in codes
        and (within == "." or item["path"] == within or item["path"].startswith(within + "/"))
    ]


def _document_filter_fields(ctx: DatasetContext, types: tuple[str, ...]) -> dict[str, Any]:
    fields = {key: {"type": "string"} for key in ("id", "title", "doc_type", "lang", "status")}
    fields.update({key: {"type": "string", "format": "date"} for key in ("created", "updated")})
    fields.update({key: {"type": "array", "items": {"type": "string"}} for key in ("tags", "related")})
    schemas = _load_schemas(ctx.root, ctx.registry_types, ctx.dataset, "doc_type", _doc_types_of)
    for type_id in types or tuple(schemas):
        if type_id in schemas:
            fields.update(schemas[type_id][0].get("properties", {}))
    common = load_metadata_schema(ctx.root)
    if common is not None:
        fields.update(common.get("properties", {}))
    return fields


def _collection_meta(command: str = "docs list", view: str = "flat") -> dict[str, Any]:
    return {
        "command": command, "scope": None, "requested_view": view, "actual_view": view,
        "complete": False, "total": None, "returned": 0, "truncated": False, "next_cursor": None,
    }


def _emit_flat_page(meta: dict[str, Any], items: list[dict[str, Any]], selection: list[Any],
                    fields: tuple[str, ...], limit: int, cursor: str | None, output: str) -> None:
    if limit == 0:
        if cursor is not None:
            raise TodocError("A count-only request does not accept a cursor.", EXIT_USAGE, "cursor.invalid")
        rows, next_cursor = [], None
    else:
        rows, next_cursor = page(items, selection, limit, cursor)
    meta.update(complete=True, total=len(items), returned=len(rows),
                truncated=next_cursor is not None or (limit == 0 and bool(items)), next_cursor=next_cursor)
    emit(Envelope.collection(meta, [project_fields(row, fields) for row in rows],
                            diagnostics=_view_diagnostics(meta)), output)


def _view_diagnostics(meta: dict[str, Any]) -> list[dict[str, Any]]:
    requested, actual = meta["requested_view"], meta["actual_view"]
    if requested == actual:
        return []
    return [{"code": "view.fallback", "severity": "info", "path": "",
             "message": f"View {requested!r} is unavailable. Returned {actual} output."}]


def _emit_collection_error(meta: dict[str, Any], code: str, message: str, output: str) -> None:
    envelope = Envelope.collection(meta, [], diagnostics=[
        {"code": code, "severity": "error", "message": message, "path": ""}
    ])
    command = meta["command"]
    envelope.next_actions = [{"argv": ["todoc", *command.split(), "--help"], "purpose": command}]
    emit(envelope, output)


_SEARCH_FIELDS = ("id", "path", "title", "doc_type", "status", "heading_path", "rank", "relevance",
                  "matched_terms", "snippet")


def _search_items_bytes(items: list[dict[str, Any]]) -> int:
    """UTF-8 bytes of the serialized result items (envelope excluded)."""
    if not items:
        return 0
    return len(json.dumps(items, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def _trim_first_search_item(item: dict[str, Any], budget: int) -> dict[str, Any] | None:
    """Largest snippet prefix whose item still fits ``budget``; ``None`` if even metadata does not."""
    snippet = item.get("snippet")
    if not isinstance(snippet, dict):
        return None
    text = str(snippet.get("text") or "")
    trial = {**item, "snippet": {**snippet, "text": "", "snippet_truncated": True}}
    if _search_items_bytes([trial]) > budget:
        return None
    best = trial
    low, high = 0, len(text)
    while low <= high:
        middle = (low + high) // 2
        candidate = {**trial, "snippet": {**trial["snippet"], "text": text[:middle]}}
        if _search_items_bytes([candidate]) <= budget:
            best = candidate
            low = middle + 1
        else:
            high = middle - 1
    return best


def _fit_search_items(items: list[dict[str, Any]], budget: int) -> tuple[list[dict[str, Any]], int, bool]:
    """Keep the highest-ranked hits that fit; trim only the first one when it alone overflows."""
    kept: list[dict[str, Any]] = []
    for item in items:
        candidate = [*kept, item]
        if _search_items_bytes(candidate) <= budget:
            kept = candidate
            continue
        if not kept:
            trimmed = _trim_first_search_item(item, budget)
            if trimmed is not None:
                kept = [trimmed]
        break
    used = _search_items_bytes(kept)
    return kept, used, used != _search_items_bytes(items)


@docs.command("search", cls=AttributeFilterCommand)
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
@click.option("--type", "types", multiple=True, help="Effective document type; separate alternatives by |.")
@click.option("--query")
@click.option("--budget", type=click.IntRange(min=1),
              help="Maximum UTF-8 bytes of the serialized result items (envelope excluded).")
@click.option("--limit", type=click.IntRange(1, 1000), default=10)
@click.option("--within", default=".")
@click.option("--cursor")
@click.option("--tag", help="Match one exact tag.")
@click.option("--tag-in", multiple=True, help="Match at least one tag, separated by |.")
@click.option("--tag-all", multiple=True, help="Match every tag, separated by |.")
@click.option("--file-format", type=click.Choice(["markdown", "json", "csv", "opaque"]))
@click.option("--attribute", "attributes", type=(str, str), multiple=True, hidden=True)
@click.option("--filter-file", type=click.Path(dir_okay=False, path_type=Path))
@click.option("--fields", "include")
@click.option("--exclude-fields", "exclude")
@click.option("--view", default="flat")
def docs_search(roots: tuple[str, ...], output: str, no_input: bool, types: tuple[str, ...], query: str | None,
                budget: int | None, limit: int, within: str, cursor: str | None,
                tag: str | None, tag_in: tuple[str, ...], tag_all: tuple[str, ...], file_format: str | None,
                attributes: tuple[tuple[str, str], ...], filter_file: Path | None,
                include: str | None, exclude: str | None, view: str) -> None:
    """Search document text or apply metadata filters with --attr-NAME 'value1|value2'."""
    meta = _collection_meta("docs search", view)
    meta["actual_view"] = "flat"
    budget_meta: dict[str, Any] | None = None
    if query is None and not any((types, tag, tag_in, tag_all, file_format, attributes, filter_file, within != ".")):
        emit(Envelope(True, {
            "meta": meta, "executed": False,
            "result": {"input": "Pass --query or a metadata filter.", "fields": _SEARCH_FIELDS},
        }, schema_version=2, guidance=guidance_for([])), output)
        return
    try:
        if query is not None and not query.strip():
            raise TodocError("--query must not be empty.", EXIT_USAGE, "usage.error")
        scope = normalize_scope(within)
        fields = selected_fields(_SEARCH_FIELDS, include, exclude, structural=("id", "path"))
        doc_types = split_values(types)
        any_tags = split_values(part.casefold() for part in tag_in)
        all_tags = split_values(part.casefold() for part in tag_all)
        resolved = resolve_roots(_effective_roots(roots))
        if len(resolved) != 1:
            raise TodocError("Choose exactly one DATA_ROOT.", EXIT_USAGE, "docs.multiple_roots")
        ctx = DatasetContext(resolved[0])
        meta["scope"] = {"dataset_id": ctx.dataset_id, "within": scope}
        payload = ctx.read_index(sections=())
        if failures := _document_read_failures(payload, scope):
            emit(Envelope.collection(meta, [], diagnostics=failures), output)
            raise click.exceptions.Exit(EXIT_INCOMPLETE)
        candidates = matching_documents(payload["documents"], scope, doc_types, file_format)
        candidates, conditions = select_document_attributes(
            candidates, _document_filter_fields(ctx, doc_types), attributes, filter_file, tag, any_tags, all_tags,
        )
        metadata = {doc["document_id"]: doc for doc in candidates}
        selection = [2, "docs search", ctx.dataset_id, payload["corpus_digest"], scope,
                     doc_types, file_format, tag, any_tags, all_tags, conditions, query]
        if query is None:
            candidates.sort(key=lambda doc: (doc["path"], doc["document_id"]))
            selected, next_cursor = page(candidates, selection, limit, cursor)
            total = len(candidates)
            items = [
                {"id": doc["document_id"], "path": doc["path"], "title": doc["title"],
                 "doc_type": doc["doc_type"], "status": doc.get("lifecycle_status")}
                for doc in selected
            ]
        else:
            key = selection_key(selection)
            offset = cursor_offset(cursor, key)
            searchable = [doc for doc in candidates if doc["format"] != "opaque"]
            hits, total, _ = search_documents(ctx.root, searchable, query, limit=limit, budget=None,
                                             offset=offset, verify_sources=True)
            if cursor is not None and offset >= total:
                raise TodocError("Cursor is outside this selection.", EXIT_USAGE, "cursor.invalid")
            items = []
            for hit in hits:
                doc = metadata.get(hit.id, {})
                items.append({**hit.to_dict(), "doc_type": doc.get("doc_type"),
                              "status": doc.get("lifecycle_status")})
            next_cursor = next_page_cursor(key, offset + len(items), total)
            if budget is not None:
                items, used_bytes, exhausted = _fit_search_items(items, budget)
                budget_meta = {"limit": budget, "used_bytes": used_bytes, "exhausted": exhausted}
                if exhausted:
                    next_cursor = (next_page_cursor(key, offset + len(items), total)
                                   if items else None)
    except TodocError as exc:
        _emit_collection_error(meta, exc.code, exc.message, output)
        raise click.exceptions.Exit(exc.exit_code) from exc
    meta.update(complete=True, total=total, returned=len(items),
                truncated=next_cursor is not None or bool(budget_meta and budget_meta["exhausted"]),
                next_cursor=next_cursor)
    if budget_meta is not None:
        meta["budget"] = budget_meta
    diagnostics = []
    if view != "flat":
        diagnostics.append({"code": "view.fallback", "severity": "info", "path": "",
                            "message": "The available view for docs search is flat."})
    response = Envelope.collection(meta, [project_fields(item, fields) for item in items],
                                   diagnostics=diagnostics)
    if items:
        first_id = items[0]["id"]
        if sum(doc["document_id"] == first_id for doc in payload["documents"]) == 1:
            response.next_actions = [
                {"argv": _root_argv(roots) + ["docs", "read", "--id", first_id, "--output", "json"],
                 "purpose": "Прочитать выбранный документ"}
            ]
    emit(response, output)


@docs.command("read", cls=UnifiedCommand)
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
@click.option("--id", "doc_id")
@click.option("--section", default=None)
@click.option("--anchor", default=None)
@click.option("--line-range", default=None)
@click.option("--pointer", default=None)
@click.option("--columns", default=None)
@click.option("--rows", type=click.IntRange(min=1), default=None)
@click.option("--where", default=None)
@click.option("--budget", type=click.IntRange(min=1), default=None,
              help="Maximum number of Unicode characters of text content.")
@click.option("--fields", "include")
@click.option("--exclude-fields", "exclude")
def docs_read(roots: tuple[str, ...], output: str, no_input: bool, doc_id: str | None, section: str | None,
              anchor: str | None, line_range: str | None, pointer: str | None, columns: str | None,
              rows: int | None, where: str | None, budget: int | None,
              include: str | None, exclude: str | None) -> None:
    """Bounded projection read (section/pointer/columns)."""
    meta = {"command": "docs read", "scope": None}
    if doc_id is None:
        emit(Envelope(True, {"meta": meta, "executed": False, "result": {"input": "Pass --id."}},
                      schema_version=2, guidance=guidance_for([])), output)
        return
    resolved = resolve_roots(_effective_roots(roots))
    if len(resolved) != 1:
        raise TodocError("Choose exactly one DATA_ROOT.", EXIT_USAGE, "docs.multiple_roots")
    ctx = DatasetContext(resolved[0])
    payload = ctx.read_index(sections=())
    # план entity-catalog З3/T5: fragment в id — синоним --section; конфликт — usage.error
    id_base, hash_sep, id_fragment = doc_id.partition("#")
    if hash_sep and section:
        raise TodocError("Фрагмент в --id и --section одновременно.", EXIT_USAGE, "usage.error")
    if hash_sep:
        doc_id, section = id_base, id_fragment
    matches = [item for item in payload["documents"] if item["document_id"] == doc_id]
    if not matches:
        raise ValidationError(f"Document not found: {doc_id}", "docs.not_found")
    if len(matches) != 1:
        raise ValidationError(f"Multiple documents share {doc_id!r}.", "docs.ambiguous_id")
    doc = matches[0]
    text = read_verified_text(ctx.root, doc["path"], doc["hash"])
    data: dict[str, Any] = {"dataset_id": ctx.dataset_id, "id": doc_id, "path": doc["path"],
                            "format": doc["format"], "doc_type": doc["doc_type"], "hash": doc["hash"]}
    if budget is not None and doc["format"] in ("json", "csv"):
        raise TodocError("--budget applies to text projections. Use --pointer or --rows for structured data.",
                         EXIT_USAGE, "docs.budget_not_applicable")
    markdown_selections = sum(value is not None for value in (section, anchor, line_range))
    csv_selection = any(value is not None for value in (columns, rows, where))
    if (markdown_selections > 1 or (markdown_selections and doc["format"] != "markdown")
            or (pointer is not None and doc["format"] != "json") or (csv_selection and doc["format"] != "csv")):
        raise TodocError("Use one selector supported by the file format.", EXIT_USAGE, "docs.invalid_selector")
    if doc["format"] == "markdown":
        md = parse_markdown(text)
        fm = md.front_matter
        data["tags"] = fm.get("tags")
        data["updated"] = fm.get("updated")
        data["related"] = fm.get("related")  # план doc-tags З2: meta-поля в read-выводе
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
            section_text = "\n".join(section_lines)
            if budget is not None:
                excerpt = section_text[:budget]
                window = excerpt.split("\n")
            else:
                window = section_lines[:SECTION_MAX_LINES]
                excerpt = "\n".join(window)
            data["section"] = selected.title
            data["heading_path"] = heading_path_for(md.headings, selected_index)
            data["line_start"] = selected.line
            data["line_end"] = selected.line + len(window) - 1
            data["lines"] = window
            data["section_total_lines"] = len(section_lines)
            data["truncated"] = len(excerpt) < len(section_text)
            data["text"] = excerpt
        elif line_range:
            start, end = _parse_line_range(line_range)
            lines = text.splitlines()
            _check_line_start(start, len(lines), line_range)
            selected_lines = lines[start - 1:end]
            requested_text = "\n".join(selected_lines)
            excerpt = requested_text[:budget]
            data["lines"] = excerpt.split("\n") if selected_lines else []
            data["text"] = excerpt
            data["line_start"] = start
            data["line_end"] = start + len(data["lines"]) - 1
            data["line_total"] = len(lines)
            data["truncated"] = len(excerpt) < len(requested_text)
        else:
            data["title"] = md.title
            data["headings"] = [{"title": h.title, "level": h.level, "line": h.line, "anchor": h.anchor} for h in md.headings]
            data["text"] = text[: budget or 4000]
            data["truncated"] = len(data["text"]) < len(text)
    elif doc["format"] == "json":
        value, errors = parse_json(text)
        if errors:
            raise ValidationError(f"Cannot project invalid JSON: {errors[0]}", "docs.invalid_json")
        if pointer:
            try:
                data["value"] = resolve_pointer(value, pointer)
            except (KeyError, IndexError, ValueError) as exc:
                raise ValidationError(f"Pointer not found: {pointer}: {exc}", "docs.pointer_not_found") from exc
        else:
            data["value"] = value
    elif doc["format"] == "csv":
        csv_doc = parse_csv(text)
        if csv_doc.errors:
            raise ValidationError(f"Cannot project invalid CSV: {csv_doc.errors[0]}", "docs.invalid_csv")
        cols = [c.strip() for c in columns.split(",")] if columns else csv_doc.headers
        if set(cols) - set(csv_doc.headers):
            raise TodocError("Unknown CSV column.", EXIT_USAGE, "docs.invalid_selector")
        # Сначала отбор, потом окно: --rows 3 --where k=v должен вернуть три
        # подходящие строки, а не три первые с последующей фильтрацией (P1-5).
        selected_rows = csv_doc.rows
        if where:
            key, equals, val = where.partition("=")
            if not equals or key.strip() not in csv_doc.headers:
                raise TodocError("--where expects a valid COLUMN=VALUE.", EXIT_USAGE, "docs.invalid_selector")
            selected_rows = [r for r in selected_rows if str(r.get(key.strip(), "")) == val.strip()]
        matched = len(selected_rows)
        if rows is not None:
            selected_rows = selected_rows[:rows]
        data["columns"] = cols
        data["rows"] = [{c: r.get(c, "") for c in cols} for r in selected_rows]
        data["total"] = len(csv_doc.rows)
        data["matched"] = matched
        data["truncated"] = matched > len(selected_rows)
    else:
        data["text"] = text[: budget or 4000]
        data["truncated"] = len(data["text"]) < len(text)
    provenance = ("dataset_id", "id", "path", "format", "doc_type", "hash",
                  "section", "heading_path", "line_start", "line_end", "section_total_lines", "truncated")
    if include is not None and doc["format"] in ("markdown", "json"):
        data["attributes"] = doc["attributes"]
    fields = selected_fields(tuple(data), include, exclude, structural=provenance)
    meta.update(scope={"dataset_id": ctx.dataset_id, "path": doc["path"]})
    emit(Envelope.result(meta, project_fields(data, fields)), output)


@docs.command("suggest", cls=UnifiedCommand)
@click.option("--root", "roots", multiple=True)
@click.option("--query", "q", help="Search for a place to file or find documents.")
@click.option("--limit", type=click.IntRange(1, 1000), default=5)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json")
@click.option("--no-input", is_flag=True)
@click.option("--within", default=".")
@click.option("--fields", "include")
@click.option("--exclude-fields", "exclude")
@click.option("--cursor")
def docs_suggest(roots: tuple[str, ...], q: str | None, limit: int, output: str, no_input: bool,
                 within: str, include: str | None, exclude: str | None, cursor: str | None) -> None:
    """Rank folders using their declared titles, tags and aliases."""
    meta = _collection_meta("docs suggest")
    if q is None:
        emit(Envelope(True, {"meta": meta, "executed": False, "result": {"input": "Pass --query."}},
                      schema_version=2, guidance=guidance_for([])), output)
        return
    if not q.strip():
        raise TodocError("Пустой запрос: укажите --query.", EXIT_USAGE, "usage.error")
    ctx = _single_context(roots, "docs")
    scope = normalize_scope(within)
    meta["scope"] = {"dataset_id": ctx.dataset_id, "within": scope}
    folder_configs, findings = load_folder_configs(ctx.root)
    related = {key: config for key, config in folder_configs.items()
               if scope == "." or key == scope or key.startswith(scope + "/")}
    if findings:
        errors = [{**finding, "severity": "error"} for finding in findings]
        emit(Envelope.collection(meta, [], diagnostics=errors), output)
        raise click.exceptions.Exit(EXIT_INCOMPLETE)
    candidates, discarded = score_folder_configs(related, q)
    fields = selected_fields(("path", "title", "description", "score", "reason", "order"),
                             include, exclude, structural=("path",))
    selected, next_cursor = page(candidates, [2, "docs suggest", ctx.dataset_id, scope, q, candidates, discarded],
                                 limit, cursor)
    meta.update(complete=True, total=len(candidates), returned=len(selected), truncated=next_cursor is not None,
                next_cursor=next_cursor, query=q, threshold=0.25, discarded_total=len(discarded))
    response = Envelope.result(meta, {"items": [project_fields(row, fields) for row in selected],
                                      "discarded": discarded[:50]})
    if selected:
        response.next_actions = [
            {"argv": _root_argv(roots) + ["explain-path", selected[0]["path"]],
             "purpose": "Объяснить выбранную папку"}
        ]
    emit(response, output)


@docs.command("links", cls=UnifiedCommand)
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json")
@click.option("--limit", type=click.IntRange(1, 1000), default=20)
@click.option("--no-input", is_flag=True)
@click.option("--within", default=".")
@click.option("--cursor")
@click.option("--fields", "include")
@click.option("--exclude-fields", "exclude")
def docs_links(roots: tuple[str, ...], output: str, no_input: bool, limit: int, within: str,
               cursor: str | None, include: str | None, exclude: str | None) -> None:
    """Audit broken local Markdown links with source coordinates."""
    meta = _collection_meta("docs links")
    try:
        ctx = _single_context(roots, "docs")
        scope = normalize_scope(within)
        meta["scope"] = {"dataset_id": ctx.dataset_id, "within": scope}
        fields = selected_fields(("source", "target", "kind", "line", "column"), include, exclude,
                                 structural=("source", "line", "column"))
        payload = ctx.read_index(sections=("records",))
        if failures := _document_read_failures(payload, scope):
            emit(Envelope.collection(meta, [], diagnostics=failures), output)
            raise click.exceptions.Exit(EXIT_INCOMPLETE)
        documents = payload["documents"]
        paths = {doc["path"] for doc in documents}
        record_ids = {record["record_id"] for record in payload["records"]}
        by_basename, _ = _basename_index(paths)
        total_links = 0
        broken = []
        for doc in matching_documents(documents, scope, (), "markdown"):
            source = doc["path"]
            text = read_verified_text(ctx.root, source, doc["hash"])
            for link in parse_markdown(text).links:
                if link.is_wikilink:
                    if not link.target:
                        continue
                    kind = "wikilink"
                    exists = link.target in record_ids or bool(_wikilink_candidates(link.target, by_basename))
                else:
                    target = resolve_link_target(source, link.target)
                    if target is None:
                        continue
                    kind = "md"
                    exists = target in paths
                total_links += 1
                if not exists:
                    broken.append({"source": source, "target": link.target, "kind": kind,
                                   "line": link.line, "column": link.column})
        selected, next_cursor = page(broken, [2, "docs links", ctx.dataset_id, payload["corpus_digest"], scope],
                                     limit, cursor)
    except TodocError as exc:
        _emit_collection_error(meta, exc.code, exc.message, output)
        raise click.exceptions.Exit(exc.exit_code) from exc
    meta.update(complete=True, total=len(broken), total_links=total_links, returned=len(selected),
                truncated=next_cursor is not None, next_cursor=next_cursor)
    emit(Envelope.collection(meta, [project_fields(item, fields) for item in selected]), output)


@docs.command("tree", cls=UnifiedCommand)
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json")
@click.option("--no-input", is_flag=True)
@click.option("--within", default=None)
@click.option("--depth", "--max-depth", "max_depth", type=click.IntRange(min=0), default=3)
@click.option("--limit", type=click.IntRange(1, 1000), default=50)
@click.option("--cursor")
@click.option("--view", default="tree")
@click.option("--fields", "include")
@click.option("--exclude-fields", "exclude")
@click.option("--match", "match_q", default=None,
              help="Фильтр папок Фазой A скоринга (.config.json): score ≥ 0.25, порядок score → order → путь.")
def docs_tree(roots: tuple[str, ...], output: str, no_input: bool, within: str | None,
              max_depth: int, limit: int, cursor: str | None, match_q: str | None,
              view: str, include: str | None, exclude: str | None) -> None:
    """Compact derived outline (folders + documents)."""
    meta = _collection_meta("docs tree", view)
    actual_view = view if view in ("tree", "flat") else "tree"
    meta["actual_view"] = actual_view
    try:
        scope = normalize_scope(within or ".")
        fields = selected_fields(
            ("id", "path", "kind", "title", "description", "order", "dir_type", "doc_type",
             "format", "status", "parse_status", "tags", "updated", "hash"),
            include, exclude, structural=("id", "path", "kind"),
        )
        resolved = resolve_roots(_effective_roots(roots))
        if len(resolved) != 1:
            raise TodocError("Choose exactly one DATA_ROOT.", EXIT_USAGE, "docs.multiple_roots")
        ctx = DatasetContext(resolved[0])
        meta["scope"] = {"dataset_id": ctx.dataset_id, "within": scope}
        items, cfg_diags, digest = _tree_items(ctx, scope, max_depth, match_q)
        if any(diagnostic["severity"] == "error" for diagnostic in cfg_diags):
            emit(Envelope.collection(meta, [], diagnostics=cfg_diags), output)
            raise click.exceptions.Exit(EXIT_INCOMPLETE)
        rows, next_cursor = page(
            items, [2, "docs tree", ctx.dataset_id, digest, scope, max_depth, match_q, items, cfg_diags],
            limit, cursor,
        )
    except TodocError as exc:
        _emit_collection_error(meta, exc.code, exc.message, output)
        raise click.exceptions.Exit(exc.exit_code) from exc
    meta.update(complete=True, total=len(items), returned=len(rows), truncated=next_cursor is not None,
                next_cursor=next_cursor, max_depth=max_depth)
    if actual_view != view:
        cfg_diags.append({"code": "view.fallback", "severity": "info", "path": "",
                          "message": "The available views for docs tree are tree and flat."})
    projected = [project_fields(row, fields) for row in rows]
    result = {"items": projected} if actual_view == "flat" else {"root": folder_tree(scope, projected)}
    emit(Envelope.result(meta, result, diagnostics=cfg_diags), output)


def _tree_items(ctx: DatasetContext, scope: str, depth: int, match_q: str | None
                ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str]:
    payload = ctx.read_index(sections=("folders",))
    folders = [dict(f) for f in payload["folders"] if within_depth(f["path"], scope, depth)]
    documents = [d for d in payload["documents"] if within_depth(d["path"], scope, depth)]
    folder_configs, cfg_diags = load_folder_configs(ctx.root)
    for f in folders:  # плоские поля из .config.json ближайшего СВОЕГО конфига (null без него)
        fc = folder_configs.get(f["path"])
        f["title"] = fc.title if fc else None
        f["description"] = fc.description if fc else None
        f["order"] = fc.order if fc else None
    if match_q:
        candidates, _discarded = score_folder_configs(folder_configs, match_q)
        rank = {c["path"]: i for i, c in enumerate(candidates)}
        folders = [f for f in folders if f["path"] in rank]
        folders.sort(key=lambda f: rank[f["path"]])
    items = [{"id": f["folder_id"], "kind": "folder", **f} for f in folders]
    items.extend({
        **d, "id": d["document_id"], "kind": "document", "parse_status": d["status"],
        "status": d.get("lifecycle_status"),
    } for d in documents)
    return items, cfg_diags + _document_read_failures(payload, scope), payload["corpus_digest"]


_FLOW_SECTIONS = ("state", "table", "mermaid", "lineage", "terms")
# План entity-catalog З8: фрагменты записи flow, по которым --write ставит якоря
# derived_from (дрейф ловит `todoc stale`); отсутствующие в записи пропускаются.
_FLOW_ANCHOR_POINTERS = ("/states", "/outcomes", "/tree", "/relations")


def _flow_record(payload: dict[str, Any], ctx: DatasetContext, flow_id: str) -> dict[str, Any]:
    rec = next((r for r in payload["records"]
                if r.get("record_id") == flow_id and r.get("entity_type") == "flow"), None)
    if rec is None:
        raise ValidationError(f"Flow not found: {flow_id}", "docs.flow_not_found")
    del ctx
    return rec


def _typed_records(payload: dict[str, Any], entity_type: str) -> list[dict[str, Any]]:
    return [r["data"] for r in payload["records"]
            if r.get("entity_type") == entity_type and isinstance(r.get("data"), dict)]


@docs.group("flow")
def docs_flow() -> None:
    """Витрина и навигатор дерева решений флоу (entity-catalog T1/T2)."""


@docs_flow.command("render", cls=UnifiedCommand)
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
@click.option("--id", "flow_id", required=True)
@click.option("--section", type=click.Choice(_FLOW_SECTIONS), default=None,
              help="Одна секция витрины вместо полного markdown.")
@click.option("--write", "write_path", default=None, help="Материализовать витрину в файл (fm derived_from).")
@click.option("--preview", is_flag=True)
@click.option("--apply", "apply_", is_flag=True)
@click.option("--if-plan-hash")
def docs_flow_render(roots: tuple[str, ...], output: str, no_input: bool, flow_id: str,
                     section: str | None, write_path: str | None, preview: bool, apply_: bool,
                     if_plan_hash: str | None) -> None:
    """Витрина флоу из записи: state machine, таблица решений (Режим), mermaid, lineage, термины."""
    del no_input
    _check_action_flags(preview, apply_)
    if apply_ and not write_path:
        raise TodocError("--apply requires --write.", EXIT_USAGE, "usage.error")
    ctx = _single_context(roots, "docs")
    payload = ctx.read_index(sections=("records",))
    rec = _flow_record(payload, ctx, flow_id)
    view = build_flow_view(rec["data"], rules=_typed_records(payload, "rule"),
                           terms=_typed_records(payload, "term"))
    if section:
        if write_path:
            raise TodocError("--section cannot be combined with --write.", EXIT_USAGE, "usage.error")
        if not view["sections"][section].strip():
            raise ValidationError(f"Section is empty for this flow: {section}", "docs.section_not_found")
        _emit_command_result(ctx, {"id": flow_id, "section": section,
                  "text": view["sections"][section]}, output)
        return
    if write_path:
        rel = normalize_scope(write_path)
        _contained_out(ctx.root, rel)  # --write не выходит за DATA_ROOT
        target = ctx.root / rel
        expected_hash: str | None = None
        if target.is_file():
            existing_fm = parse_markdown(target.read_text(encoding="utf-8")).front_matter
            if not isinstance(existing_fm, dict) or "derived_from" not in existing_fm:
                raise ConflictError(
                    f"Target is not a generated view (no derived_from): {rel}. "
                    "Ручной файл не перезаписывается.",
                    "docs.flow_render_not_derived")
            expected_hash = file_hash(target)
        # Якоря — текущие хэши фрагментов записи: дрейф после правки видит stale.
        anchors = []
        for pointer in _FLOW_ANCHOR_POINTERS:
            value, status = fragment_hash(ctx.root, {"path": rec["path"], "pointer": pointer})
            if status == "ok" and value:
                anchors.append(f'"{rec["path"]}#{pointer}@{value}"')
        fm = "---\nderived_from: [" + ", ".join(anchors) + "]\n---\n\n"
        disclaimer = (f"<!-- СГЕНЕРИРОВАНО: `todoc docs flow render --root . --id {flow_id} "
                      f"--write {rel}`. НЕ ПРАВИТЬ РУКАМИ — правки затрёт следующий рендер; "
                      "дрейф после правки записи ловит `todoc stale`. -->\n\n")
        content = fm + disclaimer + view["markdown"] + "\n"
        new_hash = "sha256:" + hashlib.sha256(content.encode("utf-8")).hexdigest()
        plan = WritePlan(dataset_id=ctx.dataset_id, target_path=rel, new_content=content,
                         expected_hash=expected_hash, new_hash=new_hash,
                         basis=f"flow render --write {flow_id}")
        plan_hash = selection_key([ctx.dataset_id, plan.to_dict()])
        if if_plan_hash is not None and if_plan_hash != plan_hash:
            raise ConflictError("The generated artifact plan is stale.", "write.hash_mismatch")
        if not apply_:
            _emit_command_result(ctx, {"path": rel, "plan": plan.preview_dict(), "plan_hash": plan_hash,
                                       "preview": True, "applied": False}, output)
            return
        apply_write_plan(ctx.root, plan, history=ctx.history_recorder(), parse_cache=ctx.parse_cache)
        ctx.ensure_index()
        _emit_command_result(ctx, {"id": flow_id, "written": rel, "hash": new_hash, "plan_hash": plan_hash, "applied": True,
                  "derived_from": len(anchors)}, output,
                 next_actions=[{"argv": _root_argv(roots) + ["stale"],
                                "purpose": "Проверить дрейф витрины"}])
        return
    _emit_command_result(ctx, {"id": flow_id, "title": view["title"], "actor": view["actor"],
              "sections": view["sections"], "markdown": view["markdown"]}, output,
             next_actions=[{"argv": _root_argv(roots) + ["docs", "flow", "walk", "--id", flow_id],
                            "purpose": "Пройти дерево решений"}])


@docs_flow.command("walk", cls=UnifiedCommand)
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
@click.option("--id", "flow_id", required=True)
@click.option("--at", default=None, help="Старт обхода с узла дерева (id узла).")
@click.option("--all-paths", is_flag=True, help="Все ациклические пути до терминалов вместо основного.")
def docs_flow_walk(roots: tuple[str, ...], output: str, no_input: bool, flow_id: str,
                   at: str | None, all_paths: bool) -> None:
    """Пройти дерево решений флоу: ветви по приоритету, props развилок, пути до терминалов."""
    del no_input
    ctx = _single_context(roots, "docs")
    payload = ctx.read_index(sections=("records",))
    rec = _flow_record(payload, ctx, flow_id)
    view = build_flow_view(rec["data"], at=at)
    data: dict[str, Any] = {"dataset_id": ctx.dataset_id, "id": flow_id, "at": at}
    if all_paths:
        data["paths"] = view["walk_all"]["paths"]
    else:
        data["steps"] = view["walk"]["steps"]
    _emit_command_result(ctx, data, output,
             next_actions=[{"argv": _root_argv(roots) + ["docs", "flow", "render", "--id", flow_id],
                            "purpose": "Показать витрину флоу целиком"}])


@docs.command("status", cls=UnifiedCommand)
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
@click.option("--id", "doc_id", required=True)
@click.option("--set", "set_value", default=None, help="Новое значение статуса (без --set — чтение).")
@click.option("--preview", is_flag=True)
@click.option("--apply", "apply_", is_flag=True)
@click.option("--if-plan-hash")
def docs_status(roots: tuple[str, ...], output: str, no_input: bool, doc_id: str,
                set_value: str | None, preview: bool, apply_: bool, if_plan_hash: str | None) -> None:
    """Чтение/смена статуса md-документа: fm `status`, набор — allowed_statuses его doc_type.

    План «скилы-взаимодействия» З2: точечная замена строки статуса без перестройки
    документа, `updated:` бампается (единый писатель created/updated), history-ревизия.
    Документ без поля status не получает его молча — set отказ (docs.no_status_field).
    """
    del no_input
    _check_action_flags(preview, apply_)
    ctx = _single_context(roots, "docs")
    payload = ctx.read_index(sections=())
    doc = next((d for d in payload["documents"] if d["document_id"] == doc_id), None)
    if doc is None:
        raise ValidationError(f"Document not found: {doc_id}", "docs.not_found")
    text = (ctx.root / doc["path"]).read_text(encoding="utf-8")
    is_md = doc["format"] == "markdown"
    if set_value is None:
        if apply_:
            raise TodocError("--apply requires --set.", EXIT_USAGE, "usage.error")
        current = parse_markdown(text).front_matter.get("status") if is_md else None
        _emit_command_result(ctx, {"id": doc_id, "status": current}, output)
        return
    value = set_value.strip()
    if not value or value != set_value or "\n" in set_value:
        raise TodocError("--set ждёт одно значение статуса без обрамляющих пробелов",
                         EXIT_USAGE, "usage.error")
    descriptor = ctx.registry_types.doc_types.get(doc["doc_type"]) or {}
    allowed = descriptor.get("allowed_statuses")
    if isinstance(allowed, list) and allowed and value not in allowed:
        raise ValidationError(
            f"Статус {value!r} не входит в allowed_statuses типа {doc['doc_type']!r}",
            "docs.status_not_allowed")
    lines = text.splitlines()
    end = None
    if lines and lines[0].strip() == "---":
        end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        raise TodocError(f"У документа нет front matter: {doc_id}", EXIT_OPERATION, "docs.no_status_field")
    status_idx = next((i for i in range(1, end) if lines[i].startswith("status:")), None)
    if status_idx is None:
        raise TodocError(f"В front matter нет поля status — set не добавляет его молча: {doc_id}",
                         EXIT_OPERATION, "docs.no_status_field")
    new_lines = list(lines)
    new_lines[status_idx] = f"status: {value}"
    updated_idx = next((i for i in range(1, end) if new_lines[i].startswith("updated:")), None)
    if updated_idx is not None:
        new_lines[updated_idx] = f"updated: {_utc_date()}"
    content = "\n".join(new_lines) + ("\n" if text.endswith("\n") else "")
    new_hash = "sha256:" + hashlib.sha256(content.encode("utf-8")).hexdigest()
    plan = WritePlan(dataset_id=ctx.dataset_id, target_path=doc["path"], new_content=content,
                     expected_hash=file_hash(ctx.root / doc["path"]), new_hash=new_hash,
                     basis=f"docs status --set {doc_id} -> {value}")
    plan_hash = selection_key([ctx.dataset_id, plan.to_dict()])
    if if_plan_hash is not None and if_plan_hash != plan_hash:
        raise ConflictError("The status plan is stale.", "write.hash_mismatch")
    if not apply_:
        _emit_command_result(ctx, {"id": doc_id, "status": value, "plan_hash": plan_hash,
                                   "expected_hash": plan.expected_hash, "new_hash": new_hash,
                                   "applied": False}, output)
        return
    apply_write_plan(ctx.root, plan, history=ctx.history_recorder(), parse_cache=ctx.parse_cache)
    ctx.ensure_index()
    _emit_command_result(ctx, {"id": doc_id, "status": value, "new_hash": new_hash, "applied": True},
             output,
             next_actions=[{"argv": _root_argv(roots) + ["validate", "--root", str(ctx.root), "--all"],
                            "purpose": "Проверить набор после смены статуса"}])


def _load_patch_file(path: str) -> dict[str, Any]:
    try:
        text = Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise TodocError(f"Не удалось прочитать --patch-file {path}: {exc}", EXIT_USAGE, "usage.error") from exc
    value, errors = parse_json(text)
    if errors or not isinstance(value, dict):
        raise ValidationError("Patch file must contain a valid JSON object.", "edit.invalid_patch")
    return value


def _execute_metadata_patch(
    ctx: DatasetContext, entry: dict[str, Any], file_format: str, operations: Any,
    schemas: list[tuple[dict[str, Any], str]], output: str, if_hash: str | None, apply_: bool,
    *, record: bool = False, allowed_statuses: list[str] | None = None,
) -> None:
    plan, previous, attributes = plan_metadata_patch(
        ctx.root, ctx.dataset_id, entry, file_format, operations, schemas, record=record,
        allowed_statuses=allowed_statuses,
    )
    if not record and not any(source == SCHEMA_PATH for _schema, source in schemas):
        findings = _check_meta_fields(ctx.dataset_id, entry["path"], attributes)
        if findings:
            raise ValidationError(findings[0].message, findings[0].code)
    if if_hash is not None and if_hash != plan.expected_hash:
        raise ConflictError("The metadata preview is stale.", "write.hash_mismatch")
    if apply_ and if_hash is None:
        raise TodocError("Pass the preview hash with --if-hash.", EXIT_USAGE, "usage.error")
    if apply_ and plan.expected_hash != plan.new_hash:
        apply_write_plan(ctx.root, plan, expected_hash=if_hash, history=ctx.history_recorder(),
                         parse_cache=ctx.parse_cache)
        ctx.ensure_index()
    before = json.dumps(previous, ensure_ascii=False, indent=2).splitlines()
    after = json.dumps(attributes, ensure_ascii=False, indent=2).splitlines()
    meta = {"command": "records edit" if record else "docs edit",
            "scope": {"dataset_id": ctx.dataset_id, "path": entry["path"]}}
    result = {"preview": not apply_, "applied": apply_, "attributes": attributes,
              "expected_hash": plan.expected_hash, "new_hash": plan.new_hash,
              "diff": "\n".join(difflib.unified_diff(before, after, "before", "after", lineterm=""))}
    emit(Envelope.result(meta, result), output)


@docs.command("edit", cls=UnifiedCommand)
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
    ctx = _single_context(roots, "docs")
    payload = ctx.read_index(sections=())
    doc = next((d for d in payload["documents"] if d["document_id"] == doc_id), None)
    if doc is None:
        raise ValidationError(f"Document not found: {doc_id}", "docs.not_found")
    patch = _load_patch_file(patch_file)
    if "metadata" in patch:
        matches = [item for item in payload["documents"] if item["document_id"] == doc_id]
        if len(matches) != 1:
            raise ValidationError(f"Multiple documents share {doc_id!r}.", "docs.ambiguous_id")
        if set(patch) != {"metadata"} or (preview and apply_):
            raise ValidationError("Use a metadata patch or a line patch.", "edit.invalid_patch")
        common = load_metadata_schema(ctx.root)
        schemas = [(common, SCHEMA_PATH)] if common is not None and doc["managed_metadata"] else []
        typed = _load_schemas(ctx.root, ctx.registry_types, ctx.dataset, "doc_type", _doc_types_of)
        if doc["doc_type"] in typed:
            schemas.append(typed[doc["doc_type"]])
        descriptor = ctx.registry_types.doc_types.get(doc["doc_type"], {})
        _execute_metadata_patch(ctx, doc, doc["format"], patch["metadata"], schemas, output,
                                if_hash, apply_, allowed_statuses=descriptor.get("allowed_statuses"))
        return
    ops = patch.get("ops") or []
    if not isinstance(ops, list) or any(not isinstance(op, dict) for op in ops) or (preview and apply_):
        raise ValidationError('Expected one mode and a list of line operations in "ops".', "edit.invalid_patch")
    plan, original, updated_bumped = plan_edit_ops(ctx.root, doc["path"], ops, if_hash,
                                                    bump_updated=True, dataset_id=ctx.dataset_id)
    if apply_:
        apply_write_plan(ctx.root, plan, expected_hash=if_hash, history=ctx.history_recorder(),
                         parse_cache=ctx.parse_cache)
        ctx.ensure_index()
    scope = {"dataset_id": ctx.dataset_id, "path": doc["path"]}
    diff = "\n".join(difflib.unified_diff(original.splitlines(), plan.new_content.splitlines(),
                                         doc["path"], doc["path"], lineterm=""))
    result = {"id": doc_id, "path": doc["path"], "preview": not apply_, "applied": apply_,
              "ops": ops, "diff": diff, "expected_hash": plan.expected_hash,
              "new_hash": plan.new_hash, "updated_bumped": updated_bumped}
    emit(Envelope.result({"command": "docs edit", "scope": scope}, result), output)


@cli.group()
@click.pass_context
def records(ctx: click.Context) -> None:
    """Typed records operations."""


@records.command("edit", cls=UnifiedCommand)
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json")
@click.option("--id", "record_id", required=True)
@click.option("--patch-file", required=True)
@click.option("--if-hash")
@click.option("--preview", is_flag=True)
@click.option("--apply", "apply_", is_flag=True)
def records_edit(roots: tuple[str, ...], output: str, record_id: str, patch_file: str,
                 if_hash: str | None, preview: bool, apply_: bool) -> None:
    """Preview or apply a structured patch to a typed record."""
    ctx = _single_context(roots, "records")
    patch = _load_patch_file(patch_file)
    if set(patch) != {"metadata"} or (preview and apply_):
        raise ValidationError("Expected one metadata patch and one mode.", "edit.invalid_patch")
    matches = [item for item in ctx.read_index(sections=("records",))["records"] if item["record_id"] == record_id]
    if len(matches) != 1:
        raise ValidationError(f"Expected exactly one match for {record_id!r}.", "records.not_found")
    record = matches[0]
    schema = _record_schema(ctx, record["entity_type"])
    descriptor = ctx.registry_types.entity_types.get(record["entity_type"], {})
    required = descriptor.get("required_fields") or []
    schemas: list[tuple[dict[str, Any], str]] = [({"required": required}, "record descriptor")]
    if schema is not None:
        schemas.append((schema, "record schema"))
    _execute_metadata_patch(ctx, record, "json", patch["metadata"], schemas, output, if_hash, apply_, record=True)


@records.command("create", cls=UnifiedCommand)
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
@click.option("--type", "entity_type", required=True)
@click.option("--input-file", required=True)
@click.option("--preview", is_flag=True)
@click.option("--apply", "apply_", is_flag=True)
@click.option("--if-plan-hash")
def records_create(roots: tuple[str, ...], output: str, no_input: bool, entity_type: str, input_file: str,
                   preview: bool, apply_: bool, if_plan_hash: str | None) -> None:
    """Create-only new JSON record (preview default)."""
    if preview and apply_:
        raise TodocError("--apply cannot be combined with --preview.", EXIT_USAGE, "usage.error")
    ctx = _single_context(roots, "records")
    payload = ctx.read_index(sections=("records",))
    record = load_input_record(Path(input_file))
    if record.get("entity_type") != entity_type:
        record["entity_type"] = entity_type
    existing_ids = {r["record_id"] for r in payload["records"]}
    existing_paths = {d["path"] for d in payload["documents"]}
    schema = _record_schema(ctx, entity_type)
    plan = create_record_plan(ctx.dataset, ctx.registry_types.entity_types, record, existing_ids, existing_paths,
                              schema)
    plan_hash = selection_key([ctx.dataset_id, payload["corpus_digest"], plan.to_dict()])
    if if_plan_hash is not None and if_plan_hash != plan_hash:
        raise ConflictError("The record creation plan is stale.", "write.hash_mismatch")
    if not apply_:
        _emit_command_result(ctx, {"preview": True, "plan": plan.preview_dict(), "plan_hash": plan_hash}, output)
        return
    new_hash = apply_write_plan(ctx.root, plan, history=ctx.history_recorder(), parse_cache=ctx.parse_cache)
    ctx.ensure_index()
    _emit_command_result(ctx, {"created": plan.target_path, "new_hash": new_hash, "plan_hash": plan_hash}, output)


@records.command("undo-relation", cls=UnifiedCommand)
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
@click.option("--id", "record_id", required=True)
@click.option("--pointer", required=True, help="Путь ребра: /relations/N")
@click.option("--preview", is_flag=True)
@click.option("--apply", "apply_", is_flag=True)
@click.option("--if-plan-hash")
@click.option("--expected-hash", default=None)
def records_undo_relation(roots: tuple[str, ...], output: str, no_input: bool, record_id: str,
                          pointer: str, preview: bool, apply_: bool, expected_hash: str | None,
                          if_plan_hash: str | None) -> None:
    """Точечный откат ребра из ревизий журнала (preview по умолчанию)."""
    _check_action_flags(preview, apply_)
    ctx = _single_context(roots, "records")
    payload = ctx.read_index(sections=("records",))
    record = next((r for r in payload["records"] if r["record_id"] == record_id), None)
    if record is None:
        raise ValidationError(f"Record not found: {record_id}", "records.not_found")
    plan = plan_undo_relation(ctx.root, record["path"], pointer, store=ctx.history_store)
    current_hash = record["hash"]
    plan_hash = selection_key([ctx.dataset_id, current_hash, plan])
    if ((if_plan_hash is not None and if_plan_hash != plan_hash)
            or (expected_hash is not None and expected_hash != current_hash)):
        raise ConflictError("The relation undo plan is stale.", "write.hash_mismatch")
    if not apply_:
        _emit_command_result(ctx, {"preview": True, "plan": plan, "plan_hash": plan_hash,
                                   "expected_hash": current_hash}, output)
        return
    new_hash = apply_undo_relation(ctx.root, record["path"], pointer, plan["previous"],
                                   expected_hash=current_hash, history=ctx.history_recorder())
    ctx.ensure_index()
    _emit_command_result(ctx, {"applied": True, "path": record["path"],
              "pointer": pointer, "mode": plan["mode"], "new_hash": new_hash,
              "undone_rev": plan.get("rev"), "plan_hash": plan_hash}, output)


@records.command("list", cls=AttributeFilterCommand)
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
@click.option("--type", "entity_type", default=None)
@click.option("--since", default=None)
@click.option("--until", default=None)
@click.option("--relation", default=None)
@click.option("--limit", type=click.IntRange(1, 1000), default=200)
@click.option("--attribute", "attributes", type=(str, str), multiple=True, hidden=True)
@click.option("--filter-file", type=click.Path(dir_okay=False, path_type=Path))
@click.option("--tag-in", multiple=True, help="Match at least one tag, separated by |.")
@click.option("--tag-all", multiple=True, help="Match every tag, separated by |.")
@click.option("--view", default="flat")
@click.option("--fields", "include")
@click.option("--exclude-fields", "exclude")
@click.option("--cursor")
def records_list(roots: tuple[str, ...], output: str, no_input: bool, entity_type: str | None, since: str | None,
                 until: str | None, relation: str | None, limit: int,
                 attributes: tuple[tuple[str, str], ...], filter_file: Path | None,
                 tag_in: tuple[str, ...], tag_all: tuple[str, ...], view: str,
                 include: str | None, exclude: str | None, cursor: str | None) -> None:
    """List records with optional filters."""
    ctx = _single_context(roots, "records")
    _require_record_type(ctx, entity_type)
    payload = ctx.read_index(sections=("records", "relations"))
    filters: dict[str, Any] = {}
    if since:
        filters["date"] = {"$gte": since}
    if until:
        filters.setdefault("date", {})["$lte"] = until
    candidates, predicate = _select_records(ctx, payload["records"], entity_type,
                                             attributes, filter_file, tag_in, tag_all)
    if relation:
        rel_type, equals, target = relation.partition("=")
        if not equals or not rel_type or not target:
            raise TodocError("--relation needs TYPE=ID.", EXIT_USAGE, "filter.invalid")
        allowed_ids = {edge["source_id"] for edge in payload["relations"]
                       if edge["type_id"] == rel_type and edge["target_id"] == target}
        candidates = [record for record in candidates if record["record_id"] in allowed_ids]
    try:
        items, _total, _truncated = query_records(candidates, entity_type, filters, len(candidates))
    except TypeError as exc:
        raise ValidationError(f"Cannot compare record dates: {exc}", "filter.invalid") from exc
    _emit_records_page(ctx, payload, items, "records list", output, limit, cursor, view,
                       include, exclude, [entity_type, since, until, relation, predicate])


@records.command("status", cls=UnifiedCommand)
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
@click.option("--id", "record_id", required=True)
@click.option("--set", "set_value", default=None, help="Новое значение статуса (без --set — чтение).")
@click.option("--preview", is_flag=True)
@click.option("--apply", "apply_", is_flag=True)
@click.option("--if-plan-hash")
def records_status(roots: tuple[str, ...], output: str, no_input: bool, record_id: str,
                   set_value: str | None, preview: bool, apply_: bool, if_plan_hash: str | None) -> None:
    """Чтение/смена статуса JSON-записи: меняется ТОЛЬКО поле `status`.

    План «скилы-взаимодействия» З2: записи иначе create-only; набор — enum статуса
    из схемы entity_type (до записи — records.status_not_allowed, файл не трогается);
    атомарная запись поверх CAS-хэша, history-ревизия.
    """
    del no_input
    _check_action_flags(preview, apply_)
    ctx = _single_context(roots, "records")
    payload = ctx.read_index(sections=("records",))
    rec = next((r for r in payload["records"] if r.get("record_id") == record_id), None)
    if rec is None:
        raise ValidationError(f"Record not found: {record_id}", "records.not_found")
    data = rec.get("data") or {}
    if set_value is None:
        if apply_:
            raise TodocError("--apply requires --set.", EXIT_USAGE, "usage.error")
        _emit_command_result(ctx, {"id": record_id, "status": data.get("status")},
                 output)
        return
    value = set_value.strip()
    if not value or value != set_value or "\n" in set_value:
        raise TodocError("--set ждёт одно значение статуса без обрамляющих пробелов",
                         EXIT_USAGE, "usage.error")
    schemas = _load_schemas(ctx.root, ctx.registry_types, ctx.dataset, "entity_type", _entity_types_of)
    loaded = schemas.get(rec["entity_type"])
    if loaded:
        prop = (loaded[0].get("properties") or {}).get("status") or {}
        enum = prop.get("enum")
        if isinstance(enum, list) and enum and value not in enum:
            raise ValidationError(
                f"Статус {value!r} не входит в enum статуса типа {rec['entity_type']!r}",
                "records.status_not_allowed")
    target = ctx.root / rec["path"]
    current = json.loads(target.read_text(encoding="utf-8"))
    current["status"] = value
    content = json.dumps(current, indent=2, ensure_ascii=False) + "\n"
    new_hash = "sha256:" + hashlib.sha256(content.encode("utf-8")).hexdigest()
    plan = WritePlan(dataset_id=ctx.dataset_id, target_path=rec["path"], new_content=content,
                     expected_hash=file_hash(target), new_hash=new_hash,
                     basis=f"records status --set {record_id} -> {value}")
    plan_hash = selection_key([ctx.dataset_id, plan.to_dict()])
    if if_plan_hash is not None and if_plan_hash != plan_hash:
        raise ConflictError("The status plan is stale.", "write.hash_mismatch")
    if not apply_:
        _emit_command_result(ctx, {"id": record_id, "status": value, "plan_hash": plan_hash,
                                   "expected_hash": plan.expected_hash, "new_hash": new_hash,
                                   "applied": False}, output)
        return
    apply_write_plan(ctx.root, plan, history=ctx.history_recorder(), parse_cache=ctx.parse_cache)
    ctx.ensure_index()
    _emit_command_result(ctx, {"id": record_id, "status": value, "new_hash": new_hash, "applied": True},
             output,
             next_actions=[{"argv": _root_argv(roots) + ["validate", "--root", str(ctx.root), "--all"],
                            "purpose": "Проверить набор после смены статуса"}])


@records.command("query", cls=AttributeFilterCommand)
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
@click.option("--query-file")
@click.option("--as-of", "as_of", default=None, help="Только записи, бывшие правдой на этот момент.")
@click.option("--attribute", "attributes", type=(str, str), multiple=True, hidden=True)
@click.option("--filter-file", type=click.Path(dir_okay=False, path_type=Path))
@click.option("--tag-in", multiple=True, help="Match at least one tag, separated by |.")
@click.option("--tag-all", multiple=True, help="Match every tag, separated by |.")
@click.option("--view", default="flat")
@click.option("--fields", "include")
@click.option("--exclude-fields", "exclude")
@click.option("--cursor")
def records_query(roots: tuple[str, ...], output: str, no_input: bool, query_file: str | None,
                  as_of: str | None, attributes: tuple[tuple[str, str], ...], filter_file: Path | None,
                  tag_in: tuple[str, ...], tag_all: tuple[str, ...], view: str,
                  include: str | None, exclude: str | None, cursor: str | None) -> None:
    """Run a saved QuerySpec and optional metadata conditions."""
    if query_file is None and not any((attributes, filter_file, tag_in, tag_all)):
        raise TodocError("Pass --query-file or a metadata filter.", EXIT_USAGE, "usage.error")
    ctx = _single_context(roots, "records")
    spec = _query_spec(query_file) if query_file is not None else {}
    _require_record_type(ctx, spec.get("entity_type"))
    payload = ctx.read_index(sections=("records",))
    candidates, predicate = _select_records(ctx, payload["records"], spec.get("entity_type"),
                                             attributes, filter_file, tag_in, tag_all)
    try:
        items, _total, _truncated = query_records(candidates, spec.get("entity_type"),
                                                  spec.get("filters"), len(candidates), as_of=as_of)
    except InvalidInstant as exc:
        raise ValidationError(str(exc), "temporal.invalid_instant") from exc
    except TypeError as exc:
        raise ValidationError(f"Cannot compare QuerySpec operands: {exc}", "query.invalid_file") from exc
    _emit_records_page(ctx, payload, items, "records query", output, spec.get("limit", 200), cursor, view,
                       include, exclude, [spec.get("entity_type"), spec.get("filters"), as_of, predicate], as_of=as_of)


def _single_context(roots: tuple[str, ...], namespace: str) -> DatasetContext:
    resolved = resolve_roots(_effective_roots(roots))
    if len(resolved) != 1:
        raise TodocError("Choose exactly one DATA_ROOT.", EXIT_USAGE, f"{namespace}.multiple_roots")
    return DatasetContext(resolved[0])


def _emit_records_page(ctx: DatasetContext, payload: dict[str, Any], items: list[dict[str, Any]],
                       command: str, output: str, limit: int, cursor: str | None, view: str,
                       include: str | None, exclude: str | None, selection: list[Any], *,
                       as_of: str | None = None) -> None:
    meta = _collection_meta(command, view)
    meta["actual_view"] = "flat"
    meta["scope"] = {"dataset_id": ctx.dataset_id}
    if command == "records query":
        meta["as_of"] = as_of
    if failures := _document_read_failures(payload, "."):
        emit(Envelope.collection(meta, [], diagnostics=failures), output)
        raise click.exceptions.Exit(EXIT_INCOMPLETE)
    fields = selected_fields(("record_id", "entity_type", "dataset_id", "path", "hash", "data"),
                             include, exclude, structural=("record_id", "path"))
    identities = [(item["path"], item["record_id"]) for item in items]
    rows, next_cursor = page(
        items, [2, command, ctx.dataset_id, payload["corpus_digest"], selection, identities], limit, cursor,
    )
    meta.update(complete=True, total=len(items), returned=len(rows),
                truncated=next_cursor is not None, next_cursor=next_cursor)
    diagnostics = []
    if view != "flat":
        diagnostics.append({"code": "view.fallback", "severity": "info", "path": "",
                            "message": "The available view is flat."})
    emit(Envelope.collection(meta, [project_fields(row, fields) for row in rows],
                             diagnostics=diagnostics), output)


def _query_spec(path: str) -> dict[str, Any]:
    try:
        value, errors = parse_json(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError) as exc:
        raise ValidationError(f"Invalid query file: {exc}", "query.invalid_file") from exc
    problem = _query_spec_problem(value, errors)
    if problem:
        raise ValidationError(f"Invalid query file: {problem}", "query.invalid_file")
    return value


_QUERY_SPEC_KEYS = frozenset({"schema_version", "name", "entity_type", "filters", "limit", "sort_hint"})
_QUERY_OPERATORS = frozenset({"$in", "$gte", "$lte"})


def _query_spec_problem(value: Any, errors: list[str] | None) -> str | None:
    if errors or not isinstance(value, dict):
        return "expected a JSON object"
    unknown = sorted(set(value) - _QUERY_SPEC_KEYS)
    if unknown:
        return f"unknown keys: {', '.join(unknown)}"
    version = value.get("schema_version", 1)
    if type(version) is not int or version != 1:
        return f"unsupported schema_version {version!r} (expected 1)"
    for key in ("name", "sort_hint"):
        if key in value and not isinstance(value[key], str):
            return f"{key} must be a string"
    entity_type = value.get("entity_type")
    if entity_type is not None and (not isinstance(entity_type, str) or not entity_type.strip()):
        return "entity_type must be a non-empty string"
    filters = value.get("filters", {})
    if not isinstance(filters, dict):
        return "filters must be an object"
    for field, expected in filters.items():
        if not isinstance(field, str) or not field:
            return "filter field names must be non-empty strings"
        problem = _filter_problem(expected)
        if problem:
            return f"filter {field!r}: {problem}"
    limit = value.get("limit", 200)
    if type(limit) is not int or limit < 1:
        return "limit must be a positive integer"
    return None


def _filter_problem(expected: Any) -> str | None:
    if isinstance(expected, dict):
        unknown = sorted(set(expected) - _QUERY_OPERATORS)
        if unknown:
            return f"unsupported operators: {', '.join(unknown)}"
        if not expected:
            return "empty operator object"
        if "$in" in expected:
            if len(expected) > 1:
                return "$in cannot be combined with range operators"
            if not isinstance(expected["$in"], list):
                return "$in expects an array"
            return None
        for operator in ("$gte", "$lte"):
            if operator in expected and isinstance(expected[operator], (dict, list)):
                return f"{operator} expects a scalar"
        return None
    if isinstance(expected, list):
        return "use $in for array membership"
    return None


def _require_record_type(ctx: DatasetContext, entity_type: str | None) -> None:
    """Reject a document/relation type used as an entity type before any index read."""
    if entity_type is None or entity_type in ctx.registry_types.entity_types:
        return
    namespaces = (("doc_type", ctx.registry_types.doc_types),
                  ("dir_type", ctx.registry_types.dir_types),
                  ("relation_type", ctx.registry_types.relation_types))
    for namespace, declared in namespaces:
        if entity_type in declared:
            raise TodocError(
                f"{entity_type!r} is a {namespace}, not an entity_type. "
                f"Use `todoc docs search` or `todoc types list`.",
                EXIT_USAGE, "query.namespace_mismatch")
    raise TodocError(
        f"Unknown entity_type: {entity_type!r}. List declared types with `todoc types list`.",
        EXIT_USAGE, "query.unknown_type")


def _select_records(
    ctx: DatasetContext, records: list[dict[str, Any]], entity_type: str | None,
    attributes: tuple[tuple[str, str], ...], filter_file: Path | None,
    tag_in: tuple[str, ...], tag_all: tuple[str, ...],
) -> tuple[list[dict[str, Any]], list[Any]]:
    if not any((attributes, filter_file, tag_in, tag_all)):
        return records, []
    candidates = [item for item in records if entity_type is None or item["entity_type"] == entity_type]
    loaded = _load_schemas(ctx.root, ctx.registry_types, ctx.dataset, "entity_type", _entity_types_of)
    schemas = {name: schema for name, (schema, _source) in loaded.items()
               if entity_type is None or name == entity_type}
    declared = {key: value for schema in schemas.values() for key, value in schema.get("properties", {}).items()}
    conditions = compile_conditions([item["data"] for item in candidates], declared, attributes, filter_file)
    any_tags = split_values(part.casefold() for part in tag_in)
    all_tags = split_values(part.casefold() for part in tag_all)
    tag_fields = {key: schema.get("x-todoc-tag-field", "tags") for key, schema in schemas.items()}

    def tags(item: dict[str, Any]) -> list[str]:
        field = tag_fields.get(item["entity_type"], "tags")
        values = item["data"].get(field) if isinstance(field, str) else None
        return [tag for tag in values if isinstance(tag, str)] if isinstance(values, list) else []

    selected = [item for item in candidates if matches_conditions(item["data"], conditions)
                and tag_matches(tags(item), any_tags, all_tags)]
    return selected, [conditions, any_tags, all_tags]


@records.command("aggregate", cls=UnifiedCommand)
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
@click.option("--metric", required=True)
@click.option("--group-by", default=None)
@click.option("--type", "entity_type", required=True)
@click.option("--view", default="flat")
@click.option("--fields", "include")
@click.option("--exclude-fields", "exclude")
@click.option("--limit", type=click.IntRange(1, 1000), default=50, show_default=True)
@click.option("--cursor")
def records_aggregate(roots: tuple[str, ...], output: str, no_input: bool, metric: str,
                      group_by: str | None, entity_type: str, view: str, include: str | None,
                      exclude: str | None, limit: int, cursor: str | None) -> None:
    """Sum a numeric field with units and source records for each group."""
    ctx = _single_context(roots, "records")
    payload = ctx.read_index(sections=("records",))
    descriptor = _entity_types_of(ctx.registry_types).get(entity_type) or {}
    metric_fields = descriptor.get("metric_fields")
    spec = metric_fields.get(metric) if isinstance(metric_fields, dict) else None
    result = aggregate_records(payload["records"], entity_type, metric, group_by,
                               metric_spec=spec if isinstance(spec, dict) else None)
    rows = [{"group": key, "value": result["groups"][key], "unit": result["group_units"][key],
             "incoming_ids": result["group_incoming_ids"][key]} for key in sorted(result["groups"])]
    fields = selected_fields(("group", "value", "unit", "incoming_ids"), include, exclude,
                             structural=("group",))
    meta = _collection_meta("records aggregate")
    meta.update(scope={"dataset_id": ctx.dataset_id, "type": entity_type, "metric": metric, "group_by": group_by},
                requested_view=view)
    items, next_cursor = page(rows, [2, "records aggregate", meta["scope"], payload["corpus_digest"], spec],
                              limit, cursor)
    meta.update(complete=True, total=len(rows), returned=len(items),
                truncated=next_cursor is not None, next_cursor=next_cursor)
    diagnostics = []
    if view != "flat":
        diagnostics.append({"code": "view.fallback", "severity": "info", "path": "",
                            "message": f"Aggregate view {view!r} is unavailable. Returned flat output."})
    report = {key: result[key] for key in ("entity_type", "metric", "units", "formula", "prompt", "completeness")}
    report["items"] = [project_fields(row, fields) for row in items]
    emit(Envelope.result(meta, report, diagnostics=diagnostics), output)


@records.command("read", cls=UnifiedCommand)
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
@click.option("--id", "record_id", required=True)
@click.option("--view", default=None)
@click.option("--record-view", default=None)
def records_read(roots: tuple[str, ...], output: str, no_input: bool, record_id: str,
                 view: str | None, record_view: str | None) -> None:
    """Read one record and its source references."""
    ctx = _single_context(roots, "records")
    payload = ctx.read_index(sections=("records", "mentions"))
    matches = [record for record in payload["records"] if record["record_id"] == record_id]
    if not matches:
        raise ValidationError(f"Record not found: {record_id}", "records.not_found")
    if len(matches) > 1:
        raise ValidationError(f"Multiple records share {record_id!r}.", "records.ambiguous_id")
    if record_view is not None and view is not None:
        raise TodocError("Use either --record-view or --view.", EXIT_USAGE, "view.conflict")
    record = matches[0]
    descriptor = ctx.registry_types.entity_types.get(record["entity_type"], {})
    requested = record_view if record_view is not None else view or "full"
    actual = "full"
    data = dict(record["data"])
    fields = (descriptor.get("views") or {}).get(requested)
    diagnostics: list[dict[str, Any]] = []
    if requested != "full":
        if fields and (record_view is not None or view not in ("tree", "graph", "flat")):
            actual = requested
            data = {key: data[key] for key in fields if key in data}
        else:
            diagnostics.append({"code": "view.fallback", "severity": "info", "path": record["path"],
                                "message": f"Record view {requested!r} is unavailable. Returned the full record."})
    mentioned_in = [{"file": item.get("source_file"), "line": item.get("source_line"),
                     "fragment": item.get("source_fragment", "")}
                    for item in payload.get("mentions") or [] if item.get("target") == record_id]
    meta = {"command": "records read", "scope": {"dataset_id": ctx.dataset_id, "path": record["path"]},
            "requested_view": requested, "actual_view": actual}
    emit(Envelope.result(meta, {"record_id": record_id, "path": record["path"], "data": data,
                                "mentioned_in": mentioned_in}, diagnostics=diagnostics), output)


# --- план «Интероп-экспорты» З2: записи → внешние форматы (derived-артефакты) --


@cli.group()
def interop() -> None:
    """Экспорт витрин во внешние форматы (DMN 1.3 / ASL / Rasa NLU YML)."""


@interop.command("export", cls=UnifiedCommand)
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
@click.option("--kind", type=click.Choice(["dmn", "asl", "rasa"]), required=True)
@click.option("--id", "record_id", default=None,
              help="record_id источника (для rasa можно опустить — весь глоссарий).")
@click.option("--write", "write_path", default=None, metavar="PATH",
              help="Путь экспорта относительно корня (только exports/…); без него артефакт печатается в stdout.")
@click.option("--preview", is_flag=True)
@click.option("--apply", "apply_", is_flag=True)
@click.option("--if-plan-hash")
def interop_export(roots: tuple[str, ...], output: str, no_input: bool, kind: str,
                   record_id: str | None, write_path: str | None, preview: bool, apply_: bool,
                     if_plan_hash: str | None) -> None:
    """Запись-источник → артефакт внешнего формата (derived-артефакт, review-first).

    Без --write артефакт печатается в stdout; с --write — markdown-документ в
    exports/ с fm derived_from на записи-источники (дрейф ловит `todoc stale`).
    Перезапись поверх CAS разрешена только для derived-целей; записи не трогаются.
    """
    del no_input
    _check_action_flags(preview, apply_)
    if apply_ and not write_path:
        raise TodocError("--apply requires --write.", EXIT_USAGE, "usage.error")
    ctx = _single_context(roots, "interop")
    payload = ctx.read_index(sections=("records",))
    doc_id, title, artifact, lang, anchors = _interop_artifact(ctx, payload, kind, record_id)
    if write_path is None:
        _emit_command_result(ctx, {"kind": kind, "record_id": record_id,
                  "id": doc_id, "artifact": artifact, "anchors": anchors}, output)
        return
    target = _contained_out(ctx.root, write_path)
    rel = target.relative_to(ctx.root).as_posix()
    if not rel.startswith("exports/") or len(rel) <= len("exports/"):
        raise TodocError(f"--write принимает путь только внутри exports/: {rel!r}",
                         EXIT_USAGE, "interop.write_outside_exports")
    target = ctx.root / rel
    expected_hash: str | None = None
    if target.is_file():
        existing_fm = parse_markdown(target.read_text(encoding="utf-8")).front_matter
        if not isinstance(existing_fm, dict) or "derived_from" not in existing_fm:
            raise ConflictError(
                f"Target is not a generated export (no derived_from): {rel}. "
                "Ручной файл не перезаписывается.",
                "interop.target_not_derived")
        expected_hash = file_hash(target)
    content = build_export_doc(doc_id=doc_id, title=title, kind=kind, anchors=anchors,
                               artifact=artifact, lang=lang, today=_utc_date())
    new_hash = "sha256:" + hashlib.sha256(content.encode("utf-8")).hexdigest()
    plan = WritePlan(dataset_id=ctx.dataset_id, target_path=rel, new_content=content,
                     expected_hash=expected_hash, new_hash=new_hash,
                     basis=f"interop export {kind} {record_id or '(glossary)'}")
    plan_hash = selection_key([ctx.dataset_id, plan.to_dict()])
    if if_plan_hash is not None and if_plan_hash != plan_hash:
        raise ConflictError("The generated artifact plan is stale.", "write.hash_mismatch")
    if not apply_:
        _emit_command_result(ctx, {"path": rel, "plan": plan.preview_dict(), "plan_hash": plan_hash,
                                   "preview": True, "applied": False}, output)
        return
    apply_write_plan(ctx.root, plan, history=ctx.history_recorder(), parse_cache=ctx.parse_cache)
    ctx.ensure_index()
    _emit_command_result(ctx, {"kind": kind, "id": doc_id,
              "written": rel, "hash": new_hash, "plan_hash": plan_hash, "applied": True, "derived_from": len(anchors)}, output,
             next_actions=[{"argv": _root_argv(roots) + ["stale"],
                            "purpose": "Проверить дрейф экспортов"}])


def _interop_artifact(ctx: DatasetContext, payload: dict[str, Any], kind: str,
                      record_id: str | None) -> tuple[str, str, str, str, list[str]]:
    """Артефакт + якоря derived_from для одного экспорта (контракт — докстроки interop.py)."""
    if kind == "rasa" and record_id is None:
        term_recs = sorted((r for r in payload["records"]
                            if r.get("entity_type") == "term" and isinstance(r.get("data"), dict)),
                           key=lambda r: str(r.get("record_id") or ""))
        if not term_recs:
            raise ValidationError("No term records in the dataset.", "interop.no_terms")
        artifact = terms_to_rasa([r["data"] for r in term_recs])
        anchors = [anchor_for(ctx.root, str(r["path"]), "/definition") for r in term_recs]
        return ("doc:export-rasa-glossary", "Экспорт Rasa NLU: глоссарий", artifact, "yaml", anchors)
    if record_id is None:
        raise TodocError("--id обязателен для kind asl|dmn (rasa без --id экспортирует весь глоссарий)",
                         EXIT_USAGE, "usage.error")
    rec = next((r for r in payload["records"] if r.get("record_id") == record_id), None)
    if rec is None:
        raise ValidationError(f"Record not found: {record_id}", "records.not_found")
    data = rec.get("data") or {}
    entity_type = data.get("entity_type")
    slug = record_id.split(":", 1)[-1]
    if kind == "asl":
        if entity_type != "flow":
            raise ValidationError(f"kind asl expects a flow record, got {entity_type!r}: {record_id}",
                                  "interop.wrong_entity_type")
        artifact = json.dumps(flow_to_asl(data), indent=2, ensure_ascii=False) + "\n"
        return (f"doc:export-asl-{slug}", f"Экспорт ASL: {record_id}", artifact, "json",
                [anchor_for(ctx.root, str(rec["path"]), "/tree")])
    if kind == "dmn":
        if entity_type != "rule":
            raise ValidationError(f"kind dmn expects a rule record, got {entity_type!r}: {record_id}",
                                  "interop.wrong_entity_type")
        flow_id = related_flow_id(data)
        flow_rec = next((r for r in payload["records"] if r.get("record_id") == flow_id), None)
        if flow_rec is None:
            raise ValidationError(f"Related flow record not found: {flow_id}", "interop.flow_missing")
        artifact = rule_to_dmn(data, flow_rec.get("data") or {})
        return (f"doc:export-dmn-{slug}", f"Экспорт DMN: {record_id}", artifact, "xml",
                [anchor_for(ctx.root, str(rec["path"]), "/statement"),
                 anchor_for(ctx.root, str(rec["path"]), "/examples"),
                 anchor_for(ctx.root, str(flow_rec["path"]), "/tree")])
    if entity_type != "term":
        raise ValidationError(f"kind rasa expects a term record, got {entity_type!r}: {record_id}",
                              "interop.wrong_entity_type")
    artifact = terms_to_rasa([data])
    return (f"doc:export-rasa-{slug}", f"Экспорт Rasa NLU: {record_id}", artifact, "yaml",
            [anchor_for(ctx.root, str(rec["path"]), "/definition")])


@cli.group()
@click.pass_context
def relations(ctx: click.Context) -> None:
    """Typed relations."""


@relations.command("graph", cls=UnifiedCommand)
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
@click.option("--from", "from_id", required=True)
@click.option("--type", "type_id", default=None)
@click.option("--depth", type=click.IntRange(0, 100), default=1)
@click.option("--limit", type=click.IntRange(1, 1000), default=100)
@click.option("--cursor")
@click.option("--view", default="graph")
@click.option("--fields", "include")
@click.option("--exclude-fields", "exclude")
def relations_graph(roots: tuple[str, ...], output: str, no_input: bool, from_id: str,
                    type_id: str | None, depth: int, limit: int, cursor: str | None,
                    view: str, include: str | None, exclude: str | None) -> None:
    """Browse directed typed relations and source mentions."""
    meta = _collection_meta("relations graph", view)
    meta["actual_view"] = view if view in ("graph", "flat") else "graph"
    try:
        resolved = resolve_roots(_effective_roots(roots))
        if len(resolved) != 1:
            raise TodocError("Choose exactly one DATA_ROOT.", EXIT_USAGE, "relations.multiple_roots")
        ctx = DatasetContext(resolved[0])
        meta["scope"] = {"dataset_id": ctx.dataset_id, "from": from_id, "depth": depth}
        fields = selected_fields(("type_id", "from", "to", "via", "fragment", "provenance"),
                                 include, exclude, structural=("type_id", "from", "to"))
        payload = ctx.read_index(sections=("relations", "mentions"))
        edges = graph_neighbors(payload["relations"], from_id, type_id, depth, None,
                                mentions=payload.get("mentions"))
        selection = [2, "relations graph", ctx.dataset_id, payload["corpus_digest"], from_id, type_id, depth]
        selected, next_cursor = page(edges, selection, limit, cursor)
    except TodocError as exc:
        _emit_collection_error(meta, exc.code, exc.message, output)
        raise click.exceptions.Exit(exc.exit_code) from exc
    meta.update(complete=True, total=len(edges), returned=len(selected),
                truncated=next_cursor is not None, next_cursor=next_cursor)
    projected = [project_fields(edge, fields) for edge in selected]
    result = {"items": projected}
    if meta["actual_view"] == "graph":
        ends = {edge[side] for edge in projected for side in ("from", "to")}
        nodes = [from_id, *sorted(ends - {from_id})]
        result = {"nodes": nodes, "edges": projected}
        if output == "markdown":
            result["mermaid"] = mermaid_graph(nodes, projected)
    diagnostics = []
    if meta["actual_view"] != view:
        diagnostics.append({"code": "view.fallback", "severity": "info", "path": "",
                            "message": "The available views for relations graph are graph and flat."})
    emit(Envelope.result(meta, result, diagnostics=diagnostics), output)


def _relations_tree_text(tree: dict[str, Any]) -> str:
    """Компактный текст-рендер дерева связей (план entity-catalog З3/T11)."""
    lines = [str(tree["root"])]

    def render(groups: list[dict[str, Any]], indent: str) -> None:
        arrow = {"out": "→", "in": "←"}
        for group in groups:
            for edge in group["edges"]:
                mark = " [mention]" if edge.get("via") == "mention" else ""
                fragment = f"#{edge['fragment']}" if edge.get("fragment") else ""
                suffix = " (cycle)" if edge.get("cycle") else ""
                lines.append(f"{indent}{group['type_id']} {arrow[edge['direction']]} "
                             f"{edge['id']}{fragment}{mark}{suffix}")
                render(edge.get("children") or [], indent + "  ")
            if group.get("truncated"):
                lines.append(f"{indent}… (обрезано)")

    render(tree["groups"], "  ")
    if tree.get("truncated"):
        lines.append("… (лимит рёбер)")
    return "\n".join(lines)


@relations.command("tree", cls=UnifiedCommand)
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
@click.option("--from", "from_id", required=True)
@click.option("--type", "type_id", default=None)
@click.option("--depth", type=click.IntRange(0, 100), default=1, show_default=True)
@click.option("--limit", type=click.IntRange(1, 1000), default=100, show_default=True)
@click.option("--cursor")
def relations_tree(roots: tuple[str, ...], output: str, no_input: bool, from_id: str,
                   type_id: str | None, depth: int, limit: int, cursor: str | None) -> None:
    """Return a page of relation traversal with ancestor context."""
    meta = _collection_meta("relations tree", "tree")
    try:
        resolved = resolve_roots(_effective_roots(roots))
        if len(resolved) != 1:
            raise TodocError("Choose exactly one DATA_ROOT.", EXIT_USAGE, "relations.multiple_roots")
        ctx = DatasetContext(resolved[0])
        payload = ctx.read_index(sections=("relations", "mentions"))
        meta["scope"] = {"dataset_id": ctx.dataset_id, "from": from_id, "depth": depth}
        key = selection_key([2, "relations tree", ctx.dataset_id, payload["corpus_digest"], from_id, type_id, depth])
        start = cursor_offset(cursor, key)
        full = build_tree(payload["relations"], from_id, type_id, depth, None,
                          mentions=payload.get("mentions"))
        tree, total = slice_relation_tree(full, start, start + limit)
        if cursor is not None and start >= total:
            raise TodocError("Cursor is outside this selection.", EXIT_USAGE, "cursor.invalid")
    except TodocError as exc:
        _emit_collection_error(meta, exc.code, exc.message, output)
        raise click.exceptions.Exit(exc.exit_code) from exc
    next_cursor = next_page_cursor(key, start + limit, total)
    meta.update(complete=True, total=total, returned=min(limit, total - start),
                truncated=next_cursor is not None, next_cursor=next_cursor)
    result = {"tree": tree}
    if output != "json":
        result["outline"] = _relations_tree_text(tree)
    emit(Envelope.result(meta, result), output)


@cli.group()
@click.pass_context
def types(ctx: click.Context) -> None:
    """Type catalog."""


@types.command("list", cls=UnifiedCommand)
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json")
@click.option("--no-input", is_flag=True)
@click.option("--kind", type=click.Choice(["dir_type", "doc_type", "entity_type", "relation_type"]))
@click.option("--fields", "include")
@click.option("--exclude-fields", "exclude")
@click.option("--limit", type=click.IntRange(1, 1000), default=100)
@click.option("--cursor")
@click.option("--view", default="flat")
def types_list(roots: tuple[str, ...], output: str, no_input: bool, kind: str | None,
               include: str | None, exclude: str | None, limit: int, cursor: str | None, view: str) -> None:
    """List registered types with their kind and descriptor summary."""
    ctx = _single_context(roots, "types")
    registry = ctx.registry_types
    stores = {"dir_type": registry.dir_types, "doc_type": registry.doc_types,
              "entity_type": registry.entity_types, "relation_type": registry.relation_types}
    rows = []
    for name, store in stores.items():
        if kind is None or kind == name:
            for type_id, descriptor in sorted(store.items()):
                rows.append({"kind": name, "type_id": type_id, "version": descriptor.get("version"),
                             "format": descriptor.get("format"), "description": descriptor.get("description")})
    meta = _collection_meta("types list")
    meta["requested_view"] = view
    meta["scope"] = {"dataset_id": ctx.dataset_id, "kind": kind}
    meta["counts"] = {name: len(store) for name, store in stores.items()}
    fields = selected_fields(("kind", "type_id", "version", "format", "description"), include, exclude,
                             structural=("kind", "type_id"))
    _emit_flat_page(meta, rows, [2, "types list", ctx.dataset_id, kind, stores], fields, limit, cursor, output)


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


@types.command("metadata", cls=UnifiedCommand)
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json")
@click.option("--limit", type=click.IntRange(1, 1000), default=50)
@click.option("--cursor")
def types_metadata(roots: tuple[str, ...], output: str, limit: int, cursor: str | None) -> None:
    """Preview adoption of the common document metadata schema."""
    ctx = _single_context(roots, "types")
    configured = load_metadata_schema(ctx.root)
    schema = configured if configured is not None else default_metadata_schema()
    payload = ctx.read_index(sections=())
    meta = _collection_meta("types metadata")
    meta["scope"] = {"dataset_id": ctx.dataset_id}
    if failures := _document_read_failures(payload, "."):
        emit(Envelope.collection(meta, [], diagnostics=failures), output)
        raise click.exceptions.Exit(EXIT_INCOMPLETE)
    all_findings = []
    inspected = 0
    for doc in payload["documents"]:
        if not doc["managed_metadata"]:
            continue
        inspected += 1
        findings = metadata_errors(doc["attributes"], schema, doc["metadata_pointer"])
        if findings:
            all_findings.append({
                "path": doc["path"], "id": doc["document_id"],
                "violations": [{"pointer": pointer, "message": message} for pointer, message in findings],
            })
    rows, next_cursor = page(all_findings, [2, "types metadata", ctx.dataset_id,
                                            payload["corpus_digest"], schema], limit, cursor)
    meta.update(complete=True, total=len(all_findings), returned=len(rows),
                truncated=next_cursor is not None, next_cursor=next_cursor)
    emit(Envelope.result(meta, {"items": rows, "inspected": inspected,
                                "installed": configured is not None, "path": SCHEMA_PATH, "schema": schema}), output)


@types.command("show", cls=UnifiedCommand)
@click.argument("type_id")
@click.option("--kind", "requested_kind", type=click.Choice(
    ["dir_type", "doc_type", "entity_type", "relation_type"]))
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
def types_show(type_id: str, roots: tuple[str, ...], output: str, no_input: bool,
               requested_kind: str | None) -> None:
    ctx = _single_context(roots, "types")
    for kind, store in (("dir_type", ctx.registry_types.dir_types), ("doc_type", ctx.registry_types.doc_types),
                        ("entity_type", ctx.registry_types.entity_types),
                        ("relation_type", ctx.registry_types.relation_types)):
        if type_id in store and requested_kind in (None, kind):
            bundle = _type_bundle(ctx, kind, store[type_id])
            data = {"dataset_id": ctx.dataset_id, "kind": kind, "type": store[type_id],
                    "template": bundle["template"], "prompts": bundle["prompts"], "schema": bundle["schema"]}
            if kind == "doc_type":
                common = load_metadata_schema(ctx.root)
                typed = _load_schemas(ctx.root, ctx.registry_types, ctx.dataset, "doc_type", _doc_types_of)
                type_schema = typed.get(type_id, ({}, ""))[0]
                data["document_metadata"] = {
                    "schema_path": SCHEMA_PATH, "enabled": common is not None,
                    "required": sorted(set((common or {}).get("required", [])) | set(type_schema.get("required", []))),
                    "fields": _document_filter_fields(ctx, (type_id,)),
                }
            _emit_command_result(ctx, data, output,
                     next_actions=[{"argv": _root_argv(roots) + ["types", "prompt", type_id, "--op", "create", "--kind", kind],
                                    "purpose": "Взять стартовый промпт создания документа этого типа"}]
                     if bundle["prompts"] else [])
            return
    raise ValidationError(f"Unknown type: {type_id}", "types.unknown")


@types.command("prompt", cls=UnifiedCommand)
@click.argument("type_id")
@click.option("--kind", "requested_kind", type=click.Choice(["doc_type", "entity_type"]))
@click.option("--op", "operation", type=click.Choice(list(PROMPT_OPERATIONS)), default="create", show_default=True)
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
def types_prompt(type_id: str, operation: str, roots: tuple[str, ...], output: str, no_input: bool,
                 requested_kind: str | None) -> None:
    """Starter prompt of a type for one CRUD operation (read/create/edit/delete)."""
    ctx = _single_context(roots, "types")
    for kind, store in (("doc_type", ctx.registry_types.doc_types), ("entity_type", ctx.registry_types.entity_types)):
        if type_id in store and requested_kind in (None, kind):
            paths = prompt_files(ctx.root, ctx.dataset, kind, store[type_id])
            path = paths.get(operation)
            if path is None or not path.is_file():
                raise ValidationError(
                    f"No {operation!r} prompt for type {type_id!r} "
                    f"(expected {path.name if path is not None else 'prompts/'}",
                    "types.prompt_missing")
            text = path.read_text(encoding="utf-8")
            _emit_command_result(ctx, {"type_id": type_id, "kind": kind, "operation": operation,
                      "path": f".todoc/{type_kind_dir(ctx.dataset, kind)}/{type_id}/prompts/{operation}.md",
                      "prompt": text, "chars": len(text)}, output)
            return
    raise ValidationError(f"Unknown type: {type_id}", "types.unknown")


@types.command("guide", cls=UnifiedCommand)
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
@click.option("--format", "fmt", type=click.Choice(["markdown", "json"]), default="markdown")
@click.option("--out", default=None)
@click.option("--preview", is_flag=True)
@click.option("--apply", "apply_", is_flag=True)
@click.option("--if-plan-hash")
def types_guide(roots: tuple[str, ...], output: str, no_input: bool, fmt: str, out: str | None,
                preview: bool, apply_: bool, if_plan_hash: str | None) -> None:
    """Generated type reference (stdout or --out)."""
    _check_action_flags(preview, apply_)
    if apply_ and out is None:
        raise TodocError("--apply requires --out.", EXIT_USAGE, "usage.error")
    ctx = _single_context(roots, "types")
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
    if out is None:
        _emit_command_result(ctx, {"guide": text, "format": fmt}, output)
        return
    target = _contained_out(ctx.root, out)
    rel = target.relative_to(ctx.root).as_posix()
    expected = file_hash(target) if target.is_file() else None
    content = text + "\n"
    digest = "sha256:" + hashlib.sha256(content.encode("utf-8")).hexdigest()
    plan = WritePlan(dataset_id=ctx.dataset_id, target_path=rel, new_content=content,
                     expected_hash=expected, new_hash=digest, basis="types guide")
    plan_hash = selection_key([ctx.dataset_id, plan.to_dict()])
    if if_plan_hash is not None and if_plan_hash != plan_hash:
        raise ConflictError("The guide plan is stale.", "write.hash_mismatch")
    if apply_:
        apply_write_plan(ctx.root, plan, parse_cache=ctx.parse_cache)
    _emit_command_result(ctx, {"guide": text, "format": fmt, "path": rel, "plan_hash": plan_hash,
                               "applied": apply_, "hash": digest}, output)


@cli.command("fix", cls=UnifiedCommand)
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
@click.option("--diagnostic", required=True)
@click.option("--preview", is_flag=True)
@click.option("--apply", "apply_", is_flag=True)
@click.option("--if-hash", default=None)
@click.option("--if-plan-hash")
def fix(roots: tuple[str, ...], output: str, no_input: bool, diagnostic: str, preview: bool,
        apply_: bool, if_hash: str | None, if_plan_hash: str | None) -> None:
    """Preview/apply a supported fix (review-first)."""
    _check_action_flags(preview, apply_)
    ctx = _single_context(roots, "fix")
    _f, _d, _r, _rel, diagnostics = ctx.scan_and_validate(write_cache=False)
    target = next((d for d in diagnostics if d.get("id") == diagnostic), None)
    if target is None:
        raise ValidationError(f"Diagnostic not found: {diagnostic}", "fix.diagnostic_not_found")
    fixes = target.get("suggested_fixes") or []
    if not fixes:
        raise ValidationError(f"Diagnostic {diagnostic} has no suggested fixes", "fix.no_fixes")
    fix0 = fixes[0]
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
    source = _contained_out(ctx.root, rel_path)
    old_bytes = source.read_bytes()
    source_hash = "sha256:" + hashlib.sha256(old_bytes).hexdigest()
    if if_hash is not None and if_hash != source_hash:
        raise ConflictError("The source changed before the fix.", "write.hash_mismatch")
    lines = old_bytes.decode("utf-8").splitlines(keepends=True)
    line = target.get("location", {}).get("line")
    if not isinstance(line, int) or line < 1 or line > len(lines) or lines[line - 1].count(evidence) != 1:
        raise ValidationError("Link evidence is missing or ambiguous on the source line.", "fix.cannot_apply")
    replacement = (f"[[{new_target}]]" if evidence.startswith("[[")
                   else evidence.removesuffix(f"{old_target})") + new_target + ")")
    lines[line - 1] = lines[line - 1].replace(evidence, replacement, 1)
    content = "".join(lines)
    new_hash = "sha256:" + hashlib.sha256(content.encode("utf-8")).hexdigest()
    plan = WritePlan(dataset_id=ctx.dataset_id, target_path=rel_path, new_content=content,
                     expected_hash=source_hash, new_hash=new_hash, basis=f"fix {diagnostic}")
    plan_hash = selection_key([ctx.dataset_id, diagnostic, plan.to_dict()])
    if if_plan_hash is not None and if_plan_hash != plan_hash:
        raise ConflictError("The fix plan is stale.", "write.hash_mismatch")
    if apply_:
        apply_write_plan(ctx.root, plan, history=ctx.history_recorder(), parse_cache=ctx.parse_cache,
                         event_kind="doc.fix")
        ctx.ensure_index()
    _emit_command_result(ctx, {"diagnostic": diagnostic, "fix": fix0, "plan": plan.preview_dict() if not apply_ else plan.to_dict(),
                               "plan_hash": plan_hash, "preview": not apply_, "applied": apply_,
                               "new_hash": new_hash}, output)


@cli.command("doctor", cls=UnifiedCommand)
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
@click.option("--check", default=None, help="Comma-separated check ids.")
@click.option("--scope", default=None, help="Группа проверок: dataset | environment | all.")
@click.option("--fix", "fix_", is_flag=True, help="Preview rebuilding a missing, stale, or corrupt index.")
@click.option("--preview", is_flag=True)
@click.option("--apply", "apply_", is_flag=True)
@click.option("--if-plan-hash")
def doctor(roots: tuple[str, ...], output: str, no_input: bool, check: str | None, scope: str | None,
           fix_: bool, preview: bool, apply_: bool, if_plan_hash: str | None) -> None:
    """Report checks and optionally repair the derived index."""
    _check_action_flags(preview, apply_)
    if (apply_ or if_plan_hash is not None) and not fix_:
        raise TodocError("Repair options require --fix.", EXIT_USAGE, "usage.error")
    if scope is not None and scope not in DOCTOR_SCOPES:
        raise TodocError(f"Unknown check scope: {scope!r}.", EXIT_USAGE, "usage.error")
    wanted = {part.strip() for part in check.split(",")} if check else set(DOCTOR_SCOPES["all"])
    if not wanted.issubset(DOCTOR_SCOPES["all"]):
        raise TodocError("--check expects config, index or python.", EXIT_USAGE, "usage.error")
    selected = wanted.intersection(DOCTOR_SCOPES[scope or "all"])
    contexts = [_single_context(roots, "doctor")] if apply_ or if_plan_hash is not None else _contexts(roots)
    reports = []
    for ctx in contexts:
        checks = []
        if "config" in selected:
            checks.append(("config", True, "Dataset config loads."))
        if "python" in selected:
            checks.append(("python", True, f"Python {sys.version.split()[0]}."))
        repair = None
        if "index" in selected:
            status = ctx.index_status()
            snapshot = ctx.read_index(sections=()) if fix_ or status.state == "valid" else None
            state = status.state
            if state == "valid" and snapshot["corpus_digest"] != status.meta["corpus_digest"]:
                state = "stale"
            if fix_:
                plan_hash = selection_key(["doctor", str(ctx.root), ctx.dataset_id, state, snapshot["corpus_digest"]])
                if if_plan_hash is not None and if_plan_hash != plan_hash:
                    raise ConflictError("The repair plan is stale.", "write.hash_mismatch")
                repair = {"operation": "index rebuild" if state != "valid" else None,
                          "index_before": state, "plan_hash": plan_hash, "applied": False}
                if apply_ and state != "valid":
                    ctx.rebuild_index(force=True, observe=False)
                    state = "valid"
                    repair["applied"] = True
            checks.append(("index", state == "valid", f"Published index state: {state}."))
        elif apply_ or if_plan_hash is not None:
            raise TodocError("Repair requires selecting the index check.", EXIT_USAGE, "usage.error")
        checks.sort(key=lambda item: DOCTOR_SCOPES["all"].index(item[0]))
        reports.append({"dataset_id": ctx.dataset_id, "root": str(ctx.root), "scope": scope or "all",
                        "checks_total": len(checks), "passed": sum(ok for _, ok, _ in checks),
                        "checks": [{"id": cid, "status": "pass" if ok else "fail", "message": message}
                                   for cid, ok, message in checks], "fix_mode": fix_, "repair": repair})
    _emit_result({"datasets": reports}, output, [], False)


@cli.command("status", cls=UnifiedCommand)
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
def status(roots: tuple[str, ...], output: str, no_input: bool) -> None:
    """Quick state snapshot (distinct from doctor)."""
    reports = []
    for ctx in _contexts(roots):
        snapshot = ctx.index_status()
        valid = snapshot.state == "valid"
        published = snapshot.meta or {}
        counts = published.get("counts", {}) if valid else {}
        reports.append({"dataset_id": ctx.dataset_id, "root": str(ctx.root), "index_built": valid, "index_state": snapshot.state,
                        "generation_id": published.get("generation_id"),
                        "documents": counts.get("documents"), "records": counts.get("records")})
    meta = {"command": "status", "scope": {"roots": [report["root"] for report in reports]}}
    response = Envelope.result(meta, {"datasets": reports})
    response.next_actions = [
        {"argv": ["todoc", "index", "rebuild", "--root", report["root"]],
         "purpose": "Посмотреть план пересборки индекса"} for report in reports if not report["index_built"]
    ]
    emit(response, output)


DOCTOR_SCOPES = {"dataset": ("config", "index"), "environment": ("python",),
                 "all": ("config", "index", "python")}


def _emit_error(code: str, message: str, exit_code: int, output: str = "json",
                command: str | None = None) -> None:
    """Failures are envelopes too: one valid JSON per invocation, plus a human line.

    Callers (agents, scripts, MCP) parse stdout; a bare text line on stderr is
    not a machine-readable result, so the same fact is also emitted as
    ``ok: false`` with a diagnostic carrying the stable ``code``.
    """
    diagnostic = {"dataset_id": "", "id": stable_id(code, message), "code": code, "severity": "error",
                  "path": "", "location": {}, "evidence": "", "message": message, "suggested_fixes": []}
    envelope = Envelope.result({"command": command or "todoc", "scope": None}, {}, diagnostics=[diagnostic])
    envelope.next_actions = [{"argv": ["todoc", *(command.split() if command else ()), "--help"],
                              "purpose": "Показать список команд и опций"}]
    emit(envelope, output)
    sys.stderr.write(f"Error [{code}]: {message}\n")
    sys.exit(exit_code)


@cli.group()
def state() -> None:
    """Агентский стейт сессии (v1): state.json вне данных, XDG_STATE_HOME."""


@state.command("set", cls=UnifiedCommand)
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
@click.argument("key")
@click.argument("value")
@click.option("--preview", is_flag=True)
@click.option("--apply", "apply_", is_flag=True)
@click.option("--if-plan-hash")
def state_set(roots: tuple[str, ...], output: str, no_input: bool, key: str, value: str,
              preview: bool, apply_: bool, if_plan_hash: str | None) -> None:
    """Показать или применить изменение переменной стейта."""
    _check_action_flags(preview, apply_)
    ctx = _single_context(roots, "state")
    previous = get_var(ctx.dataset_id, key)
    plan_hash = selection_key([ctx.dataset_id, "set", key, previous, value])
    if if_plan_hash is not None and if_plan_hash != plan_hash:
        raise ConflictError("The state plan is stale.", "write.hash_mismatch")
    data = set_var(ctx.dataset_id, key, value, apply=apply_)
    _emit_command_result(ctx, {"key": key, "value": data["vars"][key], "previous": previous,
                               "updated_at": data["updated_at"], "plan_hash": plan_hash, "applied": apply_}, output,
                         next_actions=[{"argv": _root_argv(roots) + ["state", "get", key],
                                        "purpose": "Перечитать записанное"}] if apply_ else None)


@state.command("get", cls=UnifiedCommand)
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
@click.argument("key")
def state_get(roots: tuple[str, ...], output: str, no_input: bool, key: str) -> None:
    """Прочитать переменную стейта (value: null — не установлена)."""
    ctx = _single_context(roots, "state")
    value = get_var(ctx.dataset_id, key)
    _emit_command_result(ctx, {"key": key, "value": value}, output)


@state.command("list", cls=UnifiedCommand)
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json")
@click.option("--no-input", is_flag=True)
@click.option("--prefix")
@click.option("--fields", "include")
@click.option("--exclude-fields", "exclude")
@click.option("--limit", type=click.IntRange(1, 1000), default=100)
@click.option("--cursor")
@click.option("--view", default="flat")
def state_list(roots: tuple[str, ...], output: str, no_input: bool, prefix: str | None,
               include: str | None, exclude: str | None, limit: int, cursor: str | None, view: str) -> None:
    """List dataset-scoped session variables."""
    ctx = _single_context(roots, "state")
    data = load_state(ctx.dataset_id)
    rows = [{"key": key, "value": value} for key, value in sorted(data["vars"].items())
            if prefix is None or key.startswith(prefix)]
    meta = _collection_meta("state list")
    meta["requested_view"] = view
    meta["scope"] = {"dataset_id": ctx.dataset_id, "prefix": prefix}
    fields = selected_fields(("key", "value"), include, exclude, structural=("key",))
    _emit_flat_page(meta, rows, [2, "state list", ctx.dataset_id, prefix, data], fields, limit, cursor, output)


@state.command("unset", cls=UnifiedCommand)
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
@click.argument("key")
@click.option("--preview", is_flag=True)
@click.option("--apply", "apply_", is_flag=True)
@click.option("--if-plan-hash")
def state_unset(roots: tuple[str, ...], output: str, no_input: bool, key: str,
                preview: bool, apply_: bool, if_plan_hash: str | None) -> None:
    """Показать или применить удаление переменной стейта."""
    _check_action_flags(preview, apply_)
    ctx = _single_context(roots, "state")
    previous = get_var(ctx.dataset_id, key)
    plan_hash = selection_key([ctx.dataset_id, "unset", key, previous])
    if if_plan_hash is not None and if_plan_hash != plan_hash:
        raise ConflictError("The state plan is stale.", "write.hash_mismatch")
    removed = unset_var(ctx.dataset_id, key) if apply_ else False
    _emit_command_result(ctx, {"key": key, "previous": previous, "removed": removed,
                               "plan_hash": plan_hash, "applied": apply_}, output,
                         next_actions=[{"argv": _root_argv(roots) + ["state", "list"],
                                        "purpose": "Оставшиеся переменные"}] if removed else None)


def _emit_unified_error(ctx: click.Context, code: str, message: str, exit_code: int) -> None:
    name = command_name(ctx) or "todoc"
    default = {"docs tree": "tree", "skills tree": "tree", "relations tree": "tree", "relations graph": "graph"}
    meta = _collection_meta(name, default.get(name, "flat"))
    _emit_collection_error(meta, code, message, resolved_output(ctx))
    sys.exit(exit_code)


def _click_error_output(ctx: click.Context | None) -> str:
    return resolved_output(ctx) if ctx is not None else "json"


def main() -> None:
    try:
        result = cli(standalone_mode=False)
        if isinstance(result, int):
            sys.exit(result)
    except TodocError as exc:
        ctx = getattr(exc, "cli_context", None)
        if ctx is not None:
            _emit_unified_error(ctx, exc.code, exc.message, exc.exit_code)
        _emit_error(exc.code, exc.message, exc.exit_code)
    except click.ClickException as exc:
        ctx = getattr(exc, "ctx", None)
        if (isinstance(exc, click.UsageError) and ctx is not None
                and isinstance(ctx.command, (UnifiedCommand, DiscoverableGroup))):
            _emit_unified_error(ctx, "usage.error", exc.format_message(), EXIT_USAGE)
        _emit_error("usage.error", exc.format_message(), EXIT_USAGE, _click_error_output(ctx),
                    command_name(ctx) if ctx is not None else None)


if __name__ == "__main__":
    main()
