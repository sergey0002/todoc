"""Folder self-description: ``.config.json`` per folder (idea folder-config).

Файлы — истина: конфиги читаются на лету при выводе и скоринге (P1/P2) —
никакого постоянного индекса папок в этой фазе. Ничего не исполняется
(P3/P10). Отсутствие конфига — не ошибка. Fail-open на вывод / fail-closed на
валидацию: конфиг с error-диагностикой исключается из вывода и скоринга, но
папка печатается как раньше, а диагностика видна в ``validate``. Unknown-поля
игнорируются конфигом (он продолжает работать), но репортуются — сценарий
«битый конфиг» из идеи. Служебный файл: ``.config.json`` исключён из индекса
документов (scanner.py), читается только этим модулем и CLI-выводом.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from todoc.adapters.filesystem.scanner import HARD_EXCLUDE_DIRS
from todoc.adapters.formats.jsonfmt import parse_json

CONFIG_NAME = ".config.json"

_KNOWN_FIELDS = {"schema_version", "title", "aliases", "description",
                 "order", "icon", "lang", "tags"}

_TITLE_MAX = 80
_ALIASES_MAX = 500
_DESCRIPTION_MAX = 500
_ICON_MAX = 50
_LANG_MAX = 10
_TAG_MAX = 80
_ALIAS_ELEMENT_MAX = 80

_THRESHOLD = 0.25


@dataclass
class FolderConfig:
    """Одна папка с валидным конфигом: ключ — rel-путь папки от DATA_ROOT."""

    path: str
    title: str
    aliases: list[str] = field(default_factory=list)
    description: str = ""
    order: int | None = None
    icon: str | None = None
    lang: str | None = None
    tags: list[str] = field(default_factory=list)


def _diag(path: str, code: str, message: str, line: int | None = None,
          severity: str = "error", suggested_fixes: list[str] | None = None) -> dict[str, Any]:
    """House-форма диагностики (cf. Diagnostic.to_dict); dataset_id/id ставит валидатор."""
    return {
        "dataset_id": "", "id": "", "code": code, "severity": severity, "path": path,
        "message": message, "location": {"line": line} if line else {},
        "evidence": "", "suggested_fixes": suggested_fixes or [],
    }


def _key_line(text: str, key: str) -> int | None:
    r"""Строка первого вхождения JSON-ключа (локальная копия логики validator._key_location).

    BUG-010: ключ, записанный unicode-escape ("\u006frder"), литералом не находится —
    вторым проходом ищем посимвольную форму ``(?:c|\uXXXX)``.
    """
    needle = f'"{key}"'
    for lineno, line in enumerate(text.splitlines(), start=1):
        if needle in line:
            return lineno
    pattern = re.compile('"' + "".join(f"(?:{re.escape(ch)}|\\\\u{ord(ch):04x})" for ch in key) + '"',
                         re.IGNORECASE)
    for lineno, line in enumerate(text.splitlines(), start=1):
        if pattern.search(line):
            return lineno
    return None


def _folders_under(root: Path) -> list[Path]:
    """Все папки под root (кроме корня), отсортированные по rel-пути; детерминированно (P5)."""
    found: list[Path] = []
    if not root.is_dir():
        return found
    stack = [root]
    while stack:
        current = stack.pop()
        try:
            entries = sorted(os.scandir(current), key=lambda e: e.name)
        except OSError:
            continue
        for entry in entries:
            if entry.name in HARD_EXCLUDE_DIRS or entry.name.startswith("."):
                continue  # служебные и dot-папки не описываем и не обходим
            if not entry.is_dir(follow_symlinks=False):
                continue
            child = Path(entry.path)
            found.append(child)
            stack.append(child)
    return sorted(found, key=lambda p: p.relative_to(root).as_posix())


def load_folder_configs(root: Path) -> tuple[dict[str, FolderConfig], list[dict[str, Any]]]:
    """Прочитать все ``.config.json``: ``(configs по rel-пути папки, diagnostics)``.

    Конфиг с error-диагностикой в configs не попадает (fail-open на вывод);
    unknown-поля не исключают конфиг — поле игнорируется, но репортуется.
    """
    configs: dict[str, FolderConfig] = {}
    diags: list[dict[str, Any]] = []
    for folder in _folders_under(root):
        cfg_file = folder / CONFIG_NAME
        if not cfg_file.is_file():
            continue
        rel_cfg = f"{folder.relative_to(root).as_posix()}/{CONFIG_NAME}"
        try:
            text = cfg_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            diags.append(_diag(rel_cfg, "folder.config.invalid_json",
                               "конфиг не читается как UTF-8.", 1,
                               ["Пересохраните файл в UTF-8 без BOM."]))
            continue
        value, errors = parse_json(text)
        if errors:
            first = errors[0]
            diags.append(_diag(rel_cfg, "folder.config.invalid_json", str(first),
                               getattr(first, "line", None),
                               ["Исправьте JSON: файл должен быть объектом с schema_version=1."]))
            continue
        if not isinstance(value, dict):
            diags.append(_diag(rel_cfg, "folder.config.invalid_json",
                               "конфиг должен быть JSON-объектом.", 1))
            continue
        unknown = sorted(set(value) - _KNOWN_FIELDS)
        if unknown:
            diags.append(_diag(rel_cfg, "folder.config.unknown_field",
                               f"неизвестные поля: {', '.join(unknown)}.", _key_line(text, unknown[0]),
                               ["Удалите поле или обновите todoc."]))
        broken = False

        def _bad(key: str, msg: str) -> None:
            nonlocal broken
            broken = True
            diags.append(_diag(rel_cfg, "folder.config.bad_type" if key != "order" else "folder.config.bad_order",
                               msg, _key_line(text, key)))

        schema_version = value.get("schema_version")
        if not isinstance(schema_version, int) or isinstance(schema_version, bool) or schema_version != 1:
            _bad("schema_version", "schema_version должен быть 1 (int).")
        title = value.get("title")
        if not isinstance(title, str) or not 1 <= len(title) <= _TITLE_MAX:
            _bad("title", f"title: непустая строка ≤{_TITLE_MAX} симв.")
        aliases_raw = value.get("aliases")
        aliases: list[str] = []
        if aliases_raw is not None:
            if not isinstance(aliases_raw, str) or len(aliases_raw) > _ALIASES_MAX:
                _bad("aliases", f"aliases: строка ≤{_ALIASES_MAX} симв., разделитель «|».")
            else:
                seen: set[str] = set()
                for element in aliases_raw.split("|"):
                    element = element.strip()
                    if not element:
                        continue  # пустые элементы отбрасываются молча — видно глазом в файле
                    if len(element) > _ALIAS_ELEMENT_MAX:
                        diags.append(_diag(rel_cfg, "folder.config.bad_alias",
                                           f"alias «{element[:24]}…» > {_ALIAS_ELEMENT_MAX} симв.",
                                           _key_line(text, "aliases")))
                        broken = True
                        continue
                    if element in seen:
                        diags.append(_diag(rel_cfg, "folder.config.duplicate_alias",
                                           f"alias «{element}» повторяется в этой папке.",
                                           _key_line(text, "aliases"), severity="warning"))
                        continue
                    seen.add(element)
                    aliases.append(element)
        description = value.get("description")
        if description is not None and (not isinstance(description, str) or len(description) > _DESCRIPTION_MAX):
            _bad("description", f"description: строка ≤{_DESCRIPTION_MAX} симв.")
        order = value.get("order")
        if order is not None and (not isinstance(order, int) or isinstance(order, bool)):
            diags.append(_diag(rel_cfg, "folder.config.bad_order", "order должен быть int.",
                               _key_line(text, "order")))
            broken = True
        icon = value.get("icon")
        if icon is not None and (not isinstance(icon, str) or len(icon) > _ICON_MAX):
            _bad("icon", f"icon: строка ≤{_ICON_MAX} симв.")
        lang = value.get("lang")
        if lang is not None and (not isinstance(lang, str) or len(lang) > _LANG_MAX):
            _bad("lang", f"lang: строка ≤{_LANG_MAX} симв.")
        tags_raw = value.get("tags")
        tags: list[str] = []
        if tags_raw is not None:
            if not isinstance(tags_raw, list) or any(
                    not isinstance(t, str) or not 1 <= len(t) <= _TAG_MAX for t in tags_raw):
                _bad("tags", f"tags: список строк по 1–{_TAG_MAX} симв.")
            else:
                tags = list(tags_raw)
        if broken:
            continue  # fail-open: конфиг с error-диагностикой не участвует в выводе/скоринге
        configs[folder.relative_to(root).as_posix()] = FolderConfig(
            path=folder.relative_to(root).as_posix(),
            title=str(title), aliases=aliases, description=str(description or ""),
            order=order, icon=icon if isinstance(icon, str) else None,
            lang=lang if isinstance(lang, str) else None, tags=tags)
    return configs, diags


def validate_folder_configs(root: Path) -> list[dict[str, Any]]:
    """Полная валидация конфигов папок: load-диагностики + cross-папочные (alias_collision)."""
    configs, diags = load_folder_configs(root)
    owners: dict[str, list[str]] = {}
    for rel in sorted(configs):
        for alias in configs[rel].aliases:
            owners.setdefault(alias.lower(), []).append(rel)
    for alias, folders in sorted(owners.items()):
        if len(folders) > 1:
            diags.append(_diag(f"{folders[0]}/{CONFIG_NAME}", "folder.config.alias_collision",
                               f"alias «{alias}» указан в папках: {', '.join(folders)}.",
                               None, severity="warning",
                               suggested_fixes=["Уточните aliases, чтобы разделить домены; "
                                                "обе папки участвуют в поиске с равным score."]))
    return diags


def score_folder_configs(configs: dict[str, FolderConfig],
                         query: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Фаза A: детерминированный скоринг папок по запросу (без зависимостей).

    Веса §3 плана: точный alias подстрокой +1.0 (× бонус длины 1+0.1·(слов−1)),
    пословное пересечение alias +0.3 за слово, слова title/description/tags
    +0.2 за слово; нормировка score/max → 0..1; порог 0.25; tie-break
    order → путь. CLI отдаёт ranked+discarded с reason — выбор не его
    ответственность.
    """
    from todoc.application.search import tokenize  # lazy: search.py импортирует этот модуль

    q_tokens = set(tokenize(query))
    q_lower = query.lower()
    raw: list[tuple[FolderConfig, float, list[str], list[str]]] = []
    for rel in sorted(configs):
        cfg = configs[rel]
        score = 0.0
        reasons: list[str] = []
        alias_words: list[str] = []
        exact: str | None = None
        for alias in cfg.aliases:
            a_lower = alias.lower()
            if a_lower and a_lower in q_lower:
                score += 1.0 * (1.0 + 0.1 * (len(alias.split()) - 1))
                exact = alias
            hits = [w for w in tokenize(alias) if w in q_tokens]
            score += 0.3 * len(hits)
            alias_words.extend(hits)
        if exact:
            reasons.append(f"exact alias «{exact}»")
        elif alias_words:
            reasons.append(f"words: {', '.join(dict.fromkeys(alias_words))} (aliases)")
        field_tokens = set(tokenize(" ".join([cfg.title, cfg.description, " ".join(cfg.tags)])))
        field_hits = sorted(q_tokens & field_tokens)
        score += 0.2 * len(field_hits)
        if field_hits and not reasons:
            reasons.append(f"title/desc/tags: {', '.join(field_hits[:3])}")
        raw.append((cfg, score, reasons, field_hits))
    max_score = max((s for _, s, _, _ in raw), default=0.0)
    items: list[dict[str, Any]] = []
    for cfg, s, reasons, _field_hits in raw:
        norm = round(s / max_score, 4) if max_score > 0 else 0.0
        # BUG-009: raw-величина рядом с нормированной — единственный кандидат больше не маскируется 1.0
        items.append({"path": cfg.path, "title": cfg.title, "score": norm, "score_raw": round(s, 4),
                      "reason": "; ".join(reasons[:2]), "order": cfg.order})
    items.sort(key=lambda x: (-x["score"], x["order"] if x["order"] is not None else 10**9, x["path"]))
    candidates = [x for x in items if x["score"] >= _THRESHOLD]
    discarded = [x for x in items if x["score"] < _THRESHOLD]
    return candidates, discarded
