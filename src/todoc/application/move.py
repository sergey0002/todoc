"""Review-first single-document moves. Sources, not a published index, are truth."""
from __future__ import annotations

import hashlib
from collections import Counter
import ntpath
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from todoc.adapters.filesystem.scanner import HARD_EXCLUDE_DIRS
from todoc.application.paging import selection_key
from todoc.application.write import portable_name, bump_front_matter_updated
from todoc.errors import AccessError, ConflictError, ValidationError, TodocError
from todoc.service import DatasetContext


def digest(data: bytes | None) -> str | None:
    return None if data is None else 'sha256:' + hashlib.sha256(data).hexdigest()


def today() -> str:
    return datetime.now(timezone.utc).strftime('%Y-%m-%d')


def checked_path(root: Path, raw: str, *, portable: bool = False) -> Path:
    """Check lexical AND physical components, including dangling symlinks."""
    parts = raw.split('/')
    if not raw or '\\' in raw or ntpath.splitdrive(raw)[0] or raw.startswith('/') or any(p in ('', '.', '..') for p in parts):
        raise AccessError('Use a DATA_ROOT-relative POSIX path without dot segments.', 'move.path_invalid')
    current = root
    for part in parts:
        if part in HARD_EXCLUDE_DIRS:
            raise AccessError('Reserved path component.', 'move.target_reserved')
        if portable and (portable_name(part) != part or part.rstrip(' .') != part):
            raise AccessError('Target name is not portable.', 'move.path_invalid')
        current = current / part
        if current.is_symlink():
            raise AccessError('Symlink path component.', 'move.target_symlink')
    return current


@dataclass(frozen=True)
class MoveFile:
    path: str
    before: bytes | None
    after: bytes | None


@dataclass(frozen=True)
class MovePlan:
    dataset_id: str
    source: str
    target: str
    old_id: str
    new_id: str
    corpus_digest: str
    planned_on: str
    options: dict[str, bool]
    files: tuple[MoveFile, ...]
    rewrites: dict[str, int]
    diagnostics: tuple[dict[str, Any], ...]
    new_stale: tuple[dict[str, Any], ...] = ()
    old_type: str = "unknown"
    new_type: str = "unknown"

    @property
    def plan_hash(self) -> str:
        return selection_key([1, self.dataset_id, self.source, self.target, self.old_id, self.new_id,
                              self.corpus_digest, self.planned_on, self.options,
                              [(f.path, digest(f.before), digest(f.after)) for f in self.files]])


def fresh_context(ctx: DatasetContext) -> DatasetContext:
    return DatasetContext(ctx.root, index_store=ctx.store, parse_cache=ctx.parse_cache, history_store=ctx.history_store)


def resolve_source(payload: dict, source: str | None, doc_id: str | None) -> dict:
    if (source is None) == (doc_id is None):
        raise TodocError('Choose exactly one of --id and --from.', 2, 'usage.error')
    docs = [d for d in payload['documents'] if (d['path'] == source if source is not None else d['document_id'] == doc_id)]
    if len(docs) != 1:
        raise ValidationError('Source missing or ambiguous.', 'move.source_ambiguous' if docs else 'move.source_not_found')
    doc = docs[0]
    if doc['format'] != 'markdown':
        raise ValidationError('Only Markdown documents can move.', 'move.source_not_markdown')
    if doc['status'] != 'ok':
        raise ValidationError('Source is not readable.', 'move.source_unreadable')
    if PurePosixPath(doc['path']).name == 'SKILL.md':
        raise ValidationError('Skills require a virtual vault scan.', 'move.source_unsupported')
    return doc


def resolve_target(root: Path, source: str, target: str) -> str:
    raw = target.rstrip('/')
    path = checked_path(root, raw, portable=True)
    if path.is_dir():
        raw += '/' + PurePosixPath(source).name
        path = checked_path(root, raw, portable=True)
    elif target.endswith('/'):
        raise ValidationError('Target directory missing.', 'move.target_dir_missing')
    if raw == source:
        raise TodocError('Source equals target.', 2, 'move.same_path')
    if raw.casefold() == source.casefold():
        raise ValidationError('Case-only renames are unsupported.', 'move.case_only_rename')
    if not path.parent.is_dir():
        raise ValidationError('Target directory missing.', 'move.target_dir_missing')
    if path.exists():
        raise ConflictError('Target already exists.', 'move.target_exists')
    if path.suffix != PurePosixPath(source).suffix:
        raise ValidationError('Keep the same Markdown extension.', 'move.extension_mismatch')
    return raw


def read_bytes(ctx: DatasetContext, doc: dict) -> bytes:
    path = checked_path(ctx.root, doc['path'])
    try:
        data = path.read_bytes()
        if digest(data) != doc['hash']:
            raise ConflictError('Source changed while planning.', 'move.hash_mismatch')
        data.decode('utf-8')
        return data
    except (OSError, UnicodeError) as exc:
        raise ValidationError(f'Cannot read {doc["path"]}.', 'move.source_unreadable') from exc


