"""История: журнал событий записи, снимки «до» и откат.

Единица истории — **событие записи**, а не факт запуска команды. Все записи в проекте уже
проходят через три функции ``application/write.py``, и все три принимают ``expected_hash``,
поэтому один хук покрывает весь ввод.

Хронология одна — «как файл выглядел». Связь с задачей (``change_id``) и с релизом (``tag``)
хранится рядом, но не смешивается с ней: это разные вопросы (§2 плана).
"""

from __future__ import annotations

import difflib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from todoc.adapters.filesystem.scanner import atomic_write, file_hash
from todoc.adapters.history import journal, objects
from todoc.adapters.history.backends import EmbeddedBackend, resolve_backend
from todoc.domain.models import Diagnostic

SCHEMA_VERSION = 1

JOURNAL_UNREADABLE = "history.journal_unreadable"
JOURNAL_TRUNCATED = "history.journal_truncated_line"
OBJECT_MISSING = "history.object_missing"
REVISION_UNKNOWN = "history.revision_unknown"
BACKEND_UNAVAILABLE = "history.backend_unavailable"


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
    return resolve_backend(root, configured_backend(dataset or {}))


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
                 extra: dict[str, Any] | None = None) -> str | None:
    """Пишет одно событие записи. Возвращает ``rev`` или None, если журнал выключен.

    ``before is None`` означает создание файла: образа «до» не существует, и снимать его
    не нужно.
    """
    backend = backend or EmbeddedBackend(root)
    head = git_head if git_head is not None else backend.head()

    before_ref: str | None = None
    if before is not None:
        last = _last_revision_for(root, rel_path)
        if backend.needs_snapshot(rel_path, last):
            before_ref = objects.write_snapshot(root, before)

    entry: dict[str, Any] = {"path": rel_path,
                             "before": before_ref,
                             "after": objects.content_hash(after),
                             "git_head": head}
    if before is not None:
        # decode(errors="replace") не падает на бинарных данных: диапазоны считаются по
        # заменённым символам, событие остаётся корректным для текстовых файлов.
        entry["ranges"] = changed_ranges(before.decode("utf-8", "replace"),
                                        after.decode("utf-8", "replace"))
    else:
        entry["ranges"] = []
    if extra:
        entry.update(extra)

    return journal.append_event(root, {
        "schema_version": SCHEMA_VERSION, "at": _utc_now(), "kind": kind, "actor": actor,
        "change_id": change_id, "paths": [entry], "basis": basis,
    })


def _last_revision_for(root: Path, rel_path: str) -> str | None:
    last = None
    for event in journal.iter_events(root):
        for item in event.get("paths") or []:
            if isinstance(item, dict) and item.get("path") == rel_path:
                last = item.get("git_head")
    return last


# --- refs (head, tags) -------------------------------------------------------


def refs_path(root: Path) -> Path:
    return journal.history_dir(root) / "refs.json"


def read_refs(root: Path) -> dict[str, Any]:
    path = refs_path(root)
    if not path.is_file():
        return {"head": None, "tags": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"head": None, "tags": {}}
    if not isinstance(data, dict):
        return {"head": None, "tags": {}}
    data.setdefault("head", None)
    data.setdefault("tags", {})
    return data


def write_refs(root: Path, refs: dict[str, Any]) -> None:
    atomic_write(refs_path(root), json.dumps(refs, indent=2, ensure_ascii=False) + "\n")


def set_head(root: Path, rev: str) -> None:
    refs = read_refs(root)
    refs["head"] = rev
    write_refs(root, refs)


def add_tag(root: Path, name: str, rev: str, message: str = "") -> dict[str, Any]:
    refs = read_refs(root)
    refs["tags"][name] = {"rev": rev, "at": _utc_now(), "message": message}
    write_refs(root, refs)
    return refs["tags"][name]


# --- чтение содержимого на ревизии -------------------------------------------


