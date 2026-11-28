"""Агентский стейт сессии (план agent-state, v1): ``state.json`` вне данных.

Файл ``{XDG_STATE_HOME}/todoc/state-<dataset_id>.json`` (по умолчанию
``~/.local/state/``), содержит ``{"schema_version": 1, "vars": {...},
"updated_at": ISO-8601 UTC}``. Датасет не мутирует: стейт — свойство сессии,
не данных; ключи — белый список v1 (расширение = правка ``ALLOWED_KEYS_V1``,
не формата файла). Запись атомарная (``atomic_write`` — mkstemp + replace,
родительский каталог создаёт сама); параллельные записи — «последний
выигрывает». Ошибки: ``state.unknown_key`` (ключ вне whitelist), 
``state.invalid_value`` (не строка 1–256), ``state.limit_exceeded``
(>200 ключей или файл >64 КБ), ``state.file_unavailable``.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from todoc.adapters.filesystem.scanner import atomic_write
from todoc.errors import ValidationError

ALLOWED_KEYS_V1: tuple[str, ...] = ("context.current_project",)
_MAX_VALUE = 256
_MAX_KEYS = 200
_MAX_BYTES = 64 * 1024


def state_path(dataset_id: str) -> Path:
    """Файл стейта датасета: ``{XDG_STATE_HOME|~/.local/state}/todoc/state-<id>.json``."""
    xdg = os.environ.get("XDG_STATE_HOME")
    base = Path(xdg) if xdg else Path.home() / ".local" / "state"
    return base / "todoc" / f"state-{dataset_id}.json"


def _empty() -> dict[str, Any]:
    return {"schema_version": 1, "vars": {}, "updated_at": None}


def load_state(dataset_id: str) -> dict[str, Any]:
    """Прочитать стейт; отсутствующий файл = пустой стейт, битый — ``state.file_unavailable``."""
    path = state_path(dataset_id)
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return _empty()
    except OSError as exc:
        raise ValidationError(f"Файл стейта недоступен: {path}: {exc}",
                              "state.file_unavailable") from exc
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValidationError(f"Файл стейта повреждён (не JSON): {path}",
                              "state.file_unavailable") from exc
    if not isinstance(data, dict) or not isinstance(data.get("vars"), dict):
        raise ValidationError(f"Файл стейта повреждён (ожидался объект с vars): {path}",
                              "state.file_unavailable")
    return data


def _check_key(key: str) -> None:
    if key not in ALLOWED_KEYS_V1:
        raise ValidationError(
            f"Ключ вне белого списка v1: {key!r} (разрешены: {', '.join(ALLOWED_KEYS_V1)})",
            "state.unknown_key")


def _check_limits(dataset_id: str, extra: int) -> None:
    path = state_path(dataset_id)
    if path.exists() and path.stat().st_size > _MAX_BYTES:
        raise ValidationError(f"Файл стейта больше {_MAX_BYTES} байт: {path}",
                              "state.limit_exceeded")
    if len(load_state(dataset_id)["vars"]) + extra > _MAX_KEYS:
        raise ValidationError(f"Больше {_MAX_KEYS} ключей в стейте",
                              "state.limit_exceeded")


def _save(dataset_id: str, data: dict[str, Any]) -> None:
    payload = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    try:
        atomic_write(state_path(dataset_id), payload)
    except OSError as exc:
        raise ValidationError(f"Не удалось записать файл стейта: "
                              f"{state_path(dataset_id)}: {exc}",
                              "state.file_unavailable") from exc


def _now(now: str | None) -> str:
    return now or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def set_var(dataset_id: str, key: str, value: str, *, now: str | None = None, apply: bool = True) -> dict[str, Any]:
    """Записать значение переменной стейта (whitelist + лимиты), вернуть новый стейт."""
    _check_key(key)
    if not isinstance(value, str) or not (1 <= len(value) <= _MAX_VALUE):
        raise ValidationError(f"Значение должно быть строкой 1–{_MAX_VALUE} символов",
                              "state.invalid_value")
    _check_limits(dataset_id, extra=0 if key in load_state(dataset_id)["vars"] else 1)
    data = load_state(dataset_id)
    data["schema_version"] = 1
    data["vars"][key] = value
    if apply:
        data["updated_at"] = _now(now)
        _save(dataset_id, data)
    return data


def get_var(dataset_id: str, key: str) -> str | None:
    """Прочитать переменную: ``None`` — файла нет или ключ не установлен."""
    _check_key(key)
    return load_state(dataset_id)["vars"].get(key)


def unset_var(dataset_id: str, key: str) -> bool:
    """Удалить переменную; ``True`` — была и удалена, ``False`` — не установлена."""
    _check_key(key)
    data = load_state(dataset_id)
    if key not in data["vars"]:
        return False
    del data["vars"][key]
    data["updated_at"] = _now(None)
    _save(dataset_id, data)
    return True
