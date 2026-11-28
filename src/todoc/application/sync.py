"""Post-direct-edit finalization service (`todoc sync`).

Pure application module: no ``click`` imports and no direct console I/O.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any

from todoc.adapters.filesystem.scanner import atomic_write, file_hash
from todoc.adapters.formats.markdown import parse_markdown
from todoc.application.history import open_backend, record_write
from todoc.application.validator import stable_id
from todoc.application.write import bump_front_matter_updated
from todoc.errors import AccessError, ConflictError, ValidationError
from todoc.typing_system.resolver import resolve_type

if TYPE_CHECKING:  # pragma: no cover
    from todoc.service import DatasetContext

GENERATED_MARKER = "<!-- СГЕНЕРИРОВАНО:"


def normalize_sync_path(root: Path, raw_path: str, cwd: Path | None = None) -> str:
    """Resolve ``raw_path`` (root-relative, cwd-relative, or absolute) inside ``DATA_ROOT``."""
    cleaned = raw_path.strip()
    if not cleaned:
        raise ValidationError("Empty sync path is not allowed.", "sync.empty_path")
    base = root.resolve()
    work_dir = (cwd or Path.cwd()).resolve()
    raw = Path(cleaned)

    if raw.is_absolute():
        resolved = raw.resolve()
    else:
        cwd_candidate = (work_dir / raw).resolve()
        if base in cwd_candidate.parents:
            resolved = cwd_candidate
        else:
            resolved = (base / raw).resolve()

    if resolved == base:
        raise ValidationError("Sync path must point to a file inside DATA_ROOT, not DATA_ROOT itself.",
                              "sync.root_path")
    if base not in resolved.parents:
        raise AccessError(f"Path must stay inside DATA_ROOT ({base}): {raw_path}", "access.outside_data_root")

    rel = resolved.relative_to(base).as_posix()
    if rel.split("/", 1)[0] == ".todoc":
        raise ValidationError(f"Internal .todoc path cannot be synced as a data file: {rel}", "sync.internal_path")
    return rel


def _indexed_hashes(ctx: "DatasetContext") -> dict[str, str]:
    current = ctx.load_published_index()
    docs = (current or {}).get("documents") or []
    return {str(d["path"]): str(d["hash"]) for d in docs if "path" in d and "hash" in d}


def detect_dirty_paths(ctx: "DatasetContext") -> list[str]:
    """Return sorted relative paths of created, modified, or deleted data files."""
    indexed = _indexed_hashes(ctx)
    _, scanned_files = ctx.scan()
    scanned = {f.rel_path: f.hash for f in scanned_files}
    dirty = [p for p, h in scanned.items() if indexed.get(p) != h]
    dirty.extend(p for p in indexed if p not in scanned)
    return sorted(set(dirty))


def _journal_hashes(events: list[dict[str, Any]]) -> dict[str, str]:
    hashes = {}
    for event in events:
        if event.get("kind") == "external.change":
            continue
        for item in event.get("paths") or []:
            if item.get("path") and item.get("after"):
                hashes[str(item["path"])] = str(item["after"])
    return hashes


def _previous_hash_and_bytes(rel_path: str, indexed: dict[str, str], journal_hash: str | None,
                             backend: Any, record_history: bool) -> tuple[str | None, bytes | None]:

    head = backend.head()
    before_bytes = backend.read_at(head, rel_path) if head else None
    if journal_hash is not None:
        return journal_hash, before_bytes
    if before_bytes is not None and record_history:
        return "sha256:" + hashlib.sha256(before_bytes).hexdigest(), before_bytes
    return indexed.get(rel_path), before_bytes


def _extract_derived_sources(fm: dict[str, Any]) -> list[str]:
    raw = fm.get("derived_from")
    if not isinstance(raw, list):
        return []
    return [entry.strip() for entry in raw if isinstance(entry, str) and entry.strip()]


def _is_generated_view(ctx: "DatasetContext", rel_path: str, text: str) -> tuple[bool, list[str]]:
    parsed = parse_markdown(text)
    fm = parsed.front_matter if isinstance(parsed.front_matter, dict) else {}
    doc_type, _, _ = resolve_type(ctx.doc_rules, rel_path, Path(rel_path).name, fm, "doc_type", {}, "unknown")
    descriptor = ctx.registry_types.doc_types.get(doc_type) or {}

    sources = _extract_derived_sources(fm)
    is_gen = bool(
        descriptor.get("generated") is True
        or fm.get("generated") is True
        or any(line.startswith(GENERATED_MARKER) for line in text.splitlines())
        or (doc_type == "flow-doc" and "derived_from" in fm)
    )
    return is_gen, sources


def sync_files(
    ctx: "DatasetContext",
    raw_paths: Sequence[str] = (),
    *,
    dirty: bool = False,
    expected_hash: str | None = None,
    allow_derived: bool = False,
    record_history: bool = True,
    cwd: Path | None = None,
    apply: bool = True,
) -> dict[str, Any]:
    """Synchronize directly edited files: bump ``updated``, record history, refresh index & validate."""
    indexed = _indexed_hashes(ctx)
    if raw_paths:
        targets = list(dict.fromkeys(normalize_sync_path(ctx.root, p, cwd=cwd) for p in raw_paths))
    else:
        targets = detect_dirty_paths(ctx)

    if expected_hash is not None and len(targets) != 1:
        raise ValidationError("--if-hash requires exactly one target path.", "sync.if_hash_multi_target")

    backend, _ = open_backend(ctx.root, ctx.dataset)
    store = ctx.history_store
    hashes = _journal_hashes(store.read_events(strict=True))
    synced_items: list[dict[str, Any]] = []
    blocked_diags: list[dict[str, Any]] = []
    blocked_sources: list[str] = []
    any_mutated = False

    for rel_path in targets:
        target = ctx.root / rel_path
        prev_hash, before_bytes = _previous_hash_and_bytes(rel_path, indexed, hashes.get(rel_path), backend, record_history)

        if not target.is_file():
            if expected_hash is not None and prev_hash != expected_hash:
                raise ConflictError(f"Hash mismatch for deleted {rel_path}: expected {expected_hash}",
                                    "write.hash_mismatch")
            if apply:
                ctx.parse_cache.invalidate(rel_path)
                if record_history:
                    record_write(ctx.root, rel_path, before_bytes, b"", kind="file.delete",
                                 actor="cli", basis="todoc sync", backend=backend, store=store)
            synced_items.append({"path": rel_path, "status": "deleted", "hash": None, "updated_bumped": False})
            any_mutated = True
            continue

        disk_hash = file_hash(target)
        if expected_hash is not None and expected_hash not in (disk_hash, prev_hash):
            raise ConflictError(
                f"Hash mismatch for {rel_path}: expected {expected_hash}, got {disk_hash}",
                "write.hash_mismatch",
            )

        if prev_hash == disk_hash:
            synced_items.append({"path": rel_path, "status": "unchanged", "hash": disk_hash, "updated_bumped": False})
            continue

        is_md = target.suffix.lower() == ".md"
        text = target.read_text(encoding="utf-8") if is_md else ""
        if is_md and not allow_derived:
            is_gen, sources = _is_generated_view(ctx, rel_path, text)
            if is_gen:
                blocked_sources.extend(s for s in sources if s not in blocked_sources)
                blocked_diags.append({
                    "dataset_id": ctx.dataset_id,
                    "id": stable_id(rel_path, "docs.derived_edited_directly", rel_path),
                    "code": "docs.derived_edited_directly",
                    "severity": "error",
                    "path": rel_path,
                    "location": {},
                    "evidence": "",
                    "message": (
                        f"Автособираемая витрина {rel_path} изменена напрямую: "
                        "правьте исходную запись из derived_from и пересоберите витрину "
                        "(или передайте --allow-derived)."
                    ),
                    "suggested_fixes": [],
                })
                synced_items.append({"path": rel_path, "status": "blocked", "hash": disk_hash, "updated_bumped": False})
                continue

        new_text, updated_bumped = bump_front_matter_updated(text) if is_md else ("", False)
        planned_hash = "sha256:" + hashlib.sha256(new_text.encode("utf-8")).hexdigest() if updated_bumped else disk_hash
        if apply:
            if updated_bumped:
                atomic_write(target, new_text)
            ctx.parse_cache.invalidate(rel_path)
            if record_history:
                kind = "doc.sync" if is_md else "record.sync"
                record_write(ctx.root, rel_path, before_bytes, target.read_bytes(), kind=kind,
                             actor="cli", basis="todoc sync", backend=backend, store=store)
        synced_items.append({
            "path": rel_path,
            "status": "synced",
            "hash": planned_hash,
            "current_hash": disk_hash,
            "updated_bumped": updated_bumped,
        })
        any_mutated = True

    if apply:
        if any_mutated or ctx.load_published_index() is None:
            ctx.rebuild_index(force=True, observe=record_history)
        published = ctx.load_published_index() or {}
    else:
        published = ctx.read_index(include_mentions=False)
    target_set = set(targets)
    index_diags = [
        d for d in (published.get("diagnostics") or [])
        if str(d.get("path") or "") in target_set
    ]
    all_diags = blocked_diags + index_diags
    has_errors = any(d.get("severity", "error") == "error" for d in all_diags)

    guidance: dict[str, Any] | None = None
    if blocked_diags:
        guidance = {
            "code": "sync.derived_view_blocked",
            "summary": "Файл является автособираемой витриной: ручные правки перезатрутся при следующей пересборке.",
            "sources": blocked_sources,
            "fix_hint": (
                "Откатите ручную правку витрины, отредактируйте исходную запись из sources, "
                "запустите todoc sync --apply на ней и пересоберите витрину командой render/export --write "
                "(либо передайте --allow-derived, если правка осознанная)."
            ),
        }
    elif has_errors:
        first = next(d for d in all_diags if d.get("severity", "error") == "error")
        guidance = {
            "code": "sync.validation_failed",
            "summary": f"Валидатор обнаружил ошибку [{first.get('code')}] в {first.get('path')}.",
            "fix_hint": str(first.get("message") or "Исправьте ошибку в файле и повторите todoc sync."),
        }

    return {
        "ok": not has_errors,
        "dataset_id": ctx.dataset_id,
        "synced": synced_items,
        "diagnostics": all_diags,
        "guidance": guidance,
    }