def plan_move(ctx: DatasetContext, *, source: str | None = None, doc_id: str | None = None,
              target: str, keep_id: bool = False, pin_type: bool = False) -> MovePlan:
    ctx = fresh_context(ctx)
    if source is not None:
        checked_path(ctx.root, source)
    payload = ctx.read_index()
    doc = resolve_source(payload, source, doc_id)
    if any(d['severity'] == 'error' for d in payload['diagnostics']):
        raise ValidationError('Fix dataset errors before moving.', 'move.baseline_invalid')
    source = doc['path']
    target = resolve_target(ctx.root, source, target)
    before = read_bytes(ctx, doc)
    from todoc.application.move_rewrite import rewrite_identity
    after, new_id = rewrite_identity(before.decode('utf-8'), doc, target, keep_id, pin_type)
    after = bump_front_matter_updated(after)[0].encode('utf-8')
    from todoc.application.move_rewrite import rewrite_corpus, warning
    files, counts, findings = rewrite_corpus(ctx, payload, source, target, doc['document_id'], new_id, after)
    if pin_type and doc['doc_type'] == 'unknown':
        findings += (warning('move.pin_type_unavailable', source),)
    virtual = validate_files(ctx, files)
    before_stale = stale_findings(ctx, payload, {}, set())
    overlay = {f.path: f.after for f in files if f.after is not None}
    deleted = {f.path for f in files if f.after is None}
    after_stale = stale_findings(ctx, virtual, overlay, deleted)
    def stale_key(d):
        # Identity includes each dependency and its expected hash, not merely
        # owner+code; otherwise a second stale dependency is silently hidden.
        anchor = d['evidence'].split(' ожидался ')[0]
        head, _, expected = anchor.rpartition('@')
        if head == source or head.startswith(source + '#'):
            head = target + head[len(source):]
        return (target if d['path'] == source else d['path'], d['code'], head, expected)
    existing = Counter(stale_key(d) for d in before_stale)
    added = []
    for diagnostic in after_stale:
        key = stale_key(diagnostic)
        if existing[key]:
            existing[key] -= 1
        else:
            added.append(diagnostic)
    new_stale = tuple(added)
    return MovePlan(ctx.dataset_id, source, target, doc['document_id'], new_id, payload['corpus_digest'],
                    today(), {'keep_id': keep_id, 'pin_type': pin_type}, files, counts, findings, new_stale, doc['doc_type'],
                    next(d['doc_type'] for d in virtual['documents'] if d['path'] == target))


def virtual_scan(ctx: DatasetContext, files: tuple[MoveFile, ...]):
    from todoc.adapters.filesystem.scanner import ScannedFile, FORMAT_BY_SUFFIX
    folders, scanned = ctx.scan(strict=True)
    updated = {f.path: f for f in files}
    result = [f for f in scanned if f.rel_path not in updated]
    for f in files:
        if f.after is not None:
            result.append(ScannedFile(f.path, ctx.root / f.path, FORMAT_BY_SUFFIX[PurePosixPath(f.path).suffix.lower()],
                                      len(f.after), digest(f.after)))
    return folders, sorted(result, key=lambda f: f.rel_path)


def validate_files(ctx: DatasetContext, files: tuple[MoveFile, ...]) -> dict:
    overlay = {f.path: f.after for f in files if f.after is not None}
    deleted = {f.path for f in files if f.after is None}
    scanned = virtual_scan(ctx, files)
    folders, docs, records, relations, diags = ctx.scan_and_validate(
        scanned, write_cache=False, verify_sources=True, overlay=overlay, deleted=deleted)
    if any(d['severity'] == 'error' for d in diags):
        raise ValidationError('Virtual state is invalid: ' + '; '.join(d['code'] + ':' + d['path'] for d in diags),
                              'move.validation_failed')
    mentions = ctx.build_mentions(scanned, records, folders, docs, verify_sources=True, overlay=overlay, deleted=deleted)
    return {'documents': docs, 'records': records, 'relations': relations, 'mentions': mentions, 'diagnostics': diags}


def stale_findings(ctx, payload, overlay, deleted):
    from todoc.application.staleness import check_owner, fragment_hash, fragment_hash_text
    def reader(root, dep):
        path = dep.get('path')
        if path in deleted:
            return None, 'missing'
        if path in overlay:
            return fragment_hash_text(overlay[path].decode('utf-8'), dep)
        return fragment_hash(root, dep)
    out = []
    for doc in payload['documents']:
        attrs = doc.get('attributes', {})
        if attrs.get('derived_from'):
            out.extend(d.to_dict() for d in check_owner(ctx.dataset_id, doc['path'], attrs, ctx.root, fragment_reader=reader))
    return out