def content_at(root: Path, rev: str | None, rel_path: str, backend: Any | None = None) -> tuple[bytes | None, str]:
    """Содержимое файла на ревизии ``rev``.

    Хранится только образ «до», поэтому содержимое на ревизии R — это образ «до» первого
    изменения после R, либо текущий файл, если изменений после R не было.
    """
    backend = backend or EmbeddedBackend(root)
    events = journal.read_events(root)
    if rev is not None and not any(e.get("rev") == rev for e in events):
        # Неизвестная ревизия не должна молча выглядеть как «текущее содержимое»:
        # иначе опечатка в rev вернёт текущий файл и откат пройдёт незамеченным.
        return None, "revision_unknown"
    seen_rev = rev is None
    for event in events:
        if rev is not None and event.get("rev") == rev:
            seen_rev = True
            continue
        if not seen_rev and rev is not None:
            continue
        for item in event.get("paths") or []:
            if not isinstance(item, dict) or item.get("path") != rel_path:
                continue
            before = item.get("before")
            if before:
                data = objects.read_snapshot(root, before)
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
                            current_relations: list[Any]) -> dict[str, Any] | None:
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
    for event in reversed(journal.read_events(root)):
        for item in event.get("paths") or []:
            if not isinstance(item, dict) or item.get("path") != rel_path or not item.get("before"):
                continue
            before = objects.read_snapshot(root, item["before"])
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


def resolve_rev(root: Path, rev_or_tag: str) -> str | None:
    """Разрешает имя тега в ``rev``; сам ``rev`` возвращается как есть."""
    refs = read_refs(root)
    tag = (refs.get("tags") or {}).get(rev_or_tag)
    if isinstance(tag, dict) and tag.get("rev"):
        return str(tag["rev"])
    return rev_or_tag or None


# --- команды -----------------------------------------------------------------


def log(root: Path, *, path: str | None = None, section: str | None = None, kind: str | None = None,
        change_id: str | None = None, tag: str | None = None, since: str | None = None,
        until: str | None = None, limit: int = 20, cursor: int = 0) -> tuple[list[dict[str, Any]], int, bool]:
    events = journal.read_events(root)
    tag_rev = resolve_rev(root, tag) if tag else None
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


def before_content(root: Path, rev: str, rel_path: str, backend: Any | None = None) -> tuple[bytes | None, str]:
    """Образ «до» конкретного события — то, что восстанавливает откат.

    Семантика намеренно расходится с ``content_at`` на один шаг и повторяет git:
    ``git show <c>:<path>`` показывает файл **на** коммите, а ``git revert <c>`` его
    **отменяет**. Поэтому ``show <rev>`` возвращает состояние после события, а
    ``revert <rev>`` — состояние до него.
    """
    backend = backend or EmbeddedBackend(root)
    for event in journal.read_events(root):
        if event.get("rev") != rev:
            continue
        for item in event.get("paths") or []:
            if not isinstance(item, dict) or item.get("path") != rel_path:
                continue
            before = item.get("before")
            if before:
                data = objects.read_snapshot(root, before)
                return (data, "ok") if data is not None else (None, "object_missing")
            head = item.get("git_head")
            if head:
                data = backend.read_at(head, rel_path)
                if data is not None:
                    return data, "ok"
            # Событие создания файла: откатывать некуда, файла до него не было.
            return None, "no_before"
    return None, "revision_unknown"


def show(root: Path, rev: str | None, rel_path: str, backend: Any | None = None) -> tuple[str | None, str]:
    data, status = content_at(root, rev, rel_path, backend)
    if data is None:
        return None, status
    try:
        return data.decode("utf-8"), "ok"
    except UnicodeDecodeError:
        return None, "unreadable"


def diff_texts(before: str, after: str, context: int = 3) -> list[str]:
    return list(difflib.unified_diff(before.splitlines(), after.splitlines(),
                                     fromfile="before", tofile="after", lineterm="", n=context))


def blame(root: Path, rel_path: str, section: str | None = None) -> list[dict[str, Any]]:
    """Кто и когда менял файл (или раздел) — по одному событию на диапазон."""
    entries: list[dict[str, Any]] = []
    bounds = _section_bounds(root, rel_path, section) if section else None
    if section and bounds is None:
        # Раздела в файле нет: отдавать всю историю файла нельзя — это выглядело бы
        # как ответ по разделу. Совпадает с поведением log --section.
        return entries
    for event in journal.read_events(root):
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


