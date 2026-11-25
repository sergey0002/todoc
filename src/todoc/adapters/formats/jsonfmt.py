"""JSON adapter: strict parsing, duplicate-key rejection, JSON Pointer, schema check.

Error contract: ``parse_json`` returns ``(value, errors)`` where each error is
a ``"code: message"`` string (callers split on the first ``": "``). Codes:
``json.syntax_error``, ``json.duplicate_key``, ``json.invalid_constant``,
``json.too_deep``. Strict mode: ``NaN``/``Infinity`` are rejected (not valid
JSON), a leading BOM is stripped, and nesting depth is checked iteratively
so hostile input cannot crash the process with ``RecursionError``.
"""

from __future__ import annotations

import json
import re
from typing import Any

from jsonschema import Draft202012Validator


class DuplicateKeyError(ValueError):
    """Повторный ключ. ``key`` нужен, чтобы найти позицию виновного места в тексте."""

    def __init__(self, message: str, key: str | None = None) -> None:
        super().__init__(message)
        self.key = key


class _InvalidConstant(ValueError):
    """``NaN``/``Infinity`` в JSON. ``name`` — текст константы для поиска позиции."""

    def __init__(self, message: str, name: str | None = None) -> None:
        super().__init__(message)
        self.name = name


def _no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    obj: dict[str, Any] = {}
    for key, value in pairs:
        if key in obj:
            raise DuplicateKeyError(f"duplicate key: {key}", key)
        obj[key] = value
    return obj


def _reject_constant(value: str) -> Any:
    raise _InvalidConstant(f"invalid constant: {value}", value)


# --- Позиции в тексте --------------------------------------------------------
#
# Стандартный ``json`` не сообщает позицию ни для ``object_pairs_hook``, ни для
# ``parse_constant``: оба получают уже разобранные значения. Поэтому позиция
# восстанавливается отдельным проходом по тексту. Сканер намеренно **не парсер**:
# он не решает, корректен ли JSON, он лишь находит смещения нужных токенов, и
# потому не может изменить семантику разбора. На враждебном вводе он
# останавливается, а не падает.

_WS = " \t\n\r"
_NUM_CHARS = "0123456789+-.eE"


def _iter_tokens(text: str):
    """Лексемы с их смещениями: ``(kind, payload, offset)``.

    ``kind``: ``key`` (строка перед ``:``), ``string``, ``const`` (голое слово),
    ``number``, ``open``, ``close``. Не разбирает содержимое строк дальше
    необходимого и никогда не бросает исключений.
    """
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if ch in _WS:
            i += 1
            continue
        if ch == '"':
            start = i
            i += 1
            while i < n:
                if text[i] == "\\":
                    i += 2
                    continue
                if text[i] == '"':
                    i += 1
                    break
                i += 1
            raw = text[start:i]
            try:
                payload: Any = json.loads(raw)
            except ValueError:
                payload = raw
            j = i
            while j < n and text[j] in _WS:
                j += 1
            is_key = j < n and text[j] == ":"
            yield ("key" if is_key else "string"), payload, start
            continue
        if ch in "{[":
            yield "open", ch, i
            i += 1
            continue
        if ch in "}]":
            yield "close", ch, i
            i += 1
            continue
        if ch in ":,":
            i += 1
            continue
        if ch == "-" and text.startswith("-Infinity", i):
            yield "const", "-Infinity", i
            i += len("-Infinity")
            continue
        if ch == "-" or ch.isdigit():
            start = i
            while i < n and text[i] in _NUM_CHARS:
                i += 1
            yield "number", text[start:i], start
            continue
        start = i
        while i < n and text[i] not in _WS and text[i] not in '{}[],:"':
            i += 1
        yield "const", text[start:i], start


def _line_col(text: str, offset: int) -> tuple[int, int]:
    """1-based строка и колонка для смещения."""
    prefix = text[:offset]
    return prefix.count("\n") + 1, offset - (prefix.rfind("\n") + 1) + 1


def _duplicate_key_offset(text: str, key: str | None) -> int | None:
    """Смещение **второго** вхождения ключа внутри того же объекта."""
    stack: list[set[str]] = []
    for kind, payload, offset in _iter_tokens(text):
        if kind == "open" and payload == "{":
            stack.append(set())
        elif kind == "close" and payload == "}":
            if stack:
                stack.pop()
        elif kind == "key" and stack:
            seen = stack[-1]
            if payload in seen:
                if payload == key:
                    return offset
            else:
                seen.add(payload)
    return None


def _constant_offset(text: str, name: str | None) -> int | None:
    for kind, payload, offset in _iter_tokens(text):
        if kind == "const" and payload == name:
            return offset
    return None