class MoveFailure(TodocError):
    """An operation failure with explicit source-of-truth commit state."""
    def __init__(self, code: str, result: dict, message: str):
        super().__init__(message, 6, code)
        self.result = result


def _current(path: Path) -> bytes | None:
    return path.read_bytes() if path.exists() else None


def commit_files(ctx: DatasetContext, files: tuple[MoveFile, ...], *, kind: str,
                 change_id: str, reverts_rev: str | None = None) -> dict:
    """Caller owns move-lock. History publication is the only commit point."""
    from todoc.adapters.filesystem.scanner import atomic_write
    from todoc.application.history import _record_event_locked
    result = {'applied': False, 'committed': False, 'index_published': False, 'change_id': change_id}
    touched = []
    phase = 'write'
    with ctx.history_store.transaction():
        ctx.history_store.read_events(strict=True)
        for f in files:
            if _current(checked_path(ctx.root, f.path)) != f.before:
                raise ConflictError('Affected path changed.', 'move.hash_mismatch')
        try:
            # Publish the destination first, remove sources only after all writes.
            ordered = [f for f in files if f.after is not None] + [f for f in files if f.after is None]
            for f in ordered:
                path = checked_path(ctx.root, f.path)
                try:
                    if f.after is None:
                        path.unlink()
                    else:
                        atomic_write(path, f.after, exclusive=f.before is None)
                except FileExistsError:
                    # Never claim ownership of another writer's newly created file.
                    raise ConflictError('Target created concurrently.', 'move.target_exists')
                except BaseException:
                    touched.append(f)
                    raise
                touched.append(f)
            phase = 'history'
            entries = [{'path': f.path, 'before': f.before, 'after': f.after} for f in files]
            rev = _record_event_locked(ctx.root, entries, kind=kind, change_id=change_id,
                                       backend=ctx.history_recorder().backend, store=ctx.history_store,
                                       reverts_rev=reverts_rev)
        except (OSError, TodocError) as exc:
            failed = []
            for f in reversed(touched):
                try:
                    path = checked_path(ctx.root, f.path)
                    current = _current(path)
                    if current == f.before:
                        continue
                    if current != f.after:
                        failed.append(f.path)
                        continue
                    if f.before is None:
                        path.unlink()
                    else:
                        atomic_write(path, f.before, exclusive=current is None)
                except (OSError, TodocError):
                    failed.append(f.path)
            if failed:
                raise MoveFailure('move.rollback_failed', {**result, 'applied': None, 'recovery_required': True,
                                                           'recovery_paths': failed}, str(exc)) from exc
            if isinstance(exc, ConflictError):
                raise
            raise MoveFailure('move.history_failed' if phase == 'history' else 'move.write_failed', result, str(exc)) from exc
    result.update(applied=True, committed=True, rev=rev)
    try:
        for f in files:
            ctx.parse_cache.invalidate(f.path)
        index = ctx.rebuild_index(observe=False)
    except (OSError, TodocError) as exc:
        raise MoveFailure('move.index_failed', result, str(exc)) from exc
    return {**result, 'index_published': True, 'index': index}


def apply_move(ctx: DatasetContext, plan: MovePlan, *, if_plan_hash: str,
               if_hash: str | None = None) -> dict[str, Any]:
    from uuid import uuid4
    from todoc.adapters.filesystem.locks import directory_lock
    if not if_plan_hash:
        raise TodocError('Apply requires --if-plan-hash from preview.', 2, 'usage.error')
    with directory_lock(ctx.root / '.todoc/locks/move.lock'):
        live = fresh_context(ctx)
        payload = live.read_index()
        if (plan.dataset_id != live.dataset_id or plan.corpus_digest != payload['corpus_digest']
                or plan.planned_on != today() or plan.plan_hash != if_plan_hash):
            raise ConflictError('Preview is stale; request a new preview.', 'move.plan_stale')
        if any(d['severity'] == 'error' for d in plan.diagnostics):
            raise ValidationError('Cannot apply an invalid plan.', 'move.validation_failed')
        candidate = plan_move(live, source=plan.source, target=plan.target, **plan.options)
        if candidate.plan_hash != if_plan_hash:
            raise ConflictError('Plan differs from live computation.', 'move.plan_stale')
        before = next(f.before for f in candidate.files if f.path == plan.source)
        if if_hash is not None and digest(before) != if_hash:
            raise ConflictError('Source hash mismatch.', 'move.hash_mismatch')
        result = commit_files(live, candidate.files, kind='doc.move', change_id='move:' + uuid4().hex)
    return {**result, 'plan_hash': if_plan_hash, 'source': plan.source, 'target': plan.target,
            'old_id': plan.old_id, 'new_id': plan.new_id, 'rewrites': plan.rewrites,
            'new_stale': list(candidate.new_stale)}