def revert_plan(root: Path, rev: str | None, rel_path: str, backend: Any | None = None) -> dict[str, Any]:
    """План отката события ``rev``: вернуть файлу образ «до» этого события."""
    if not rev:
        return {"path": rel_path, "rev": rev, "status": "revision_unknown"}
    data, status = before_content(root, rev, rel_path, backend)
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
    after, _after_status = content_at(root, rev, rel_path, backend)
    at_rev = objects.content_hash(after) if after is not None else ""
    return {"path": rel_path, "rev": rev, "status": "ok", "content": text,
            "current_hash": current, "new_hash": objects.content_hash(text.encode("utf-8")),
            "range_conflict": bool(at_rev) and current != at_rev}


EXTERNAL_CHANGE = "external.change"


def observe_external_changes(root: Path, files: list[tuple[str, str]], *,
                             backend: Any | None = None, mode: str = "observed") -> list[str]:
    """Режим ``observed``: внешняя правка фиксируется событием, а не теряется молча.

    ``files`` — пары ``(rel_path, hash)`` из сканирования. Событие пишется только когда
    текущий хеш расходится с последним известным состоянием журнала, поэтому повторный
    скан ничего не дописывает: один внешний факт — одно событие, а не событие на запуск.
    Содержимое «до» неизвестно (``before: null``) — todoc его не видел; в режиме ``git``
    предыдущее состояние достаётся по сохранённому ``git_head``.
    """
    if mode != "observed":
        return []
    events = journal.read_events(root)
    if not events:
        # Журнала нет — сравнивать не с чем. Точкой отсчёта служит `history adopt`,
        # иначе первый же скан объявил бы внешним весь корпус.
        return []
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
                revs.append(_append_observed(root, rel_path, current, head))
        elif baseline:
            # Базовая линия есть, а пути в журнале нет — файл появился в корпусе позже.
            revs.append(_append_observed(root, rel_path, current, head))
        # Без базовой линии путь просто неизвестен истории: объявлять его внешней
        # правкой нельзя, иначе первый скан после первой записи пометил бы весь корпус.
    for rel_path in last:
        # Внешнее удаление: путь был в журнале, но из корпуса исчез и на диске его нет.
        if rel_path not in seen and not (root / rel_path).exists():
            revs.append(_append_observed(root, rel_path, "", head))
    return revs


def _append_observed(root: Path, rel_path: str, after_hash: str, head: str | None) -> str:
    return journal.append_event(root, {
        "schema_version": SCHEMA_VERSION, "at": _utc_now(), "kind": EXTERNAL_CHANGE,
        "actor": "external", "change_id": None, "basis": "observed at scan",
        "paths": [{"path": rel_path, "before": None, "after": after_hash,
                   "git_head": head, "ranges": []}],
    })


def gc(root: Path, *, keep_objects: int | None = None, purge_before: str | None = None,
       dry_run: bool = False, limits: dict[str, Any] | None = None) -> dict[str, Any]:
    """Сборка мусора: убирает события по возрасту и снимки, на которые никто не ссылается.

    ``limits`` — ``dataset["limits"]``. ``max_history_objects`` служит значением по
    умолчанию для ``keep_objects``, а ``max_journal_bytes`` подрезает самые старые
    события, когда журнал вырос больше потолка. Явный ``--keep-objects`` важнее лимита:
    потолок обслуживает хранилище, а не отменяет решение пользователя.
    """
    limits = limits or {}
    events = journal.read_events(root)
    kept = [e for e in events if not (purge_before and str(e.get("at") or "") < purge_before)]
    removed_events = len(events) - len(kept)

    objects_trimmed = 0
    max_bytes = limits.get("max_journal_bytes")
    trimmed_for_size = 0
    if isinstance(max_bytes, int) and max_bytes > 0:
        while kept and journal.events_bytes(kept) > max_bytes:
            kept = kept[1:]
            trimmed_for_size += 1
        removed_events += trimmed_for_size

    if keep_objects is None:
        limit_objects = limits.get("max_history_objects")
        if isinstance(limit_objects, int) and limit_objects >= 0:
            keep_objects = limit_objects

    referenced: set[str] = set()
    for event in kept:
        for item in event.get("paths") or []:
            if isinstance(item, dict) and item.get("before"):
                referenced.add(str(item["before"]))
    total = objects.count_objects(root)
    orphans = total - len(referenced)

    if not dry_run:
        journal.rewrite(root, kept)
        # Обход идёт по хранилищу, а не по событиям: сирота по определению ни в одном
        # событии не упоминается, и обходом событий её не найти.
        removed = 0
        for digest in _all_object_digests(root):
            if digest not in referenced and objects.remove_object(root, digest):
                removed += 1
        orphans = removed
        if keep_objects is not None:
            objects_trimmed = _trim_objects(root, keep_objects)
    return {"removed_events": removed_events, "kept_events": len(kept),
            "objects_before": total, "objects_referenced": len(referenced),
            "orphans_removed": max(orphans, 0), "trimmed_for_size": trimmed_for_size,
            "objects_trimmed": objects_trimmed, "dry_run": dry_run}