def _depth_limit_offset(text: str, max_depth: int) -> int | None:
    """Где вложенность впервые превысила лимит.

    ``_depth()`` считает глубину значений: у k вложенных контейнеров она равна
    k-1, поэтому порог здесь — ``max_depth + 1`` открывающих скобок.
    """
    depth = 0
    for kind, _payload, offset in _iter_tokens(text):
        if kind == "open":
            depth += 1
            if depth > max_depth + 1:
                return offset
        elif kind == "close":
            depth = max(depth - 1, 0)
    return None


def _located(text: str, code: str, message: str, offset: int | None) -> "JsonError":
    if offset is None:
        return JsonError(code, message)
    line, column = _line_col(text, offset)
    return JsonError(code, message, line, column)


def _depth(value: Any) -> int:
    """Iterative nesting depth (no recursion limit issues)."""
    max_depth = 0
    stack: list[tuple[Any, int]] = [(value, 0)]
    while stack:
        current, depth = stack.pop()
        if depth > max_depth:
            max_depth = depth
        if isinstance(current, dict):
            stack.extend((v, depth + 1) for v in current.values())
        elif isinstance(current, list):
            stack.extend((v, depth + 1) for v in current)
    return max_depth


class JsonError(str):
    """Parse error that also carries a source position.

    Subclasses ``str`` so every existing consumer (``"code" in err``,
    ``err.partition(": ")``, equality against literals) keeps working, while
    callers that can report locations get ``line``/``column`` for free.
    """

    code: str
    message: str
    line: int | None
    column: int | None

    def __new__(cls, code: str, message: str, line: int | None = None, column: int | None = None) -> "JsonError":
        self = super().__new__(cls, f"{code}: {message}")
        self.code = code
        self.message = message
        self.line = line
        self.column = column
        return self


def parse_json(text: str, max_depth: int = 128) -> tuple[Any, list[JsonError]]:
    """Return (value, errors). Duplicate keys, invalid constants and depth
    overflow are errors; the value is None whenever errors is non-empty."""
    if text.startswith("\ufeff"):
        text = text[1:]
    try:
        value = json.loads(text, object_pairs_hook=_no_duplicates, parse_constant=_reject_constant)
    except DuplicateKeyError as exc:
        return None, [_located(text, "json.duplicate_key", str(exc),
                               _duplicate_key_offset(text, exc.key))]
    except _InvalidConstant as exc:
        return None, [_located(text, "json.invalid_constant", str(exc),
                               _constant_offset(text, exc.name))]
    except json.JSONDecodeError as exc:
        # exc.msg alone: the full str(exc) repeats "line N column M (char K)",
        # which would duplicate the structured location.
        return None, [JsonError("json.syntax_error", exc.msg, exc.lineno, exc.colno)]
    except RecursionError:
        return None, [_located(text, "json.too_deep", "parser recursion limit exceeded",
                               _depth_limit_offset(text, max_depth))]
    depth = _depth(value)  # iterative: cannot RecursionError on hostile nesting
    if depth > max_depth:
        return None, [_located(text, "json.too_deep",
                               f"nesting depth {depth} exceeds limit {max_depth}",
                               _depth_limit_offset(text, max_depth))]
    return value, []


_ARRAY_INDEX_RE = re.compile(r"^(0|[1-9][0-9]*)$")


def resolve_pointer(value: Any, pointer: str) -> Any:
    """Resolve an RFC 6901 JSON Pointer. Raises KeyError/IndexError on miss.

    ``""`` refers to the whole document; ``"/"`` refers to the member with
    the empty-string key. Array indices must be canonical (no leading zeros,
    no negatives); ``"-"`` (past-the-end) is a miss.
    """
    if pointer == "":
        return value
    if not pointer.startswith("/"):
        raise KeyError(f"Invalid JSON Pointer: {pointer}")
    current = value
    for raw_part in pointer[1:].split("/"):
        part = raw_part.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict):
            if part not in current:
                raise KeyError(part)
            current = current[part]
        elif isinstance(current, list):
            if not _ARRAY_INDEX_RE.match(part):
                raise KeyError(part)
            index = int(part)
            if index >= len(current):
                raise IndexError(part)
            current = current[index]
        else:
            raise KeyError(part)
    return current


def validate_against_schema(instance: Any, schema: dict[str, Any]) -> list[str]:
    """Validate instance against a JSON Schema (2020-12). Returns messages."""
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(instance), key=lambda e: list(e.absolute_path))
    messages: list[str] = []
    for error in errors:
        path = "/".join(str(p) for p in error.absolute_path)
        messages.append(f"/{path}: {error.message}" if path else f"/: {error.message}")
    return messages
