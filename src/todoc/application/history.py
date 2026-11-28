"""История: журнал событий записи, снимки «до» и откат.

Единица истории — **событие записи**, а не факт запуска команды. Все записи в проекте уже
проходят через три функции ``application/write.py``, и все три принимают ``expected_hash``,
поэтому один хук покрывает весь ввод.

Хронология одна — «как файл выглядел». Связь с задачей (``change_id``) и с релизом (``tag``)
хранится рядом, но не смешивается с ней: это разные вопросы (§2 плана).
"""

from __future__ import annotations

import difflib
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from todoc.adapters.filesystem.scanner import file_hash, is_within_root
from todoc.application.storage import HistoryStore
from todoc.composition import default_history_backend, default_history_store, open_history_backend
from todoc.domain.models import Diagnostic
from todoc.errors import AccessError, ConflictError, IncompleteError, TodocError

SCHEMA_VERSION = 1

JOURNAL_UNREADABLE = "history.journal_unreadable"
JOURNAL_TRUNCATED = "history.journal_truncated_line"
OBJECT_MISSING = "history.object_missing"
REVISION_UNKNOWN = "history.revision_unknown"
BACKEND_UNAVAILABLE = "history.backend_unavailable"


def _content_hash(content: bytes) -> str:
    return "sha256:" + hashlib.sha256(content).hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# --- конфигурация бэкенда ----------------------------------------------------


def configured_backend(dataset: dict[str, Any]) -> str | None:
    section = dataset.get("history")
    if isinstance(section, dict):
        value = section.get("backend")
        if isinstance(value, str) and value:
            return value
    return None


def open_backend(root: Path, dataset: dict[str, Any] | None) -> tuple[Any, str | None]:
    return open_history_backend(root, configured_backend(dataset or {}))


# --- запись события ----------------------------------------------------------


