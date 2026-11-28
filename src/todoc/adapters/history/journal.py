"""Append-only журнал событий истории: ``.todoc/history/journal.jsonl``.

Одна строка — одно событие записи. Формат JSONL выбран потому, что дописка атомарна одним
``write`` без read-modify-write, файл грепается и диффится в git, и не нужна БД.

``rev`` — SHA-256 самой строки (12 hex). Он не требует счётчика и не зависит от порядка
обработки, поэтому два одинаковых события в разных датасетах получают одинаковый ``rev``.

Оборванная последняя строка (обрыв питания посреди дописки) игнорируется, а не валит
команду: журнал обязан читаться в любом состоянии.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterator


def history_dir(root: Path) -> Path:
    return root / ".todoc" / "history"


def journal_path(root: Path) -> Path:
    return history_dir(root) / "journal.jsonl"


def event_rev(line: str) -> str:
    return hashlib.sha256(line.encode("utf-8")).hexdigest()[:12]


def append_event(root: Path, event: dict[str, Any]) -> str:
    """Дописывает событие и возвращает его ``rev``.

    ``rev`` вычисляется из сериализованной строки, поэтому поле ``rev`` в самом событии
    не участвует в собственном хеше.
    """
    payload = {k: v for k, v in event.items() if k != "rev"}
    line = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    rev = event_rev(line)
    path = journal_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")
        fh.flush()
        os.fsync(fh.fileno())
    return rev


def iter_events(root: Path) -> Iterator[dict[str, Any]]:
    """События в порядке записи. Битые строки пропускаются, а не роняют чтение."""
    path = journal_path(root)
    if not path.is_file():
        return
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(event, dict):
                event.setdefault("rev", event_rev(line))
                yield event


def read_events(root: Path) -> list[dict[str, Any]]:
    return list(iter_events(root))


def truncated_last_line(root: Path) -> bool:
    """True, если последняя строка не разбирается — признак оборванной записи."""
    path = journal_path(root)
    if not path.is_file():
        return False
    try:
        lines = [ln for ln in path.read_text(encoding="utf-8", errors="replace").splitlines() if ln.strip()]
    except OSError:
        return False
    if not lines:
        return False
    try:
        json.loads(lines[-1])
    except json.JSONDecodeError:
        return True
    return False


def _retained_line(event: dict[str, Any]) -> str:
    payload = {key: value for key, value in event.items() if key != "rev"}
    line = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    revision = event.get("rev")
    if revision is None or revision == event_rev(line):
        return line
    # Older or imported JSONL may have different whitespace. Both readers
    # recognize an explicit revision, so compaction keeps existing references.
    return json.dumps(event, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def events_bytes(events: list[dict[str, Any]]) -> int:
    """Return the size of the serialized journal after compaction."""
    return sum(len(_retained_line(event).encode("utf-8")) + 1 for event in events)


def rewrite(root: Path, events: list[dict[str, Any]]) -> None:
    """Replace the journal atomically, preserving existing revision identifiers."""
    from todoc.adapters.filesystem.scanner import atomic_write

    path = journal_path(root)
    body = "".join(_retained_line(event) + "\n" for event in events)
    atomic_write(path, body)