def _all_object_digests(root: Path) -> list[str]:
    """Все ``sha256:`` в хранилище: имя объекта — это его дайджест."""
    base = objects.objects_dir(root)
    if not base.is_dir():
        return []
    out = []
    for path in base.rglob("*"):
        if path.is_file() and len(path.parent.name) == 2:
            out.append("sha256:" + path.parent.name + path.name)
    return out


def _trim_objects(root: Path, keep: int) -> int:
    """Оставляет в хранилище не больше ``keep`` снимков, начиная с самых старых.

    Снимки, на которые ссылается журнал, больше не пропускаются: иначе потолок не
    значил бы ничего — все «живые» снимки защищены ссылкой, а незащищённые удаляет
    цикл выше, и до этого обхода дело не доходит. Цена явная и уже предусмотрена
    состояниями чтения: у затёртой ревизии ``show``/``revert`` вернут
    ``object_missing``, а не придуманное содержимое.
    """
    base = objects.objects_dir(root)
    if not base.is_dir():
        return 0
    files = sorted((p for p in base.rglob("*") if p.is_file()), key=lambda p: p.stat().st_mtime)
    excess = len(files) - keep
    trimmed = 0
    for path in files[: max(excess, 0)]:
        try:
            path.unlink()
        except OSError:
            continue
        trimmed += 1
    return trimmed


def adopt(root: Path, files: list[dict[str, Any]]) -> dict[str, Any]:
    """Миграция: снимок текущего состояния как точка отсчёта ``rev=baseline``.

    Старые поколения индекса не конвертируются: они не несли намерения, восстанавливать из
    них нечего. Журнал начинается с честной базовой линии.
    """
    entries = []
    for item in files:
        rel = str(item["path"])
        target = root / rel
        if not target.is_file():
            continue
        entries.append({"path": rel, "before": None, "after": item.get("hash") or file_hash(target),
                        "git_head": None, "ranges": []})
    rev = journal.append_event(root, {"schema_version": SCHEMA_VERSION, "at": _utc_now(),
                                      "kind": "snapshot", "actor": "cli", "change_id": None,
                                      "paths": entries, "basis": "history adopt"})
    set_head(root, rev)
    return {"rev": rev, "paths": len(entries)}


def export(root: Path, destination: Path) -> dict[str, Any]:
    """Бэкап истории для бэкенда ``embedded``: копирует журнал, снимки и refs."""
    source = journal.history_dir(root)
    if not source.is_dir():
        return {"exported": 0, "to": str(destination)}
    destination.mkdir(parents=True, exist_ok=True)
    count = 0
    for path in source.rglob("*"):
        if not path.is_file():
            continue
        target = destination / path.relative_to(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(path.read_bytes())
        count += 1
    return {"exported": count, "to": str(destination)}


# --- диагностики -------------------------------------------------------------


def journal_diagnostics(dataset_id: str, root: Path) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    if journal.truncated_last_line(root):
        diagnostics.append(Diagnostic(
            dataset_id=dataset_id, id="history-journal-truncated", code=JOURNAL_TRUNCATED,
            severity="warning", path=".todoc/history/journal.jsonl",
            message="Последняя строка журнала оборвана и проигнорирована. Предыдущие события целы.",
        ))
    return diagnostics