def changed_ranges(before: str, after: str) -> list[list[int]]:
    """Изменённые диапазоны строк (1-based, включительно).

    Без них невозможна лента по разделу: git даёт историю файла, но не раздела, а раздел —
    это диапазон строк.
    """
    ranges: list[list[int]] = []
    matcher = difflib.SequenceMatcher(None, before.splitlines(), after.splitlines(), autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        start = max(i1 + 1, 1)
        end = max(i2, start)
        ranges.append([start, end])
    return ranges


def record_write(root: Path, rel_path: str, before: bytes | None, after: bytes, *, kind: str,
                 actor: str = "cli", basis: str = "", change_id: str | None = None,
                 backend: Any | None = None, git_head: str | None = None,
                 extra: dict[str, Any] | None = None, store: HistoryStore | None = None) -> str | None:
    """Пишет одно событие записи. Возвращает ``rev`` или None, если журнал выключен.

    ``before is None`` означает создание файла: образа «до» не существует, и снимать его
    не нужно.
    """
    backend = backend or default_history_backend(root)
    storage = store if store is not None else default_history_store(root)
    with storage.transaction():
        head = git_head if git_head is not None else backend.head()

        before_ref: str | None = None
        if before is not None:
            last = _last_revision_for(storage, rel_path, strict=store is not None)
            if backend.needs_snapshot(rel_path, last):
                before_ref = storage.write_snapshot(before)

        entry: dict[str, Any] = {"path": rel_path,
                                 "before": before_ref,
                                 "after": _content_hash(after),
                                 "git_head": head}
        if before is not None:
            # decode(errors="replace") не падает на бинарных данных: диапазоны считаются по
            # заменённым символам, событие остаётся корректным для текстовых файлов.
            entry["ranges"] = changed_ranges(before.decode("utf-8", "replace"),
                                            after.decode("utf-8", "replace"))
        else:
            entry["ranges"] = []
            if store is not None:
                storage.read_events(strict=True)
        if extra:
            entry.update(extra)

        return storage.append_event({
            "schema_version": SCHEMA_VERSION, "at": _utc_now(), "kind": kind, "actor": actor,
            "change_id": change_id, "paths": [entry], "basis": basis,
        })


def _last_revision_for(store: HistoryStore, rel_path: str, *, strict: bool = False) -> str | None:
    last = None
    for event in store.read_events(strict=strict):
        for item in event.get("paths") or []:
            if isinstance(item, dict) and item.get("path") == rel_path:
                last = item.get("git_head")
    return last


# --- refs (head, tags) -------------------------------------------------------


def refs_path(root: Path) -> Path:
    return default_history_store(root).refs_path()


def read_refs(root: Path) -> dict[str, Any]:
    return default_history_store(root).read_legacy_refs()


def write_refs(root: Path, refs: dict[str, Any]) -> None:
    default_history_store(root).write_refs(refs)


def set_head(root: Path, rev: str) -> None:
    refs = read_refs(root)
    refs["head"] = rev
    write_refs(root, refs)


def add_tag(root: Path, name: str, rev: str, message: str = "", *,
            store: HistoryStore | None = None, expected_refs: dict[str, Any] | None = None) -> dict[str, Any]:
    storage = default_history_store(root) if store is None else store
    with storage.transaction():
        refs = read_refs(root) if store is None else storage.read_refs()
        if expected_refs is not None:
            if refs != expected_refs or not any(event["rev"] == rev for event in storage.read_events(strict=True)):
                raise ConflictError("History changed before writing the tag.", "write.hash_mismatch")
        refs["tags"][name] = {"rev": rev, "at": _utc_now(), "message": message}
        storage.write_refs(refs)
        return refs["tags"][name]


# --- чтение содержимого на ревизии -------------------------------------------


def content_at(root: Path, rev: str | None, rel_path: str, backend: Any | None = None, *,
                store: HistoryStore | None = None) -> tuple[bytes | None, str]:
    """Содержимое файла на ревизии ``rev``.

    Хранится только образ «до», поэтому содержимое на ревизии R — это образ «до» первого
    изменения после R, либо текущий файл, если изменений после R не было.
    """
    backend = backend or default_history_backend(root)
    storage = store if store is not None else default_history_store(root)
    events = storage.read_events(strict=store is not None) if rev is not None else []
    if rev is not None and not any(e.get("rev") == rev for e in events):
        # Неизвестная ревизия не должна молча выглядеть как «текущее содержимое»:
        # иначе опечатка в rev вернёт текущий файл и откат пройдёт незамеченным.
        return None, "revision_unknown"
    seen_rev = rev is None
    for event in events:
        if rev is not None and event.get("rev") == rev:
            seen_rev = True
            if any(item.get("path") == rel_path and item.get("after_exists") is False
                   for item in event.get("paths", [])):
                return None, "missing"
            continue
        if not seen_rev and rev is not None:
            continue
        for item in event.get("paths") or []:
            if not isinstance(item, dict) or item.get("path") != rel_path:
                continue
            if item.get("before_exists") is False:
                return None, "missing"
            before = item.get("before")
            if before:
                data = storage.read_snapshot(before)
                if data is None:
                    return None, "object_missing"
                return data, "ok"
            head = item.get("git_head")
            if head:
                data = backend.read_at(head, rel_path)
                if data is not None:
                    return data, "ok"
    target = root / rel_path
    if target.is_file():
        try:
            return target.read_bytes(), "ok"
        except OSError:
            return None, "unreadable"
    return None, "missing"


def relation_identity(edge: dict[str, Any]) -> tuple[str, str]:
    """Идентичность ребра = type_id + target.id (план entity-catalog З4, T3)."""
    target = edge.get("target") if isinstance(edge.get("target"), dict) else {}
    return (str(edge.get("type_id", "")), str(target.get("id", "")))


def previous_relation_state(root: Path, rel_path: str, pointer_index: int,
                            current_edge: dict[str, Any],
                            current_relations: list[Any], *, store: HistoryStore | None = None) -> dict[str, Any] | None:
    """Прежнее состояние ребра по журналу (план entity-catalog З4, T3).

    Скан событий файла новейшие→старейшие. Сначала поиск ребра с той же
    идентичностью: идентичное значение — ребро ещё не менялось, идём старше;
    отличающееся — прежнее значение. Если такой идентичности нет ни в одной
    версии, берём первую версию с отличающимся массивом relations: ребро на
    позиции N там — прежнее значение (ребро изменено), при коротком массиве —
    «ребро отсутствовало» (добавлено последней ревизией).

    None — журнал не даёт прежнего состояния (ревизий нет).
    """
    identity = relation_identity(current_edge)
    storage = default_history_store(root) if store is None else store
    for event in reversed(storage.read_events(strict=store is not None)):
        for item in event.get("paths") or []:
            if not isinstance(item, dict) or item.get("path") != rel_path or not item.get("before"):
                continue
            before = storage.read_snapshot(item["before"])
            if before is None:
                continue
            try:
                old = json.loads(before.decode("utf-8"))
            except (UnicodeDecodeError, ValueError):
                continue
            old_relations = old.get("relations") if isinstance(old, dict) else None
            if not isinstance(old_relations, list):
                old_relations = []
            for old_edge in old_relations:
                if isinstance(old_edge, dict) and relation_identity(old_edge) == identity:
                    if old_edge == current_edge:
                        break  # не менялось в этой версии — смотрим старше
                    return {"state": "value", "value": old_edge,
                            "rev": event.get("rev"), "at": event.get("at")}
            else:
                # идентичности нет: массив отличался — ребро на позиции
                # pointer_index в этой версии прежнее (или его не было).
                # (Массив, равный текущему, сюда не попадает: равенство массивов
                # означает совпадение ребра по идентичности, т.е. break выше.)
                value = old_relations[pointer_index] if pointer_index < len(old_relations) else None
                return {"state": "value" if value is not None else "absent",
                        "value": value, "rev": event.get("rev"), "at": event.get("at")}
    return None


def resolve_rev(root: Path, rev_or_tag: str, *, refs: dict[str, Any] | None = None) -> str | None:
    """Разрешает имя тега в ``rev``; сам ``rev`` возвращается как есть."""
    refs = read_refs(root) if refs is None else refs
    tag = (refs.get("tags") or {}).get(rev_or_tag)
    if isinstance(tag, dict) and tag.get("rev"):
        return str(tag["rev"])
    return rev_or_tag or None


# --- команды -----------------------------------------------------------------


def log(root: Path, *, path: str | None = None, section: str | None = None, kind: str | None = None,
        change_id: str | None = None, tag: str | None = None, since: str | None = None,
        until: str | None = None, limit: int = 20, cursor: int = 0,
        events: list[dict[str, Any]] | None = None,
        refs: dict[str, Any] | None = None) -> tuple[list[dict[str, Any]], int, bool]:
    if events is None:
        events = default_history_store(root).read_events()
    tag_rev = resolve_rev(root, tag, refs=refs) if tag else None
    selected: list[dict[str, Any]] = []
    for event in events:
        if kind and event.get("kind") != kind:
            continue
        if change_id and event.get("change_id") != change_id:
            continue
        if since and str(event.get("at") or "") < since:
            continue
        if until and str(event.get("at") or "") > until:
            continue
        if tag_rev and event.get("rev") != tag_rev:
            continue
        items = [i for i in (event.get("paths") or []) if isinstance(i, dict)]
        if path:
            items = [i for i in items if i.get("path") == path]
            if not items:
                continue
        if section and path:
            items = [i for i in items if _ranges_touch_section(root, path, section, i.get("ranges") or [])]
            if not items:
                continue
        selected.append({**event, "paths": items})
    selected.reverse()  # свежие первыми, как git log
    total = len(selected)
    window = selected[cursor : cursor + limit]
    return window, total, cursor + limit < total


def _ranges_touch_section(root: Path, rel_path: str, selector: str, ranges: list[Any]) -> bool:
    bounds = _section_bounds(root, rel_path, selector)
    if bounds is None:
        return False
    start, end = bounds
    for item in ranges:
        if isinstance(item, (list, tuple)) and len(item) == 2:
            if int(item[0]) <= end and int(item[1]) >= start:
                return True
    return False


def _section_bounds(root: Path, rel_path: str, selector: str) -> tuple[int, int] | None:
    """Границы раздела в текущем файле (1-based, включительно).

    Разбор делегирован ``markdown.section_bounds``: тот же механизм используют дельты,
    поэтому лента по разделу и якорь дельты не могут разойтись в понимании границ.
    """
    from todoc.adapters.formats.markdown import section_bounds

    target = root / rel_path
    if not target.is_file():
        return None
    try:
        text = target.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    return section_bounds(text, selector)


def before_content(root: Path, rev: str, rel_path: str, backend: Any | None = None, *,
                store: HistoryStore | None = None,
                events: list[dict[str, Any]] | None = None) -> tuple[bytes | None, str]:
    """Образ «до» конкретного события — то, что восстанавливает откат.

    Семантика намеренно расходится с ``content_at`` на один шаг и повторяет git:
    ``git show <c>:<path>`` показывает файл **на** коммите, а ``git revert <c>`` его
    **отменяет**. Поэтому ``show <rev>`` возвращает состояние после события, а
    ``revert <rev>`` — состояние до него.
    """
    backend = backend or default_history_backend(root)
    storage = store if store is not None else default_history_store(root)
    if events is None:
        events = storage.read_events(strict=store is not None)
    for event in events:
        if event.get("rev") != rev:
            continue
        for item in event.get("paths") or []:
            if not isinstance(item, dict) or item.get("path") != rel_path:
                continue
            if item.get("before_exists") is False:
                return None, "no_before"
            before = item.get("before")
            if before:
                data = storage.read_snapshot(before)
                return (data, "ok") if data is not None else (None, "object_missing")
            head = item.get("git_head")
            if head:
                data = backend.read_at(head, rel_path)
                if data is not None:
                    return data, "ok"
            # Событие создания файла: откатывать некуда, файла до него не было.
            return None, "no_before"
    return None, "revision_unknown"


def first_before(root: Path, rel_path: str, *, backend: Any | None = None,
                 store: HistoryStore | None = None,
                 events: list[dict[str, Any]] | None = None) -> tuple[bytes | None, str]:
    """Read the image before the earliest event for the path."""
    if events is None:
        storage = default_history_store(root) if store is None else store
        events = storage.read_events(strict=store is not None)
    for event in events:
        if any(isinstance(item, dict) and item.get("path") == rel_path for item in event.get("paths") or []):
            return before_content(root, event.get("rev"), rel_path, backend, store=store, events=[event])
    return None, "revision_unknown"


def show(root: Path, rev: str | None, rel_path: str, backend: Any | None = None, *,
                store: HistoryStore | None = None) -> tuple[str | None, str]:
    data, status = content_at(root, rev, rel_path, backend, store=store)
    if data is None:
        return None, status
    try:
        return data.decode("utf-8"), "ok"
    except UnicodeDecodeError:
        return None, "unreadable"


def diff_texts(before: str, after: str, context: int = 3) -> list[str]:
    return list(difflib.unified_diff(before.splitlines(), after.splitlines(),
                                     fromfile="before", tofile="after", lineterm="", n=context))


def blame(root: Path, rel_path: str, section: str | None = None, *,
                store: HistoryStore | None = None) -> list[dict[str, Any]]:
    """Кто и когда менял файл (или раздел) — по одному событию на диапазон."""
    entries: list[dict[str, Any]] = []
    bounds = _section_bounds(root, rel_path, section) if section else None
    if section and bounds is None:
        # Раздела в файле нет: отдавать всю историю файла нельзя — это выглядело бы
        # как ответ по разделу. Совпадает с поведением log --section.
        return entries
    storage = store if store is not None else default_history_store(root)
    for event in storage.read_events(strict=store is not None):
        for item in event.get("paths") or []:
            if not isinstance(item, dict) or item.get("path") != rel_path:
                continue
            if bounds:
                if not _ranges_touch_section(root, rel_path, section or "", item.get("ranges") or []):
                    continue
            entries.append({"rev": event.get("rev"), "at": event.get("at"), "kind": event.get("kind"),
                            "actor": event.get("actor"), "change_id": event.get("change_id"),
                            "ranges": item.get("ranges") or []})
    entries.reverse()
    return entries


def revert_plan(root: Path, rev: str | None, rel_path: str, backend: Any | None = None, *,
                store: HistoryStore | None = None) -> dict[str, Any]:
    """План отката события ``rev``: вернуть файлу образ «до» этого события."""
    if not rev:
        return {"path": rel_path, "rev": rev, "status": "revision_unknown"}
    data, status = before_content(root, rev, rel_path, backend, store=store)
    if data is None:
        return {"path": rel_path, "rev": rev, "status": status}
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return {"path": rel_path, "rev": rev, "status": "unreadable"}
    target = root / rel_path
    current = file_hash(target) if target.is_file() else ""
    # Файл менялся после снимаемой ревизии, если его текущее содержимое не совпадает
    # с состоянием на этой ревизии. Откат тогда стирает более поздние правки — это
    # надо сказать вслух, а не решать за пользователя (P6).
    after, _after_status = content_at(root, rev, rel_path, backend, store=store)
    at_rev = _content_hash(after) if after is not None else ""
    return {"path": rel_path, "rev": rev, "status": "ok", "content": text,
            "current_hash": current, "new_hash": _content_hash(text.encode("utf-8")),
            "range_conflict": bool(at_rev) and current != at_rev}


EXTERNAL_CHANGE = "external.change"


def observe_external_changes(root: Path, files: list[tuple[str, str]], *,
                             backend: Any | None = None, mode: str = "observed",
                             store: HistoryStore | None = None) -> list[str]:
    """Режим ``observed``: внешняя правка фиксируется событием, а не теряется молча.

    ``files`` — пары ``(rel_path, hash)`` из сканирования. Событие пишется только когда
    текущий хеш расходится с последним известным состоянием журнала, поэтому повторный
    скан ничего не дописывает: один внешний факт — одно событие, а не событие на запуск.
    Содержимое «до» неизвестно (``before: null``) — todoc его не видел; в режиме ``git``
    предыдущее состояние достаётся по сохранённому ``git_head``.
    """
    if mode != "observed":
        return []
    storage = default_history_store(root) if store is None else store
    events = storage.read_events(strict=store is not None)
    if not events:
        # Журнала нет — сравнивать не с чем. Точкой отсчёта служит `history adopt`,
        # иначе первый же скан объявил бы внешним весь корпус.
        return []
    with storage.transaction():
        events = storage.read_events(strict=store is not None)
        last: dict[str, str] = {}
        baseline = False
        for event in events:
            if event.get("kind") == "snapshot":
                baseline = True
            for item in event.get("paths") or []:
                if isinstance(item, dict) and item.get("path"):
                    last[str(item["path"])] = str(item.get("after") or "")

        head = backend.head() if backend is not None else None
        revs: list[str] = []
        seen: set[str] = set()
        for rel_path, current in files:
            seen.add(rel_path)
            if rel_path in last:
                # Путь уже в журнале: расходится хеш — значит правка была вне todoc.
                if last[rel_path] != current:
                    revs.append(_append_observed(storage, rel_path, current, head))
            elif baseline:
                # Базовая линия есть, а пути в журнале нет — файл появился в корпусе позже.
                revs.append(_append_observed(storage, rel_path, current, head))
            # Без базовой линии путь просто неизвестен истории: объявлять его внешней
            # правкой нельзя, иначе первый скан после первой записи пометил бы весь корпус.
        for rel_path in last:
            # Внешнее удаление: путь был в журнале, но из корпуса исчез и на диске его нет.
            if rel_path not in seen and last[rel_path] and not (root / rel_path).exists():
                revs.append(_append_observed(storage, rel_path, "", head))
        return revs


def _append_observed(store: HistoryStore, rel_path: str, after_hash: str, head: str | None) -> str:
    return store.append_event({
        "schema_version": SCHEMA_VERSION, "at": _utc_now(), "kind": EXTERNAL_CHANGE,
        "actor": "external", "change_id": None, "basis": "observed at scan",
        "paths": [{"path": rel_path, "before": None, "after": after_hash,
                   "git_head": head, "ranges": []}],
    })


def gc(root: Path, *, keep_objects: int | None = None, purge_before: str | None = None,
       dry_run: bool = False, limits: dict[str, Any] | None = None,
       events: list[dict[str, Any]] | None = None, refs: dict[str, Any] | None = None,
       store: HistoryStore | None = None, snapshots: list[str] | None = None) -> dict[str, Any]:
    """Plan or apply event retention and snapshot cleanup."""
    limits = limits or {}
    storage = store if store is not None else default_history_store(root)
    if events is None:
        events = storage.read_events(strict=store is not None)
    kept = [event for event in events if not (purge_before and str(event.get("at") or "") < purge_before)]
    max_bytes = limits.get("max_journal_bytes")
    trimmed_for_size = 0
    if isinstance(max_bytes, int) and max_bytes > 0:
        sizes = [storage.event_bytes(event) for event in kept]
        remaining_bytes = sum(sizes)
        for size in sizes:
            if remaining_bytes <= max_bytes:
                break
            remaining_bytes -= size
            trimmed_for_size += 1
        kept = kept[trimmed_for_size:]

    if keep_objects is None:
        limit_objects = limits.get("max_history_objects")
        if isinstance(limit_objects, int) and limit_objects >= 0:
            keep_objects = limit_objects

    referenced = {str(item["before"]) for event in kept for item in event.get("paths") or []
                  if isinstance(item, dict) and item.get("before")}
    if snapshots is None:
        snapshots = storage.list_snapshots()
    orphans = [digest for digest in snapshots if digest not in referenced]
    remaining = [digest for digest in snapshots if digest in referenced]
    if refs is not None:
        removed_revs = {event["rev"] for event in events} - {event["rev"] for event in kept}
        removed_tags = sorted(name for name, tag in refs["tags"].items()
                              if isinstance(tag, dict) and tag.get("rev") in removed_revs)
        if removed_tags:
            raise ConflictError("Cleanup would invalidate history tags: " + ", ".join(removed_tags),
                                "history.tagged_revision")
    drop_count = 0 if keep_objects is None else max(0, len(remaining) - keep_objects)
    oversized = remaining[:drop_count]
    if not dry_run:
        with storage.transaction():
            if store is not None and (storage.read_events(strict=True) != events
                                      or (refs is not None and storage.read_refs() != refs)
                                      or storage.list_snapshots() != snapshots):
                raise ConflictError("History changed before cleanup.", "write.hash_mismatch")
            storage.replace_events(kept)
            removed_orphans = [digest for digest in orphans if storage.remove_snapshot(digest)]
            removed_oversized = [digest for digest in oversized if storage.remove_snapshot(digest)]
            if store is not None and (len(removed_orphans) != len(orphans) or len(removed_oversized) != len(oversized)):
                raise IncompleteError("History cleanup only removed some planned snapshots.", "history.cleanup_incomplete")
            orphans = removed_orphans
            oversized = removed_oversized
    return {"removed_events": len(events) - len(kept), "kept_events": len(kept),
            "objects_before": len(snapshots), "objects_referenced": len(referenced), "orphans_removed": len(orphans),
            "trimmed_for_size": trimmed_for_size, "objects_trimmed": len(oversized), "dry_run": dry_run}


def adopt(root: Path, files: list[dict[str, Any]], *, store: HistoryStore | None = None,
          expected_history: tuple[list[dict[str, Any]], dict[str, Any]] | None = None) -> dict[str, Any]:
    """Миграция: снимок текущего состояния как точка отсчёта ``rev=baseline``.

    Старые поколения индекса не конвертируются: они не несли намерения, восстанавливать из
    них нечего. Журнал начинается с честной базовой линии.
    """
    storage = store if store is not None else default_history_store(root)
    with storage.transaction():
        entries = []
        for item in files:
            rel = str(item["path"])
            target = root / rel
            expected = item.get("hash")
            if store is not None:
                if not is_within_root(root, target):
                    raise AccessError(f"Adoption path is outside the dataset: {rel}", "access.outside_data_root")
                if not target.is_file() or (expected is not None and expected != file_hash(target)):
                    raise ConflictError(f"Source changed before adoption: {rel}", "write.hash_mismatch")
            elif not target.is_file():
                continue
            entries.append({"path": rel, "before": None, "after": expected or file_hash(target),
                            "git_head": None, "ranges": []})
        refs = storage.read_refs() if store is not None else read_refs(root)
        if expected_history is not None and (storage.read_events(strict=True), refs) != expected_history:
            raise ConflictError("History changed before adoption.", "write.hash_mismatch")
        rev = storage.append_event({"schema_version": SCHEMA_VERSION, "at": _utc_now(),
                                          "kind": "snapshot", "actor": "cli", "change_id": None,
                                          "paths": entries, "basis": "history adopt"})
        refs["head"] = rev
        try:
            storage.write_refs(refs)
        except (OSError, TodocError) as exc:
            raise IncompleteError(f"Adopted baseline {rev}, but could not update head: {exc}",
                                  "history.adopt_refs_failed") from exc
        return {"rev": rev, "paths": len(entries)}


def export(root: Path, destination: Path) -> dict[str, Any]:
    """Бэкап истории для бэкенда ``embedded``: копирует журнал, снимки и refs."""
    return {"exported": default_history_store(root).backup_to_existing_directory(destination), "to": str(destination)}


# --- диагностики -------------------------------------------------------------


def journal_diagnostics(dataset_id: str, root: Path) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    if default_history_store(root).truncated_final_line():
        diagnostics.append(Diagnostic(
            dataset_id=dataset_id, id="history-journal-truncated", code=JOURNAL_TRUNCATED,
            severity="warning", path=".todoc/history/journal.jsonl",
            message="Последняя строка журнала оборвана и проигнорирована. Предыдущие события целы.",
        ))
    return diagnostics


def record_event(root: Path, entries: list[dict[str, Any]], *, kind: str,
                 change_id: str | None = None, backend: Any = None,
                 store: HistoryStore | None = None, basis: str = "") -> str:
    """Record an exact multi-path operation; existing files always get snapshots."""
    storage = store if store is not None else default_history_store(root)
    with storage.transaction():
        return _record_event_locked(root, entries, kind=kind, change_id=change_id,
                                    backend=backend, store=storage, basis=basis)


def _record_event_locked(root: Path, entries: list[dict[str, Any]], *, kind: str,
                         change_id: str | None, backend: Any, store: HistoryStore,
                         basis: str = "", reverts_rev: str | None = None) -> str:
    # Caller already owns the history transaction. Never recursively lock it.
    store.read_events(strict=True)
    backend = backend or default_history_backend(root)
    head = backend.head()
    paths = []
    for entry in entries:
        before, after = entry['before'], entry['after']
        paths.append({'path': entry['path'], 'before_exists': before is not None,
                      'after_exists': after is not None,
                      'before': store.write_snapshot(before) if before is not None else None,
                      'after': _content_hash(after) if after is not None else None,
                      'git_head': head,
                      'ranges': changed_ranges((before or b'').decode('utf-8', 'replace'),
                                               (after or b'').decode('utf-8', 'replace'))})
    event = {'schema_version': SCHEMA_VERSION, 'at': _utc_now(), 'kind': kind, 'actor': 'cli',
             'change_id': change_id, 'paths': paths, 'basis': basis}
    if reverts_rev is not None:
        event['reverts_rev'] = reverts_rev
    return store.append_event(event)


def plan_revert_event(ctx: Any, change_id: str) -> dict[str, Any]:
    """Build a read-only, whole-corpus-bound inverse of one exact move event."""
    from todoc.application.move import MoveFile, checked_path, _current, digest, fresh_context, validate_files
    from todoc.application.paging import selection_key
    ctx = fresh_context(ctx)
    payload = ctx.read_index()
    events = ctx.history_store.read_events(strict=True)
    matches = [e for e in events if e.get('change_id') == change_id and e.get('kind') == 'doc.move']
    if not matches:
        raise IncompleteError('Move event not found.', 'move.revert_not_found')
    if len(matches) != 1:
        raise ConflictError('Ambiguous move identity.', 'move.revert_ambiguous')
    event = matches[0]
    if any(e.get('reverts_rev') == event['rev'] for e in events):
        raise ConflictError('Operation already reverted.', 'move.revert_conflict')
    files = []
    seen = set()
    for item in event['paths']:
        path = item['path']
        if path in seen or type(item.get('before_exists')) is not bool or type(item.get('after_exists')) is not bool:
            raise IncompleteError('No exact exists-state in history.', 'move.revert_unsupported')
        seen.add(path)
        current = _current(checked_path(ctx.root, path))
        if (current is not None) != item['after_exists'] or digest(current) != item.get('after'):
            raise ConflictError('Files changed since move; inverse would overwrite later work.', 'move.revert_conflict')
        before = ctx.history_store.read_snapshot(item['before']) if item['before_exists'] else None
        if item['before_exists'] and (before is None or digest(before) != item['before']):
            raise IncompleteError('Before snapshot missing.', 'move.revert_unsupported')
        files.append(MoveFile(path, current, before))
    if not files:
        raise IncompleteError('Empty move event.', 'move.revert_unsupported')
    validate_files(ctx, tuple(files))
    plan_hash = selection_key([1, ctx.dataset_id, payload['corpus_digest'], event,
                               [(f.path, digest(f.before), digest(f.after)) for f in files]])
    return {'preview': True, 'applied': False, 'plan_hash': plan_hash, 'rev': event['rev'],
            'change_id': change_id, '_files': tuple(files),
            'actions': [{'path': f.path, 'action': 'delete' if f.after is None else 'restore',
                         'current_hash': digest(f.before), 'target_hash': digest(f.after)} for f in files]}


def revert_event(ctx: Any, change_id: str, *, if_plan_hash: str) -> dict[str, Any]:
    from uuid import uuid4
    from todoc.adapters.filesystem.locks import directory_lock
    from todoc.application.move import commit_files, fresh_context
    if not if_plan_hash:
        raise TodocError('Revert requires --if-plan-hash from preview.', 2, 'usage.error')
    with directory_lock(ctx.root / '.todoc/locks/move.lock'):
        ctx = fresh_context(ctx)
        plan = plan_revert_event(ctx, change_id)
        if plan['plan_hash'] != if_plan_hash:
            raise ConflictError('Revert preview is stale.', 'move.plan_stale')
        result = commit_files(ctx, plan['_files'], kind='doc.move.revert',
                              change_id='move-revert:' + uuid4().hex, reverts_rev=plan['rev'])
    return {**result, 'preview': False, 'plan_hash': if_plan_hash, 'reverts_rev': plan['rev']}
