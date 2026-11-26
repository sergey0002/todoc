"""Click CLI: thin input layer over application services (constitution §8)."""

from __future__ import annotations

import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import click

from todoc import __version__
from todoc.adapters.filesystem.scanner import atomic_write, file_hash, is_within_root
from todoc.adapters.history.journal import read_events
from todoc.adapters.formats.csvfmt import parse_csv
from todoc.adapters.formats.jsonfmt import parse_json, resolve_pointer
from todoc.adapters.formats.markdown import (heading_path_for, parse_markdown,
                                           resolve_link_target)
from todoc.application.history import (add_tag, blame as history_blame, content_at, diff_texts,
                                       export as history_export_run, gc as history_gc_run,
                                       adopt as history_adopt_run, journal_diagnostics,
                                       log as history_log, resolve_rev,
                                       revert_plan, show as history_show)
from todoc.application.changes import (TRANSLIT, apply_change, archive_change, change_id_for,
                                       collect_deltas, list_changes, load_change,
                                       open_change, record_path, revert_change,
                                       validate_change, verify_change)
from todoc.application.context import build_context
from todoc.application.query import aggregate_records, graph_neighbors, query_records
from todoc.application.folder_config import load_folder_configs, score_folder_configs
from todoc.application.search import search_documents
from todoc.application.skills import scan_skills
from todoc.application.staleness import check_all, collect_owners, current_hashes, plan_ack
from todoc.application.temporal import InvalidInstant, timeline as build_timeline
from todoc.application.validator import (_basename_index, _entity_types_of,
                                         _load_schemas, _wikilink_candidates, stable_id)
from todoc.application.write import (apply_edit_ops, apply_fix, apply_write_plan, create_document_plan,
                                   create_record_plan, load_input_record)
from todoc.config import init_dataset
from todoc.errors import (EXIT_CONFLICT, EXIT_INCOMPLETE, EXIT_OPERATION, EXIT_USAGE, AccessError,
                          ConflictError, TodocError, ValidationError)
from todoc.output.envelope import emit, make_envelope
from todoc.service import DatasetContext, resolve_roots
from todoc.typing_system.descriptors import (PROMPT_OPERATIONS, descriptor_diagnostics,
                                             load_json_file, prompt_files, schema_file,
                                             template_file, type_kind_dir)


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
@click.option("--dataset-id", default=None,
              help="Идентификатор датасета. По умолчанию случаен; явное значение делает "
                   "демо-датасет и фикстуры воспроизводимыми.")
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
def init(root: str, dataset_id: str | None, output: str, no_input: bool) -> None:
    """Create portable .todoc/ control files (never scans/moves user data)."""
    dataset = init_dataset(Path(root), dataset_id)
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
        meta = ctx.store.read_current_meta() or {}
        gen = meta.get("generation_id")
        results.append({"dataset_id": ctx.dataset_id, "generation_id": gen, "current": gen is not None,
                        "corpus_digest": meta.get("corpus_digest"), "created_at": meta.get("created_at")})
    _emit_ok({"datasets": results}, output, None)


@index.command("rebuild")
@click.option("--root", "roots", multiple=True)
@click.option("--force", is_flag=True, help="Recompute even when the corpus digest is unchanged.")
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
def index_rebuild(roots: tuple[str, ...], force: bool, output: str, no_input: bool) -> None:
    results = [ctx.rebuild_index(force=force) for ctx in _contexts(roots)]
    _emit_ok({"datasets": results}, output, None)


@cli.group()
def skills() -> None:
    """Skills vault (open Agent Skills standard): tree/read/attach/import."""


