"""Би-темпоральные факты: время правды и время знания (план §5.5).

Два независимых часа, оба опциональны и обратно совместимы:

- ``valid_from`` / ``valid_to`` — когда факт был правдой **в мире**;
- ``observed_at`` / ``superseded_at`` — когда todoc о нём **узнал** и когда закрыл.

Точка во времени вычисляется по формуле плана::

    valid_from <= T AND (valid_to IS NULL OR T < valid_to)

Интервал полуоткрытый: ``valid_to`` — это уже не правда. Это важно для K40, где
ответ требуется точным, без допусков.

**Инвалидация вместо удаления.** Закрытие факта ставит ``superseded_at``, а сам
факт остаётся в файле и остаётся читаемым: он исчезает только из выборки «на
момент T». Хронология — это не кэш, терять её нельзя.

Ядро детерминированное (P5): противоречия система **не ищет сама**. Закрытие
факта — всегда явное действие человека (правка записи или ``change``).

Значения сравниваются как нормализованные к UTC строки ISO-8601: лексикографический
порядок у них совпадает с хронологическим, поэтому сравнение не зависит от локали
и не требует часовых поясов в рантайме.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from todoc.adapters.history import journal

TEMPORAL_FIELDS = ("valid_from", "valid_to", "observed_at", "superseded_at")


class InvalidInstant(ValueError):
    """Значение не разбирается как дата или момент ISO-8601."""


def normalize_instant(value: Any) -> str | None:
    """Приводит дату/момент к сравниваемой строке. ``None`` — поля нет.

    Дата без времени остаётся датой: ``"2024-01-01"`` — это полночь того дня, и
    лексикографически она меньше любого момента того же дня, что и требуется.
    Моменты с часовым поясом приводятся к UTC, иначе порядок сравнения зависел бы
    от написания, а не от времени.
    """
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        try:
            parsed = datetime.fromisoformat(f"{text}T00:00:00")
        except ValueError as exc:
            raise InvalidInstant(f"Not an ISO-8601 date or instant: {value!r}") from exc
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return parsed.strftime("%Y-%m-%dT%H:%M:%S") + "Z"
    if _is_date_only(text):
        return parsed.date().isoformat()
    return parsed.strftime("%Y-%m-%dT%H:%M:%S") + "Z"


def _is_date_only(text: str) -> bool:
    try:
        date.fromisoformat(text)
    except ValueError:
        return False
    return True


def _key(fields: dict[str, Any], name: str) -> str | None:
    """Сравниваемый ключ поля; ``None``, если поля нет.

    Неразбираемое значение даёт ``InvalidInstant``: порядок по мусорным данным
    недетерминирован, а молча принять его — значит выдать выдуманный ответ.
    """
    return normalize_instant(fields.get(name))


def interval_defect(fields: dict[str, Any]) -> tuple[str, str, str] | None:
    """Дефект интервала: ``(код, сообщение, виновное поле)`` либо ``None``.

    Виновное поле возвращается всегда, чтобы диагностика указывала точный
    JSON Pointer, а не «где-то в записи».
    """
    try:
        start = _key(fields, "valid_from")
    except InvalidInstant as exc:
        return "temporal.invalid_instant", str(exc), "valid_from"
    try:
        end = _key(fields, "valid_to")
    except InvalidInstant as exc:
        return "temporal.invalid_instant", str(exc), "valid_to"
    if start is not None and end is not None and end <= start:
        return ("temporal.invalid_interval",
                f"valid_to ({fields.get('valid_to')}) не позже valid_from ({fields.get('valid_from')})",
                "valid_to")
    return None


def is_valid_at(fields: dict[str, Any], as_of: str) -> bool:
    """Был ли факт правдой в момент ``as_of`` (время правды).

    Опечатка в самой точке во времени — это ошибка вызова, а не пустой ответ: иначе
    ``--as-of вчера`` молча вернул бы «ничего», и отличить это от правды было бы нельзя.
    Неразбираемое значение **в данных** делает факт невидимым: выборка остаётся
    детерминированной, а причина видна в ``validate`` как ``temporal.invalid_instant``.
    """
    moment = normalize_instant(as_of)
    try:
        start = _key(fields, "valid_from")
        end = _key(fields, "valid_to")
    except InvalidInstant:
        return False
    if moment is None:
        return True
    if start is not None and moment < start:
        return False
    return end is None or moment < end


def is_superseded(fields: dict[str, Any], as_of: str | None) -> bool:
    """Закрыт ли факт к моменту ``as_of`` (время знания)."""
    moment = normalize_instant(as_of) if as_of else None
    try:
        closed = _key(fields, "superseded_at")
    except InvalidInstant:
        return True
    if closed is None:
        return False
    if moment is None:
        return True
    return closed <= moment


def visible_at(fields: dict[str, Any], as_of: str | None) -> bool:
    """Виден ли факт в выборке «на момент ``as_of``»."""
    if as_of is None:
        # Без точки во времени фильтруем только по времени знания: закрытый факт
        # уже не правда о настоящем, но остаётся читаемым в файле и в timeline.
        return not is_superseded(fields, None)
    return is_valid_at(fields, as_of) and not is_superseded(fields, as_of)


def temporal_of(rel: Any) -> dict[str, Any]:
    """Темпоральные поля объекта (записи или отношения). Не-словарь — пустой интервал."""
    if not isinstance(rel, dict):
        return {}
    return {name: rel.get(name) for name in TEMPORAL_FIELDS if rel.get(name) is not None}


def records_as_of(records: list[dict[str, Any]], as_of: str | None) -> list[dict[str, Any]]:
    """Записи, видимые на момент ``as_of``. Записи без полей видны всегда."""
    if as_of is None:
        return records
    return [r for r in records if visible_at(temporal_of(r.get("data")), as_of)]


def relations_as_of(relations: list[dict[str, Any]], as_of: str | None) -> list[dict[str, Any]]:
    """Рёбра графа, видимые на момент ``as_of``."""
    if as_of is None:
        return relations
    return [r for r in relations if visible_at(temporal_of(r), as_of)]


def timeline(root: Path, records: list[dict[str, Any]], relations: list[dict[str, Any]], *,
             as_of: str | None = None, path: str | None = None,
             limit: int = 200) -> dict[str, Any]:
    """Единая лента: события журнала (время знания) + интервалы фактов (время правды).

    Это ответ на «что было известно на дату T» — то, чего не даёт ни ``git log``
    (у него нет времени правды), ни ``git bisect`` (у него нет фактов).

    ``--as-of`` срезает обе половины по одному и тому же моменту: события позже T
    ещё не произошли, факты позже T ещё не правда.
    """
    # InvalidInstant намеренно не перехватывается: неверная точка во времени —
    # ошибка вызова, CLI превращает её в конверт temporal.invalid_instant.
    moment = normalize_instant(as_of) if as_of else None

    by_record = {str(r.get("record_id", "")): str(r.get("path", "")) for r in records}
    entries: list[dict[str, Any]] = []

    for event in journal.read_events(root):
        at = str(event.get("at") or "")
        if moment is not None and at and at > moment:
            continue
        for item in event.get("paths") or []:
            if not isinstance(item, dict):
                continue
            rel_path = str(item.get("path") or "")
            if path and rel_path != path:
                continue
            entries.append({
                "kind": str(event.get("kind") or ""),
                "entry": "event",
                "at": at,
                "rev": str(event.get("rev") or ""),
                "path": rel_path,
                "change_id": event.get("change_id"),
                "sort": (at, "event", str(event.get("rev") or ""), rel_path),
            })

    for rel in relations:
        fields = temporal_of(rel)
        if not fields:
            continue
        owner = by_record.get(str(rel.get("source_id") or ""), "")
        if path and owner != path:
            continue
        if moment is not None and not visible_at(fields, as_of):
            continue
        started = normalize_instant(fields.get("valid_from")) or str(fields.get("observed_at") or "")
        entries.append({
            "kind": "fact",
            "entry": "fact",
            "at": started,
            "valid_from": fields.get("valid_from"),
            "valid_to": fields.get("valid_to"),
            "observed_at": fields.get("observed_at"),
            "superseded_at": fields.get("superseded_at"),
            "source_id": rel.get("source_id"),
            "target_id": rel.get("target_id"),
            "type_id": rel.get("type_id"),
            "path": owner,
            "sort": (started or "", "fact", str(rel.get("source_id") or ""), str(rel.get("type_id") or "")),
        })

    entries.sort(key=lambda e: e["sort"])
    total = len(entries)
    for entry in entries:
        entry.pop("sort", None)
    return {"as_of": moment, "path": path, "count": total, "truncated": total > limit,
            "entries": entries[:limit]}
