"""``todoc context``: весь контекст задачи одним вызовом, в пределах бюджета.

Агенту на задачу нужны не десять команд, а один ответ: что за изменение, какие дельты,
какие файлы затронуты, что по ним уже известно из истории. Отдельный вызов вместо
набора ``show``/``log``/``read`` — это требование исследования
(``docs/research/mcp-cli-agents.md``): меньше обращений, меньше токенов, меньше шансов
собрать контекст неверно.

Выдача ограничена бюджетом символов (P7). Порядок заполнения фиксированный: сначала
структура (запись, дельты, события), потом содержимое файлов — так усечение режет
текст, а не смысл.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from todoc.adapters.filesystem.scanner import file_hash, is_within_root
from todoc.application import changes as C
from todoc.application import history as H
from todoc.application.storage import HistoryStore


def build_context(root: Path, dataset_id: str, *, change_id: str | None = None,
                  tag: str | None = None, budget: int = 8000,
                  with_diff: bool = False, max_diff_lines: int | None = None,
                  store: HistoryStore | None = None, backend: Any = None) -> dict[str, Any]:
    """Собирает контекст задачи. Возвращает словарь с флагом ``truncated``.

    ``budget`` считается по сериализованному объёму добавляемых кусков, а не по числу
    строк: размер измеряется в символах Unicode. Поля конверта не входят в бюджет.

    ``max_diff_lines`` — потолок строк на один дифф (``limits.max_diff_lines``): один
    огромный дифф не должен съедать бюджет, оставленный остальным частям контекста.
    """
    used = 0
    result: dict[str, Any] = {"dataset_id": dataset_id, "change_id": change_id, "tag": tag,
                              "budget": budget, "truncated": False, "record": None}

    def take(value: Any) -> tuple[Any, bool]:
        """Добавляет кусок, если он влезает в бюджет. Возвращает ``(значение, влезло)``."""
        nonlocal used
        import json

        size = len(value) if isinstance(value, str) else len(json.dumps(value, ensure_ascii=False))
        if used + size > budget:
            return None, False
        used += size
        return value, True

    record = C.load_change(root, change_id) if change_id else None
    if change_id and record is None:
        result["error"] = "change.not_found"
        return result

    if record is not None:
        slim = {k: v for k, v in record.items() if k not in ("baseline", "relations")}
        slim["blocked_by"] = [str((r.get("target") or {}).get("id") or "")
                              for r in record.get("relations") or []
                              if isinstance(r, dict) and r.get("type_id") == "blocked_by"]
        value, ok = take(slim)
        result["record"] = value
        if not ok:
            result["truncated"] = True

    deltas = C.collect_deltas(root, change_id) if change_id else []
    delta_view = [{"path": d["path"], "target": d["target"], "base_hash": d["base_hash"],
                   "order": d["order"],
                   "ops": [{"op": o["op"], "anchor": o["anchor"]} for o in d["ops"]]}
                  for d in deltas]
    value, ok = take(delta_view)
    result["deltas"] = value if ok else []
    result["truncated"] = result["truncated"] or not ok

    # События истории: по change_id, либо по метке, либо последние по затронутым файлам.
    all_events = store.read_events(strict=True) if store is not None else None
    refs = store.read_refs() if store is not None and tag else None
    events, total, _t = H.log(root, tag=tag, change_id=change_id if not tag else None,
                              limit=20, events=all_events, refs=refs)
    value, ok = take([{"rev": e.get("rev"), "at": e.get("at"), "kind": e.get("kind"),
                       "actor": e.get("actor"),
                       "paths": [p.get("path") for p in e.get("paths") or []]}
                      for e in events])
    result["events"] = value if ok else []
    result["events_total"] = total
    result["truncated"] = result["truncated"] or not ok

    # Содержимое файлов — последнее, что добавляется, поэтому режется первым.
    # Артефакт и цель дельты — часто один и тот же файл; без дедупликации контекст
    # отдавал бы его дважды и вдвое быстрее упирался бы в бюджет.
    seen: set[str] = set()
    paths: list[str] = []
    for candidate in [str(a) for a in (record or {}).get("artifacts") or []] + \
            sorted({d["target"] for d in deltas if d["target"]}):
        if candidate not in seen:
            seen.add(candidate)
            paths.append(candidate)
    files: list[dict[str, Any]] = []
    for rel in paths:
        target = root / rel
        if not is_within_root(root, target) or not target.is_file():
            continue
        try:
            text = target.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        entry: dict[str, Any] = {"path": rel, "hash": file_hash(target), "chars": len(text)}
        value, ok = take(text)
        if not ok:
            result["truncated"] = True
            break
        entry["content"] = value
        files.append(entry)
    result["files"] = files

    if with_diff and change_id:
        diffs: list[dict[str, Any]] = []
        baseline = (record or {}).get("baseline") if isinstance((record or {}).get("baseline"), dict) else {}
        base_hashes = baseline.get("artifacts") if isinstance(baseline.get("artifacts"), dict) else {}
        for rel in paths:
            target = root / rel
            known = base_hashes.get(rel)
            if not is_within_root(root, target) or not target.is_file() or known is None or known == file_hash(target):
                # Без базового хеша сравнивать не с чем: отдавать «revision_unknown»
                # означало бы шум вместо контекста.
                continue
            data, status = H.first_before(root, rel, backend=backend, store=store, events=all_events)
            before = data.decode("utf-8", "replace") if data is not None else None
            if before is None:
                diffs.append({"path": rel, "status": status})
                continue
            lines = H.diff_texts(before, target.read_text(encoding="utf-8"))
            if max_diff_lines is not None and len(lines) > max_diff_lines:
                # Обрезано по лимиту, а не по бюджету: это разные причины, и обе
                # обязаны быть видны в флаге truncated.
                lines = lines[:max_diff_lines]
                result["truncated"] = True
            value, ok = take(lines)
            if not ok:
                result["truncated"] = True
                break
            diffs.append({"path": rel, "changed": bool(lines), "lines": len(lines), "diff": value})
        result["diffs"] = diffs
    result["used_chars"] = used
    return result