@skills.command("tree")
@click.option("--root", "roots", multiple=True)
@click.option("--vault", default="skills", show_default=True, help="Vault dir relative to DATA_ROOT.")
@click.option("--within", default=None, help="Срез раздела: префикс пути секции (напр. coding/git).")
@click.option("--query", default=None, help="Lowercase-подстрока по name+description+пути (кириллица работает).")
@click.option("--all", "show_all", is_flag=True, help="Показать мьютнутые (!-папки) с пометкой [!].")
@click.option("--limit", type=int, default=100, show_default=True, help="Bounded output (P7).")
@click.option("--max-depth", type=int, default=6, show_default=True, help="Глубина печатаемого дерева.")
@click.option("--output", type=click.Choice(["json", "table"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
def skills_tree(roots: tuple[str, ...], vault: str, within: str | None, query: str | None,
                show_all: bool, limit: int, max_depth: int, output: str, no_input: bool) -> None:
    """Оглавление хранилища скилов на лету (live-scan, без индекса — P1)."""
    ctx = _contexts(roots)[0]
    vault_root = ctx.root / vault
    skills_list, _diags = scan_skills(vault_root)
    if not vault_root.is_dir():
        raise TodocError(f"Хранилище скилов не найдено: {vault}/ (DATA_ROOT: {ctx.root})",
                         EXIT_OPERATION, "skills.not_found")
    if len(skills_list) > 500:  # порог идеи: живой скан всегда, предупреждение вместо индекса
        sys.stderr.write(f"warning: {len(skills_list)} skills in vault — live scan may be slow\n")
    shown = [s for s in skills_list if show_all or not s.muted]
    if within:
        shown = [s for s in shown if s.section == within or s.section.startswith(within.rstrip("/") + "/")]
    vault_configs, _fc_diags = load_folder_configs(vault_root)
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

    def _depth(s: Any) -> int:
        return 0 if s.section == "" else s.section.count("/") + 1

    shown = [s for s in shown if _depth(s) < max_depth]  # bounded в обоих режимах (P7)
    truncated = len(shown) > limit
    shown = shown[:limit]
    items = [{"name": s.name, "path": s.path, "section": s.section,
              "description": s.description, "muted": s.muted,
              "refs": s.refs, "scripts": s.scripts, "assets": s.assets} for s in shown]
    data = {
        "dataset_id": ctx.dataset_id,
        "vault": vault,
        "counts": {"skills": len(skills_list),
                   "sections": len({s.section.split("/")[0] for s in skills_list if s.section}),
                   "muted": sum(1 for s in skills_list if s.muted)},
        "skills": items,
        "section_meta": section_meta,
        "truncated": truncated,
    }
    if output == "table":
        click.echo(_skills_tree_text(items, data["counts"], truncated, max_depth, section_meta))
        return
    _emit_ok(data, output, None,
             next_actions=[{"argv": _root_argv(roots) + ["skills", "read", "--path", "<путь из дерева>"],
                            "purpose": "Прочитать SKILL.md выбранного скила"}])


def _skills_tree_text(shown: list[dict[str, Any]], counts: dict[str, int],
                      truncated: bool, max_depth: int,
                      sec_meta: dict[str, dict[str, Any]] | None = None) -> str:
    """ASCII-дерево как в образце идеи: описания в stdout, [!] для мьюта."""
    sec_meta = sec_meta or {}
    lines = [f"skills/  ({counts['skills']} skills, {counts['sections']} sections, "
             f"{counts['muted']} muted){' [truncated]' if truncated else ''}"]
    sections: dict[str, list[dict[str, Any]]] = {}
    for s in shown:
        sections.setdefault(s["section"], []).append(s)

    children: dict[str, set[str]] = {}
    for section in sections:
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
            label = f"[!] {s['name']}" if s["muted"] else s["name"]
            lines.append("  " * (depth + 1) + f"{label}  {s['description']}")
        for child in sorted(children.get(node, set()), key=_sec_key):
            _render(child, depth + 1)

    _render("", 0)
    return "\n".join(lines)


@skills.command("read")
@click.option("--root", "roots", multiple=True)
@click.option("--vault", default="skills", show_default=True)
@click.option("--path", "p", required=True, help="Папка скила или путь к SKILL.md (можно с префиксом vault).")
@click.option("--line-range", default=None, help="Диапазон строк A-B (дефис).")
@click.option("--budget", type=int, default=None, help="Максимум байт содержимого (честный бюджет).")
@click.option("--output", type=click.Choice(["json", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
def skills_read(roots: tuple[str, ...], vault: str, p: str, line_range: str | None,
                budget: int | None, output: str, no_input: bool) -> None:
    """Прочитать SKILL.md скила: путь резолвится только внутри vault (confinement)."""
    ctx = _contexts(roots)[0]
    vault_root = (ctx.root / vault).resolve()
    skills_list, _diags = scan_skills(vault_root)
    rel = Path(p.strip("/"))
    parts = rel.as_posix().split("/")
    if parts and parts[0] == vault:
        parts = parts[1:]
    rel = Path("/".join(parts))
    if rel.as_posix().endswith("/SKILL.md"):
        folder_rel = rel.parent.as_posix()
    else:
        folder_rel = rel.as_posix()
    skill = next((s for s in skills_list
                  if s.path == folder_rel or s.path.lstrip("!") == folder_rel), None)
    target = vault_root / folder_rel / "SKILL.md" if skill is None else vault_root / skill.skill_md
    if skill is None or not target.is_file() or not is_within_root(vault_root, target):
        raise TodocError(
            f"Скил не найден вне/внутри vault: {p} (vault: {vault}/). Сначала: todoc skills tree",
            EXIT_OPERATION, "skills.not_found")
    content = target.read_text(encoding="utf-8")
    truncated = False
    if line_range:
        a, _, b = line_range.partition("-")
        lo, hi = max(1, int(a or 1)), int(b or 10**9)
        lines = content.splitlines(keepends=True)
        content = "".join(lines[lo - 1:hi])
    if budget is not None:
        encoded = content.encode("utf-8")
        if len(encoded) > budget:
            content = encoded[:budget].decode("utf-8", errors="ignore")
            truncated = True
    if output == "markdown":
        click.echo(content)
        return
    _emit_ok({"path": skill.skill_md, "name": skill.name, "description": skill.description,
              "muted": skill.muted, "content": content, "truncated": truncated},
             output, None,
             next_actions=[{"argv": _root_argv(roots) + ["skills", "read", "--path", skill.path],
                            "purpose": "Перечитать скил"},
                           {"argv": _root_argv(roots) + ["docs", "read", "--id",
                                                         f"doc:{skill.skill_md.removesuffix('/SKILL.md')}"],
                            "purpose": "Прочитать скил как документ датасета (bounded)"}])


@skills.command("attach")
@click.option("--to", "to_dir", required=True,
              help="Каталог скилов платформы (.claude/skills/, .agents/skills/, .cursor/skills/, ...).")
@click.option("--root", "roots", multiple=True, help="DATA_ROOT, вшиваемый в тело диспетчера ({ROOT}).")
@click.option("--force", is_flag=True, help="Перезаписать существующий скил todoc.")
@click.option("--output", type=click.Choice(["json", "table"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
def skills_attach(roots: tuple[str, ...], to_dir: str, force: bool, output: str, no_input: bool) -> None:
    """Диспетчер-скил todoc → одна точка входа для любого агента.

    Копирует пакетную папку `todoc/` в платформенный каталог скилов, подставляя
    DATA_ROOT вместо {ROOT}. Витрина скилов в платформу НЕ монтируется —
    L1-контекст несёт ровно один скил (~100 токенов) при vault любого размера.
    """
    from importlib import resources

    if not roots:
        raise TodocError("Укажите --root DATA_ROOT (вшивается в тело диспетчера).",
                         EXIT_USAGE, "usage.error")
    root_resolved = Path(_effective_roots(roots)[0]).resolve()
    dest = Path(to_dir) / "todoc"
    if dest.exists() and not force:
        raise TodocError(f"{dest} уже существует; обновление — с --force.",
                         EXIT_CONFLICT, "attach.exists")
    dest.mkdir(parents=True, exist_ok=force)
    pkg = resources.files("todoc") / "data" / "agent-skill" / "todoc"
    copied = 0
    with resources.as_file(pkg) as src_dir:
        for src in sorted(Path(src_dir).rglob("*")):
            if not src.is_file():
                continue
            rel = src.relative_to(src_dir)
            target = dest / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            if rel.name == "SKILL.md":
                target.write_text(src.read_text(encoding="utf-8")
                                  .replace("{ROOT}", str(root_resolved)), encoding="utf-8")
            else:
                target.write_bytes(src.read_bytes())
            copied += 1
    _emit_ok({"installed": str(dest / "SKILL.md"), "skill": "todoc", "files": copied,
              "root_embedded": str(root_resolved),
              "mount_hint": "для платформ без нативных скилов — строка роутинга в AGENTS.md "
                            "(demo/notes/agent-contract.md → «Скилы»)"},
             output, None,
             next_actions=[{"argv": ["todoc", "skills", "tree", "--root", str(root_resolved)],
                            "purpose": "Проверить, что дерево хранилища доступно диспетчеру"}])


@skills.command("import")
@click.option("--root", "roots", multiple=True)
@click.option("--src", "src_dir", required=True, help="Локальная папка-скил или репо-пакет (**/SKILL.md).")
@click.option("--skill", "skill_filter", default=None, help="Копировать один скил (по имени папки).")
@click.option("--into", "section", required=True, help="Раздел vault, куда класть (напр. coding/review).")
@click.option("--vault", default="skills", show_default=True)
@click.option("--dry-run", is_flag=True, help="Показать план без записи.")
@click.option("--adopt", is_flag=True, help="Источник уже в vault: валидировать и отчитаться без копии.")
@click.option("--output", type=click.Choice(["json", "table"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
def skills_import(roots: tuple[str, ...], src_dir: str, skill_filter: str | None, section: str,
                  vault: str, dry_run: bool, adopt: bool, output: str, no_input: bool) -> None:
    """Офлайн-импорт чужих скилов: папки со SKILL.md, обвязка пакетов не переносится."""
    from todoc.application.skills import scan_skills, validate_skills, effective_name

    ctx = _contexts(roots)[0]
    vault_root = (ctx.root / vault).resolve()
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
    written = False
    for folder in folders:
        name = effective_name(folder.name)
        if adopt:
            dest = vault_root / section / name
            if not (dest / "SKILL.md").is_file():
                raise TodocError(f"Скил «{name}» не найден в vault: {section}/{name}/SKILL.md. "
                                 f"Скопируй папку в vault и повтори --adopt.",
                                 EXIT_OPERATION, "skills.not_found")
            adopted.append(name)
            continue
        dest = vault_root / section / folder.name
        if (dest / "SKILL.md").exists() or (dest.exists() and any(dest.iterdir())):
            skipped.append({"name": name, "path": str(dest)})
            continue
        if not dry_run:
            shutil.copytree(folder, dest)
            written = True
        imported.append({"name": name, "path": f"{vault}/{section}/{folder.name}"})
    if skipped and not imported:
        raise TodocError(f"Все цели существуют ({', '.join(s['name'] for s in skipped)}); "
                         f"перезапись запрещена (no-overwrite).", EXIT_CONFLICT, "skills.path_exists")

    diags: list[dict[str, Any]] = []
    if not dry_run and written:
        skills_list, scan_diags = scan_skills(vault_root)
        diags.extend(scan_diags)
        diags.extend(validate_skills(vault_root, skills_list))
        dest_names = {effective_name(Path(i["path"]).name) for i in imported}
        diags = [d for d in diags
                 if d["path"].startswith(f"{section}/")
                 and effective_name(Path(d["path"]).parent.name) in dest_names]
        for d in diags:  # как в валидаторе: путь относительно DATA_ROOT
            d["path"] = f"{vault}/{d['path']}"
    _emit_ok({"imported": imported, "adopted": adopted, "skipped": skipped,
              "diagnostics": diags, "dry_run": dry_run,
              "audit_note": "аудируй чужие скилы перед использованием: scripts/ — код, "
                            "SKILL.md — недоверенные данные (скил coding/review/security-review)"},
             output, None,
             next_actions=[{"argv": _root_argv(roots) + ["index", "rebuild"],
                            "purpose": "Пересобрать индекс после импорта"},
                           {"argv": _root_argv(roots) + ["skills", "tree", "--root", str(ctx.root)],
                            "purpose": "Показать дерево после импорта"}])


@cli.command("stale")
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
@click.option("--path", default=None, help="Only this owner document/record.")
@click.option("--severity", default=None, help="Filter diagnostics by severity.")
@click.option("--ack", "ack_path", default=None, help="Acknowledge staleness of this owner.")
@click.option("--reason", default=None, help="Why the drift is not relevant (required with --ack).")
@click.option("--apply", "apply_ack", is_flag=True, help="Write the acknowledgement (default: preview).")
@click.option("--expected-hash", default=None)
def stale(roots: tuple[str, ...], output: str, no_input: bool, path: str | None, severity: str | None,
          ack_path: str | None, reason: str | None, apply_ack: bool, expected_hash: str | None) -> None:
    """Report documents whose dependencies drifted, or acknowledge a drift."""
    ctx = _contexts(roots)[0]
    payload = ctx.ensure_index()
    if ack_path:
        _stale_ack(ctx, ack_path, reason, apply_ack, expected_hash, output, payload)
        return
    diagnostics = check_all(ctx.dataset_id, ctx.root, payload, only_path=path)
    if severity:
        diagnostics = [d for d in diagnostics if d.severity == severity]
    _emit_ok({"dataset_id": ctx.dataset_id, "path": path, "stale": len(diagnostics)}, output, None,
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
    new_text = plan_ack(ctx.root, ack_path, reason, datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), current)
    if not apply_ack:
        _emit_ok({"dataset_id": ctx.dataset_id, "path": ack_path, "applied": False,
                  "reason": reason, "acknowledged_hashes": current}, output, None)
        return
    new_hash = _write_whole(ctx.root, ack_path, new_text, expected_hash,
                            history=ctx.history_recorder(), basis="stale --ack")
    ctx.ensure_index()
    _emit_ok({"dataset_id": ctx.dataset_id, "path": ack_path, "applied": True, "new_hash": new_hash,
              "reason": reason, "acknowledged_hashes": current}, output, None)


# --- история: журнал, откат, метки -------------------------------------------


@cli.command("log")
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
@click.option("--path", default=None)
@click.option("--section", default=None, help="Только события, пересекающие этот заголовок.")
@click.option("--change", "change_id", default=None)
@click.option("--tag", default=None)
@click.option("--kind", default=None)
@click.option("--since", default=None)
@click.option("--until", default=None)
@click.option("--limit", type=int, default=20)
@click.option("--cursor", default=None)
def log_cmd(roots: tuple[str, ...], output: str, no_input: bool, path: str | None, section: str | None,
            change_id: str | None, tag: str | None, kind: str | None, since: str | None, until: str | None,
            limit: int, cursor: str | None) -> None:
    """Журнал событий записи: что, когда и в каких строках менялось."""
    ctx = _contexts(roots)[0]
    ctx.ensure_index()
    if section and not path:
        raise TodocError("--section требует --path: раздел ищется внутри файла", EXIT_USAGE, "usage.error")
    events, total, truncated = history_log(ctx.root, path=path, section=section, kind=kind,
                                           change_id=change_id, tag=tag, since=since, until=until,
                                           limit=limit, cursor=_parse_offset(cursor))
    _emit_ok({"dataset_id": ctx.dataset_id, "total": total, "truncated": truncated,
              "cursor": str(_parse_offset(cursor) + len(events)), "events": events}, output, None,
             [d.to_dict() for d in journal_diagnostics(ctx.dataset_id, ctx.root)])


@cli.command("show")
@click.argument("rev", required=False, default=None)
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
@click.option("--path", required=True)
@click.option("--budget", type=int, default=None)
def show_cmd(rev: str | None, roots: tuple[str, ...], output: str, no_input: bool, path: str,
             budget: int | None) -> None:
    """Содержимое файла на ревизии (или текущее, если rev не задан)."""
    ctx = _contexts(roots)[0]
    resolved = resolve_rev(ctx.root, rev) if rev else None
    text, status = history_show(ctx.root, resolved, path, backend=ctx.history_recorder().backend)
    if text is None:
        raise _history_unavailable(status, path)
    if budget is not None:
        text = text[:budget]
    _emit_ok({"dataset_id": ctx.dataset_id, "path": path, "rev": resolved, "content": text}, output, None)


@cli.command("diff")
@click.argument("rev_a", required=False, default=None)
@click.argument("rev_b", required=False, default=None)
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
@click.option("--path", required=True)
@click.option("--context", "ctx_lines", type=int, default=3)
@click.option("--budget", type=int, default=None)
def diff_cmd(rev_a: str | None, rev_b: str | None, roots: tuple[str, ...], output: str, no_input: bool,
             path: str, ctx_lines: int, budget: int | None) -> None:
    """Разница между двумя ревизиями файла; без rev_b — против текущего состояния."""
    ctx = _contexts(roots)[0]
    backend = ctx.history_recorder().backend
    left, status_a = history_show(ctx.root, resolve_rev(ctx.root, rev_a) if rev_a else None, path, backend=backend)
    right, status_b = history_show(ctx.root, resolve_rev(ctx.root, rev_b) if rev_b else None, path, backend=backend)
    if left is None:
        raise _history_unavailable(status_a, path)
    if right is None:
        raise _history_unavailable(status_b, path)
    lines = diff_texts(left, right, context=ctx_lines)
    if budget is not None:
        lines = lines[: max(budget // 40, 1)]
    _emit_ok({"dataset_id": ctx.dataset_id, "path": path, "rev_a": rev_a, "rev_b": rev_b,
              "changed": bool(lines), "lines": len(lines), "diff": lines}, output, None)


@cli.command("blame")
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
@click.option("--path", required=True)
@click.option("--section", default=None)
def blame_cmd(roots: tuple[str, ...], output: str, no_input: bool, path: str, section: str | None) -> None:
    """Кто и когда менял файл или его раздел."""
    ctx = _contexts(roots)[0]
    ctx.ensure_index()
    entries = history_blame(ctx.root, path, section)
    _emit_ok({"dataset_id": ctx.dataset_id, "path": path, "section": section,
              "entries": entries}, output, None)


@cli.command("timeline")
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
@click.option("--as-of", "as_of", default=None, help="Состояние на этот момент (ISO-8601).")
@click.option("--path", default=None, help="Только события и факты этого файла.")
@click.option("--limit", type=int, default=200, show_default=True)
def timeline_cmd(roots: tuple[str, ...], output: str, no_input: bool, as_of: str | None,
                 path: str | None, limit: int) -> None:
    """Единая лента: события записи и интервалы фактов в одном хронологическом порядке."""
    ctx = _contexts(roots)[0]
    payload = ctx.ensure_index()
    try:
        result = build_timeline(ctx.root, payload["records"], payload["relations"],
                                as_of=as_of, path=path, limit=limit)
    except InvalidInstant as exc:
        raise ValidationError(str(exc), "temporal.invalid_instant") from exc
    _emit_ok({"dataset_id": ctx.dataset_id, **result}, output, None,
             [d.to_dict() for d in journal_diagnostics(ctx.dataset_id, ctx.root)])


@cli.command("revert")
@click.argument("rev")
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
@click.option("--path", required=True)
@click.option("--apply", "apply_revert", is_flag=True)
@click.option("--expected-hash", default=None)
def revert_cmd(rev: str, roots: tuple[str, ...], output: str, no_input: bool, path: str,
               apply_revert: bool, expected_hash: str | None) -> None:
    """Откат файла к ревизии. Без --apply — только план (review-first)."""
    ctx = _contexts(roots)[0]
    recorder = ctx.history_recorder()
    plan = revert_plan(ctx.root, resolve_rev(ctx.root, rev), path, backend=recorder.backend)
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
        _emit_ok({"dataset_id": ctx.dataset_id, "path": path, "rev": rev, "applied": False,
                  "current_hash": plan["current_hash"], "new_hash": plan["new_hash"],
                  "range_conflict": bool(plan.get("range_conflict"))}, output, None,
                 diagnostics=warnings)
        return
    if expected_hash is not None and expected_hash != plan["current_hash"]:
        raise ConflictError(f"Hash mismatch for {path}", "write.hash_mismatch")
    new_hash = _write_whole(ctx.root, path, plan["content"], None, history=recorder,
                            basis=f"revert {rev}")
    ctx.ensure_index()
    _emit_ok({"dataset_id": ctx.dataset_id, "path": path, "rev": rev, "applied": True,
              "new_hash": new_hash, "range_conflict": bool(plan.get("range_conflict"))},
             output, None, diagnostics=warnings)


@cli.command("tag")
@click.argument("name")
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
@click.option("--rev", default=None, help="По умолчанию — последнее событие журнала.")
@click.option("--message", default="")
def tag_cmd(name: str, roots: tuple[str, ...], output: str, no_input: bool, rev: str | None,
            message: str) -> None:
    """Метка на ревизии: привязка истории к релизу."""
    ctx = _contexts(roots)[0]
    target = resolve_rev(ctx.root, rev) if rev else (read_events(ctx.root)[-1]["rev"] if read_events(ctx.root) else None)
    if not target:
        raise TodocError("Журнал пуст: метку ставить не на что", EXIT_INCOMPLETE, "history.revision_unknown")
    entry = add_tag(ctx.root, name, target, message)
    _emit_ok({"dataset_id": ctx.dataset_id, "tag": name, **entry}, output, None)


@cli.group()
@click.pass_context
def history(ctx: click.Context) -> None:
    """Обслуживание истории: сборка мусора, миграция, бэкап."""


@history.command("gc")
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
@click.option("--keep-objects", type=int, default=None)
@click.option("--purge-before", default=None)
@click.option("--dry-run", is_flag=True)
def history_gc(roots: tuple[str, ...], output: str, no_input: bool, keep_objects: int | None,
               purge_before: str | None, dry_run: bool) -> None:
    """Удаляет события и снимки, на которые больше никто не ссылается."""
    ctx = _contexts(roots)[0]
    result = history_gc_run(ctx.root, keep_objects=keep_objects, purge_before=purge_before,
                            dry_run=dry_run, limits=ctx.dataset.get("limits") or {})
    _emit_ok({"dataset_id": ctx.dataset_id, **result}, output, None)


@history.command("adopt")
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
def history_adopt(roots: tuple[str, ...], output: str, no_input: bool) -> None:
    """Миграция: снимок текущего состояния как базовая линия журнала."""
    ctx = _contexts(roots)[0]
    payload = ctx.ensure_index()
    files = [{"path": d["path"], "hash": d["hash"]} for d in payload["documents"]]
    result = history_adopt_run(ctx.root, files)
    _emit_ok({"dataset_id": ctx.dataset_id, **result}, output, None)


@history.command("export")
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
@click.option("--to", "destination", required=True)
def history_export(roots: tuple[str, ...], output: str, no_input: bool, destination: str) -> None:
    """Бэкап истории для бэкенда embedded."""
    ctx = _contexts(roots)[0]
    target = Path(destination)
    if not target.is_absolute():
        target = ctx.root / target
    if not is_within_root(ctx.root, target):
        raise AccessError("--to указывает вне DATA_ROOT", "access.outside_data_root")
    result = history_export_run(ctx.root, target)
    _emit_ok({"dataset_id": ctx.dataset_id, **result}, output, None)


@cli.group()
@click.pass_context
def change(ctx: click.Context) -> None:
    """Записи изменений: жизненный цикл, проверка применимости, bundle-применение."""


def _descriptor_lookup(ctx: Any):
    """Описатель doc_type для пробной проверки структуры после применения дельты."""
    payload = ctx.ensure_index()

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


@change.command("list")
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
@click.option("--status", default=None)
def change_list(roots: tuple[str, ...], output: str, no_input: bool, status: str | None) -> None:
    """Список изменений; --status фильтрует по состоянию жизненного цикла."""
    ctx = _contexts(roots)[0]
    items = list_changes(ctx.root, status)
    _emit_ok({"dataset_id": ctx.dataset_id, "total": len(items),
              "items": [{k: v for k, v in i.items() if k != "baseline"} for i in items]}, output, None)


@change.command("open")
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
@click.option("--title", required=True)
@click.option("--blocked-by", multiple=True)
@click.option("--artifact", multiple=True)
def change_open(roots: tuple[str, ...], output: str, no_input: bool, title: str,
                blocked_by: tuple[str, ...], artifact: tuple[str, ...]) -> None:
    """Открывает изменение и снимает базовую линию: хеши артефактов и диагностики."""
    ctx = _contexts(roots)[0]
    _folders, _docs, _records, _relations, diagnostics = ctx.scan_and_validate()
    baseline = {"artifacts": {a: file_hash(ctx.root / a) if (ctx.root / a).is_file() else ""
                              for a in artifact},
                "diagnostics": sorted(f"{d['code']}:{d['path']}" for d in diagnostics)}
    record = open_change(ctx.root, title, blocked_by=blocked_by, artifacts=artifact,
                         baseline=baseline, history=ctx.history_recorder(change_id_for(title)))
    _emit_ok({"dataset_id": ctx.dataset_id, "change_id": record["record_id"],
              "path": str(record_path(ctx.root, record["record_id"]).relative_to(ctx.root)),
              "status": record["status"], "artifacts": record["artifacts"],
              "next": "положите дельты в changes/<id>/deltas/*.md"}, output, None)


@change.command("show")
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
@click.argument("change_id")
def change_show(roots: tuple[str, ...], output: str, no_input: bool, change_id: str) -> None:
    """Запись изменения и её дельты."""
    ctx = _contexts(roots)[0]
    record = load_change(ctx.root, change_id)
    if record is None:
        raise TodocError(f"Изменение не найдено: {change_id}", EXIT_INCOMPLETE, "change.not_found")
    deltas = collect_deltas(ctx.root, change_id)
    _emit_ok({"dataset_id": ctx.dataset_id, "record": record,
              "deltas": [{"path": d["path"], "target": d["target"], "base_hash": d["base_hash"],
                          "order": d["order"],
                          "ops": [{"op": o["op"], "anchor": o["anchor"]} for o in d["ops"]]}
                         for d in deltas]}, output, None)


@change.command("validate")
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
@click.argument("change_id")
def change_validate(roots: tuple[str, ...], output: str, no_input: bool, change_id: str) -> None:
    """Применимость дельт к живому состоянию: цель, якорь, base_hash, структура после."""
    ctx = _contexts(roots)[0]
    diagnostics = validate_change(ctx.root, change_id, ctx.dataset_id, _descriptor_lookup(ctx))
    errors = [d for d in diagnostics if d.severity == "error"]
    _emit_ok({"dataset_id": ctx.dataset_id, "change_id": change_id,
              "applicable": not errors, "errors": len(errors),
              "warnings": len(diagnostics) - len(errors)}, output, None,
             diagnostics=[d.to_dict() for d in diagnostics])


@change.command("verify")
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
@click.argument("change_id")
def change_verify(roots: tuple[str, ...], output: str, no_input: bool, change_id: str) -> None:
    """Completeness / correctness / coherence — детерминированно, без модели."""
    ctx = _contexts(roots)[0]
    result = verify_change(ctx.root, change_id)
    if not result.get("found"):
        raise TodocError(f"Изменение не найдено: {change_id}", EXIT_INCOMPLETE, "change.not_found")
    _emit_ok({"dataset_id": ctx.dataset_id, **result}, output, None)


@change.command("apply")
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
@click.argument("change_id")
@click.option("--apply", "apply_", is_flag=True)
@click.option("--if-hash", multiple=True, help="PATH=sha256:… — отказ, если файл ушёл.")
def change_apply(roots: tuple[str, ...], output: str, no_input: bool, change_id: str,
                 apply_: bool, if_hash: tuple[str, ...]) -> None:
    """Bundle-транзакция: без --apply показывает план, с --apply пишет всё или ничего."""
    ctx = _contexts(roots)[0]
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
                          expected_hashes=expected)
    if result.get("applied"):
        ctx.ensure_index()
    # Диагностики плана обязаны попасть в конверт: без них отказ «applied: false»
    # необъясним, и агент не узнает, что именно мешает применить изменение.
    payload = {"dataset_id": ctx.dataset_id, **result}
    diagnostics = [d for d in (result.get("diagnostics") or []) if isinstance(d, dict)]
    _emit_ok({k: v for k, v in payload.items() if k != "diagnostics"}, output, None,
             diagnostics=diagnostics)


@change.command("archive")
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
@click.argument("change_id")
@click.option("--tag", default=None)
def change_archive(roots: tuple[str, ...], output: str, no_input: bool, change_id: str,
                   tag: str | None) -> None:
    """Закрывает изменение; --tag ставит метку истории на последнее событие."""
    ctx = _contexts(roots)[0]
    result = archive_change(ctx.root, change_id, tag, ctx.root,
                            history=ctx.history_recorder(change_id))
    _emit_ok({"dataset_id": ctx.dataset_id, **result}, output, None)


@change.command("revert")
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
@click.argument("change_id")
@click.option("--apply", "apply_", is_flag=True)
def change_revert(roots: tuple[str, ...], output: str, no_input: bool, change_id: str,
                  apply_: bool) -> None:
    """Откат применения к базовой линии изменения. Без --apply — только план."""
    ctx = _contexts(roots)[0]
    result = revert_change(ctx.root, change_id, apply=apply_,
                           history=ctx.history_recorder(change_id))
    if result.get("applied"):
        ctx.ensure_index()
    _emit_ok({"dataset_id": ctx.dataset_id, **result}, output, None)


@cli.command("context")
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
@click.option("--change", "change_id", default=None)
@click.option("--tag", default=None)
@click.option("--budget", type=int, default=8000, show_default=True)
@click.option("--with-diff", is_flag=True)
def context_cmd(roots: tuple[str, ...], output: str, no_input: bool, change_id: str | None,
                tag: str | None, budget: int, with_diff: bool) -> None:
    """Весь контекст задачи одним вызовом, в пределах бюджета байт."""
    ctx = _contexts(roots)[0]
    if not change_id and not tag:
        raise TodocError("Нужен --change или --tag", EXIT_USAGE, "usage.error")
    limits = ctx.dataset.get("limits") or {}
    max_diff_lines = limits.get("max_diff_lines")
    result = build_context(ctx.root, ctx.dataset_id, change_id=change_id, tag=tag,
                           budget=budget, with_diff=with_diff,
                           max_diff_lines=max_diff_lines if isinstance(max_diff_lines, int) else None)
    _emit_ok({"dataset_id": ctx.dataset_id, **result}, output, None)


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


def _write_whole(root: Path, rel_path: str, text: str, expected_hash: str | None, *,
                 history: Any, basis: str) -> str:
    """Запись файла целиком с обязательной записью события: молчаливых правок не бывает."""
    target = root / rel_path
    if expected_hash is not None:
        actual = file_hash(target) if target.is_file() else ""
        if actual != expected_hash:
            raise ConflictError(f"Hash mismatch for {rel_path}", "write.hash_mismatch")
    before = target.read_bytes() if target.is_file() else None
    atomic_write(target, text)
    history.record(rel_path, before, text.encode("utf-8"), "doc.edit", basis)
    return file_hash(target)


@cli.command("explain-path")
@click.argument("path")
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
def explain_path(path: str, roots: tuple[str, ...], output: str, no_input: bool) -> None:
    """Show resolved type/rule for a path — документы И папки (с .config.json-метой предка)."""
    for ctx in _contexts(roots):
        folders, documents, _r, _rel, _d = ctx.scan_and_validate()
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
            _emit_ok({"dataset_id": ctx.dataset_id, "path": path, "folder": True,
                      "dir_type": fm["dir_type"], "rule_source": fm["rule_source"],
                      **_ancestor_fields(path)}, output, None)
            return
        for doc in documents:
            if doc["path"] == path:
                _emit_ok({"dataset_id": ctx.dataset_id, "path": path, "doc_type": doc["doc_type"],
                          "format": doc["format"], "rule_source": doc["rule_source"], "document_id": doc["document_id"],
                          **_ancestor_fields(path)},
                         output, None)
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
    apply_write_plan(ctx.root, plan, history=ctx.history_recorder())
    ctx.ensure_index()
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
    payload = ctx.ensure_index()
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
    payload = ctx.ensure_index()
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
            if budget is not None:
                # BUG-005: --budget ограничивает окно секции в байтах вместо молчаливого игнора
                window: list[str] = []
                used = 0
                for ln in section_lines:
                    cost = len(ln.encode("utf-8")) + 1
                    if window and used + cost > budget:
                        break
                    window.append(ln)
                    used += cost
            else:
                window = section_lines[:SECTION_MAX_LINES]
            data["section"] = selected.title
            data["heading_path"] = heading_path_for(md.headings, selected_index)
            data["line_start"] = selected.line
            data["line_end"] = selected.line + len(window) - 1
            data["lines"] = window
            data["section_total_lines"] = len(section_lines)
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
        # Сначала отбор, потом окно: --rows 3 --where k=v должен вернуть три
        # подходящие строки, а не три первые с последующей фильтрацией (P1-5).
        selected_rows = csv_doc.rows
        if where:
            key, _, val = where.partition("=")
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
    _emit_ok(data, output, None)


@docs.command("suggest")
@click.option("--root", "roots", multiple=True)
@click.option("--query", "q", required=True, help="Запрос: куда положить/где искать (кириллица работает).")
@click.option("--limit", type=int, default=5, show_default=True)
@click.option("--output", type=click.Choice(["json", "table"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
def docs_suggest(roots: tuple[str, ...], q: str, limit: int, output: str, no_input: bool) -> None:
    """Куда положить/где искать: скоринг папок по .config.json (Фаза A, детерминированно)."""
    ctx = _contexts(roots)[0]
    if not q.strip():
        raise TodocError("Пустой запрос: укажите --query.", EXIT_USAGE, "usage.error")
    folder_configs, _cfg_diags = load_folder_configs(ctx.root)
    candidates, discarded = score_folder_configs(folder_configs, q)
    truncated = len(candidates) > limit
    candidates = candidates[:limit]
    _emit_ok({"query": q, "threshold": 0.25, "truncated": truncated,
              "candidates": candidates, "discarded": discarded},
             output, None,
             next_actions=[{"argv": _root_argv(roots) + ["docs", "new", "--dir", "<путь из кандидатов>"],
                            "purpose": "Создать документ в выбранной папке"},
                           {"argv": _root_argv(roots) + ["explain-path", "<путь из кандидатов>"],
                            "purpose": "Объяснить выбранную папку (dir_type + мета)"}])


@docs.command("links")
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table"]), default="json", show_default=True)
@click.option("--limit", type=int, default=20, show_default=True)
@click.option("--no-input", is_flag=True)
def docs_links(roots: tuple[str, ...], output: str, no_input: bool, limit: int) -> None:
    """Инвентаризация локальных ссылок: total/broken (BUG-007, тот же резолв, что в validate)."""
    ctx = _contexts(roots)[0]
    _folders, documents, _r, _rel, _diags = ctx.scan_and_validate()
    paths = {d["path"] for d in documents}
    by_basename, _basenames = _basename_index(paths)
    total = broken = 0
    items: list[dict[str, Any]] = []
    for d in documents:
        if d.get("format") != "markdown":
            continue
        fpath = ctx.root / d["path"]
        try:
            text = fpath.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for link in parse_markdown(text).links:
            if link.is_wikilink:
                if not link.target:
                    continue
                kind = "wikilink"
                ok = bool(_wikilink_candidates(link.target, by_basename))
            else:
                normalized = resolve_link_target(d["path"], link.target)
                if normalized is None:
                    continue  # внешние/якорные — не локальный граф
                kind = "md"
                ok = normalized in paths
            total += 1
            if not ok:
                broken += 1
                items.append({"path": d["path"], "target": link.target,
                              "kind": kind, "line": link.line})
    truncated = broken > limit
    items = items[:limit]
    _emit_ok({"total": total, "broken": broken, "items": items, "truncated": truncated},
             output, None)


@docs.command("tree")
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
@click.option("--within", default=None)
@click.option("--max-depth", type=int, default=3)
@click.option("--match", "match_q", default=None,
              help="Фильтр папок Фазой A скоринга (.config.json): score ≥ 0.25, порядок score → order → путь.")
def docs_tree(roots: tuple[str, ...], output: str, no_input: bool, within: str | None,
              max_depth: int, match_q: str | None) -> None:
    """Compact derived outline (folders + documents)."""
    ctx = _contexts(roots)[0]
    payload = ctx.ensure_index()
    folders = [dict(f) for f in payload["folders"]]
    documents = payload["documents"]
    if within:
        folders = [f for f in folders if f["path"] == within or f["path"].startswith(within.rstrip("/") + "/")]
        documents = [d for d in documents if d["path"] == within or d["path"].startswith(within.rstrip("/") + "/")]
    folder_configs, _cfg_diags = load_folder_configs(ctx.root)
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
    payload = ctx.ensure_index()
    doc = next((d for d in payload["documents"] if d["document_id"] == doc_id), None)
    if doc is None:
        raise ValidationError(f"Document not found: {doc_id}", "docs.not_found")
    try:
        patch_text = Path(patch_file).read_text(encoding="utf-8")
    except OSError as exc:
        # P11: отсутствующий --patch-file — ошибка контракта, а не трейсбек интерпретатора.
        raise TodocError(f"Не удалось прочитать --patch-file {patch_file}: {exc}",
                         EXIT_USAGE, "usage.error") from exc
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
    new_hash = apply_edit_ops(ctx.root, doc["path"], ops, expected_hash=if_hash,
                             history=ctx.history_recorder())
    ctx.ensure_index()
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
def records_create(roots: tuple[str, ...], output: str, no_input: bool, entity_type: str, input_file: str,
                   preview: bool, apply_: bool) -> None:
    """Create-only new JSON record (preview default)."""
    ctx = _contexts(roots)[0]
    payload = ctx.ensure_index()
    record = load_input_record(Path(input_file))
    if record.get("entity_type") != entity_type:
        record["entity_type"] = entity_type
    existing_ids = {r["record_id"] for r in payload["records"]}
    existing_paths = {d["path"] for d in payload["documents"]}
    schema = _record_schema(ctx, entity_type)
    plan = create_record_plan(ctx.dataset, ctx.registry_types.entity_types, record, existing_ids, existing_paths,
                              schema)
    # Флага --if-hash-new больше нет (P1-4): он обещал проверку, которую команда и так
    # выполняет безусловно — create_record_plan отказывает занятому пути, а
    # apply_write_plan повторно проверяет цель в момент записи. Флаг, намекающий, что
    # гарантия включается по желанию, был дефектом, а не возможностью.
    if not apply_:
        _emit_ok({"dataset_id": ctx.dataset_id, "preview": True, "plan": plan.to_dict()}, output, None)
        return
    new_hash = apply_write_plan(ctx.root, plan, history=ctx.history_recorder())
    ctx.ensure_index()
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
    payload = ctx.ensure_index()
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
@click.option("--as-of", "as_of", default=None, help="Только записи, бывшие правдой на этот момент.")
def records_query(roots: tuple[str, ...], output: str, no_input: bool, query_file: str,
                  as_of: str | None) -> None:
    """Run a saved declarative QuerySpec."""
    ctx = _contexts(roots)[0]
    payload = ctx.ensure_index()
    try:
        spec = json.loads(Path(query_file).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValidationError(f"Invalid query file: {exc}", "query.invalid_file") from exc
    try:
        items, total, truncated = query_records(payload["records"], spec.get("entity_type"),
                                                spec.get("filters"), int(spec.get("limit", 200)),
                                                as_of=as_of)
    except InvalidInstant as exc:
        raise ValidationError(str(exc), "temporal.invalid_instant") from exc
    _emit_ok({"dataset_id": ctx.dataset_id, "as_of": as_of, "total": total, "truncated": truncated,
              "items": items}, output, None)


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
    payload = ctx.ensure_index()
    resolved_type = entity_type or "workout"
    # metric_fields.<f> несёт промпт и единицу; вычисляемой формулы в типе нет (P1-11),
    # поэтому объявленный промпт просто доходит до ответа вместе с тем, что ядро посчитало.
    descriptor = _entity_types_of(ctx.registry_types).get(resolved_type) or {}
    metric_fields = descriptor.get("metric_fields")
    spec = metric_fields.get(metric) if isinstance(metric_fields, dict) else None
    result = aggregate_records(payload["records"], resolved_type, metric, group_by,
                               metric_spec=spec if isinstance(spec, dict) else None)
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
    payload = ctx.ensure_index()
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
    payload = ctx.ensure_index()
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
    new_hash = apply_fix(ctx.root, rel_path, old_target, new_target, expected_hash=if_hash,
                         history=ctx.history_recorder())
    ctx.ensure_index()
    _emit_ok({"dataset_id": ctx.dataset_id, "diagnostic": diagnostic, "applied": True, "new_hash": new_hash}, output, None)


@cli.command("doctor")
@click.option("--root", "roots", multiple=True)
@click.option("--output", type=click.Choice(["json", "table", "markdown"]), default="json", show_default=True)
@click.option("--no-input", is_flag=True)
@click.option("--check", default=None, help="Comma-separated check ids.")
@click.option("--scope", default=None, help="Группа проверок: dataset | environment | all.")
@click.option("--fix", "fix_", is_flag=True, help="Separate repair mode (dry-run by default).")
def doctor(roots: tuple[str, ...], output: str, no_input: bool, check: str | None, scope: str | None, fix_: bool) -> None:
    """Read-only environment diagnostics (stable IDs, never auto-repairs)."""
    wanted = {c.strip() for c in check.split(",")} if check else None
    # --scope раньше принимался и игнорировался (P1-4): `--scope nonsense` выполнял
    # все проверки. Теперь он отбирает группу, а неизвестное значение — ошибка вызова,
    # а не молчаливый полный прогон.
    if scope is not None and scope not in DOCTOR_SCOPES:
        raise TodocError(f"--scope ожидает одно из {', '.join(sorted(DOCTOR_SCOPES))}, получено {scope!r}",
                         EXIT_USAGE, "usage.error")
    reports = []
    for ctx in _contexts(roots):
        checks = [
            ("config", True, "Dataset config loads."),
            ("index", ctx.store.current_generation_id() is not None, "Index generation is current."),
            ("python", True, f"Python {sys.version.split()[0]}."),
        ]
        if scope is not None and scope != "all":
            allowed = DOCTOR_SCOPES[scope]
            checks = [c for c in checks if c[0] in allowed]
        if wanted:
            checks = [c for c in checks if c[0] in wanted]
        passed = sum(1 for _id, ok, _msg in checks if ok)
        reports.append({"dataset_id": ctx.dataset_id, "scope": scope or "all",
                        "checks_total": len(checks), "passed": passed,
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
        if payload:
            reports.append({"dataset_id": ctx.dataset_id, "index_built": True,
                            "generation_id": payload.get("generation_id"),
                            "documents": len(payload["documents"]),
                            "records": len(payload["records"])})
        else:
            # P1-6: нули до первой пересборки читались как «в датасете ничего нет».
            # Честный ответ — «ещё не измерено» (null), а не выдуманное число.
            reports.append({"dataset_id": ctx.dataset_id, "index_built": False,
                            "generation_id": None, "documents": None, "records": None})
    next_actions = ([{"action": "todoc index rebuild",
                     "reason": "Индекс ещё не опубликован: считать документы не по чему."}]
                    if any(not r["index_built"] for r in reports) else None)
    _emit_ok({"datasets": reports}, output, None, next_actions=next_actions)


DOCTOR_SCOPES = {"dataset": ("config", "index"), "environment": ("python",),
                 "all": ("config", "index", "python")}


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
