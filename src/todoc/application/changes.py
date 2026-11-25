"""Записи изменений и дельты: жизненный цикл, проверка применимости, применение.

Изменение — обычная запись ``entity_type: change`` (план §5.3), поэтому валидация схемы,
``records query --where status=…`` и обход графа ``blocked_by`` достаются бесплатно.

Дельта — markdown-файл ``doc_type: delta`` с операциями ``## ADDED: <якорь>``,
``## MODIFIED: <якорь>`` и ``## REMOVED: <якорь>`` (план §5.4). Префиксное совпадение
заголовков уже работает в валидаторе, поэтому отдельный парсер формата не нужен.

Главное отличие от OpenSpec: ``validate`` проверяет не формат дельты, а **применимость к
живому состоянию** — цель существует, якорь найден, ``base_hash`` совпал, пробное
применение не ломает документ.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from todoc.adapters.filesystem.scanner import atomic_write, file_hash
from todoc.adapters.formats.jsonfmt import validate_against_schema
from todoc.adapters.formats.markdown import parse_markdown, section_bounds
from todoc.domain.models import Diagnostic
from todoc.errors import ValidationError

SCHEMA_VERSION = 1
DELTA_OPERATIONS = ("ADDED", "MODIFIED", "REMOVED")
STATUS_FLOW = ("proposed", "in_progress", "blocked", "applied", "archived", "reverted")


def _utc_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# --- расположение ------------------------------------------------------------


def changes_dir(root: Path) -> Path:
    return root / "changes"


#: Транслитерация кириллицы для идентификаторов: без неё любой русский заголовок
#: схлопывался бы в одно и то же имя, и второе изменение не открылось бы.
TRANSLIT: dict[str, str] = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e", "ж": "zh",
    "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o",
    "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f", "х": "h", "ц": "c",
    "ч": "ch", "ш": "sh", "щ": "sch", "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu",
    "я": "ya",
}


def slugify(title: str) -> str:
    """Идентификатор изменения из заголовка: только ``[a-z0-9-]``, детерминированно.

    Кириллица транслитерируется. Если после нормализации ничего не осталось (заголовок
    из одних знаков препинания), берётся короткий хеш — иначе разные изменения получили
    бы одно имя и второе не открылось бы.
    """
    import hashlib

    lowered = title.strip().lower()
    translit = "".join(TRANSLIT.get(ch, ch) for ch in lowered)
    slug = re.sub(r"[^a-z0-9]+", "-", translit).strip("-")
    if slug:
        return slug
    return "change-" + hashlib.sha256(title.encode("utf-8")).hexdigest()[:8]


def archive_dir(root: Path) -> Path:
    return changes_dir(root) / "archive"


def change_dir(root: Path, change_id: str) -> Path:
    """Папка изменения: активная, а после архивации — в ``changes/archive/`` (§4).

    Ищется по файлу записи, а не по имени папки: в архиве имя дополнено датой,
    поэтому ``change show`` обязан находить изменение и после переноса.
    """
    slug = change_id.split(":", 1)[-1]
    active = changes_dir(root) / slug
    if (active / "change.json").is_file():
        return active
    base = archive_dir(root)
    if base.is_dir():
        for folder in sorted(base.iterdir()):
            if folder.is_dir() and folder.name.endswith("-" + slug) \
                    and (folder / "change.json").is_file():
                return folder
    return active


def deltas_dir(root: Path, change_id: str) -> Path:
    return change_dir(root, change_id) / "deltas"


def record_path(root: Path, change_id: str) -> Path:
    return change_dir(root, change_id) / "change.json"


# --- жизненный цикл ----------------------------------------------------------


def change_id_for(title: str) -> str:
    """Идентификатор изменения по заголовку.

    Единственное место, где заголовок превращается в id: вызывающему (CLI) он нужен
    до создания записи — чтобы события журнала сразу несли ``change_id``.
    """
    return f"change:{slugify(title)}"


def open_change(root: Path, title: str, *, blocked_by: tuple[str, ...] = (),
                artifacts: tuple[str, ...] = (), status: str = "proposed",
                baseline: dict[str, Any] | None = None,
                history: Any = None) -> dict[str, Any]:
    """Создаёт запись изменения и папку для дельт. Существующее не перезаписывает.

    ``baseline`` — снимок состояния на момент открытия: хеши артефактов и коды
    диагностик. Без него ``verify`` не смог бы сказать, появились ли диагностики
    после открытия, а не были ли они там всегда.
    """
    from todoc.errors import ConflictError

    change_id = change_id_for(title)
    folder = change_dir(root, change_id)
    if record_path(root, change_id).is_file():
        raise ConflictError(f"Изменение уже существует: {change_id}", "change.id_invalid")
    (folder / "deltas").mkdir(parents=True, exist_ok=True)

    record: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION, "record_id": change_id, "entity_type": "change",
        "title": title, "status": status, "created_at": _utc_now(), "applied_at": None,
        "artifacts": list(artifacts),
        "relations": [{"type_id": "blocked_by", "target": {"kind": "record", "id": dep}}
                      for dep in blocked_by],
    }
    if baseline:
        record["baseline"] = baseline
    atomic_write(record_path(root, change_id), json.dumps(record, indent=2, ensure_ascii=False) + "\n")

    # §4: папка изменения — это намерение человека, оно читается в Obsidian и проходит
    # review. proposal.md и tasks.md создаются сразу: verify проверяет задачи, а без
    # файла задач проверка полноты молча degenerates в «замечаний нет».
    proposal = folder / "proposal.md"
    if not proposal.exists():
        atomic_write(proposal, f"---\ntitle: \"{title}\"\ndoc_type: note\n---\n\n"
                               f"# {title}\n\n## Суть\n\nОпишите, зачем это изменение.\n")
    tasks = folder / "tasks.md"
    if not tasks.exists():
        # Пункты задач не выдумываются: незакрытый пункт — это находка verify, и
        # шаблонная задача сделала бы каждое свежее изменение «неполным» по умолчанию.
        atomic_write(tasks, f"---\ntitle: \"Задачи: {title}\"\ndoc_type: note\n---\n\n"
                            f"# Задачи: {title}\n\n## Суть\n\n"
                            f"Добавьте пункты вида `- [ ] …`; `change verify` считает закрытые.\n")

    if history is not None:
        history.record(str(record_path(root, change_id).relative_to(root)), None,
                       record_path(root, change_id).read_bytes(), "change.open",
                       f"change open {change_id}")
    return record


def load_change(root: Path, change_id: str) -> dict[str, Any] | None:
    path = record_path(root, change_id)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def list_changes(root: Path, status: str | None = None) -> list[dict[str, Any]]:
    """Активные и архивные изменения. ``record_id`` читается из файла, а не из имени
    папки: в архиве имя дополнено датой (§4)."""
    base = changes_dir(root)
    if not base.is_dir():
        return []
    folders = [f for f in sorted(base.iterdir()) if f.is_dir() and f.name != "archive"]
    archive = archive_dir(root)
    if archive.is_dir():
        folders += [f for f in sorted(archive.iterdir()) if f.is_dir()]
    out: list[dict[str, Any]] = []
    for folder in folders:
        path = folder / "change.json"
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        if status and str(data.get("status")) != status:
            continue
        out.append(data)
    return out


def set_status(root: Path, change_id: str, status: str, **extra: Any) -> dict[str, Any]:
    record = load_change(root, change_id)
    if record is None:
        raise ValidationError(f"Изменение не найдено: {change_id}", "change.not_found")
    if status not in STATUS_FLOW:
        raise ValidationError(f"Недопустимый статус {status!r} (можно: {', '.join(STATUS_FLOW)})",
                              "change.id_invalid")
    record["status"] = status
    record.update(extra)
    atomic_write(record_path(root, change_id), json.dumps(record, indent=2, ensure_ascii=False) + "\n")
    return record


# --- разбор дельты -----------------------------------------------------------


def parse_delta(text: str) -> dict[str, Any]:
    """Разбирает дельту на операции. Формат — из плана §5.4."""
    doc = parse_markdown(text)
    ops: list[dict[str, Any]] = []
    lines = text.splitlines()
    # Операции — заголовки второго уровня вида "## OP: <якорь>". Идём по заголовкам
    # документа, а не по регулярке, чтобы тело раздела не могло подделать операцию.
    for index, heading in enumerate(doc.headings):
        if heading.level != 2 or ":" not in heading.title:
            continue
        operation, _, anchor = heading.title.partition(":")
        operation = operation.strip().upper()
        if operation not in DELTA_OPERATIONS:
            continue
        end = len(lines)
        for later in doc.headings[index + 1:]:
            if later.level <= heading.level:
                end = later.line - 1
                break
        body = "\n".join(lines[heading.line:end]).strip("\n")
        ops.append({"op": operation, "anchor": anchor.strip(), "body": body,
                    "line": heading.line})
    # YAML-lite во front matter всегда отдаёт строки, поэтому числовой order приводим
    # к int: иначе ключ сортировки его не увидит и порядок применения окажется случайным.
    raw_order = doc.front_matter.get("order")
    order: int | None = None
    if isinstance(raw_order, str) and raw_order.strip().lstrip("-").isdigit():
        order = int(raw_order.strip())
    return {"target": str(doc.front_matter.get("target") or ""),
            "base_hash": doc.front_matter.get("base_hash"),
            "order": order,
            "ops": ops}


def apply_ops(text: str, ops: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
    """Применяет операции к тексту. Возвращает ``(новый текст, ошибки)``.

    Каждая операция перечитывает документ заново: правка смещает номера строк, и
    применение «пачкой» по старым границам тихо порвало бы файл.
    """
    errors: list[dict[str, Any]] = []
    for operation in ops:
        op, anchor, body = operation["op"], operation["anchor"], operation["body"]
        if op == "ADDED":
            text = text.rstrip("\n") + f"\n\n{anchor}\n\n{body}\n" if body else \
                text.rstrip("\n") + f"\n\n{anchor}\n"
            continue
        found = section_bounds(text, anchor)
        if found is None:
            errors.append({"code": "change.delta_anchor_missing", "anchor": anchor, "op": op})
            continue
        start, end = found
        lines = text.splitlines()
        if op == "REMOVED":
            lines = lines[: start - 1] + lines[end:]
        else:  # MODIFIED — заголовок сохраняется, тело заменяется
            # Пустые строки вокруг тела обязательны: без них заголовок следующего
            # раздела прилипает к тексту и markdown разбирается иначе.
            lines = lines[:start] + [""] + body.splitlines() + [""] + lines[end:]
        text = "\n".join(lines).rstrip("\n") + "\n"
    return text, errors


# --- проверка применимости к живому состоянию --------------------------------


def _diag(dataset_id: str, rel_path: str, code: str, message: str, *,
          severity: str = "error", location: dict[str, Any] | None = None,
          evidence: str = "") -> Diagnostic:
    from todoc.application.validator import stable_id

    return Diagnostic(dataset_id=dataset_id, id=stable_id(rel_path, code, message[:40]),
                      code=code, severity=severity, path=rel_path,
                      location=location or {}, evidence=evidence,
                      message=message, suggested_fixes=())


def collect_deltas(root: Path, change_id: str) -> list[dict[str, Any]]:
    """Дельты изменения, отсортированные по ``order``, затем по имени файла."""
    folder = deltas_dir(root, change_id)
    if not folder.is_dir():
        return []
    out: list[dict[str, Any]] = []
    for path in sorted(folder.glob("*.md")):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        delta = parse_delta(text)
        delta["path"] = path.relative_to(root).as_posix()
        out.append(delta)

    def key(item: dict[str, Any]) -> tuple[int, str]:
        order = item.get("order")
        return (int(order) if isinstance(order, int) else 0, str(item["path"]))

    return sorted(out, key=key)


def validate_change(root: Path, change_id: str, dataset_id: str = "",
                    descriptor_lookup: Any = None) -> list[Diagnostic]:
    """Проверяет применимость дельт к **живому состоянию**, а не формат дельты.

    Это главное отличие от OpenSpec: ``openspec validate`` смотрит на разметку, а здесь
    проверяется, что цель существует, якорь находится, ``base_hash`` не уехал и пробное
    применение не ломает структуру документа.
    """
    record = load_change(root, change_id)
    if record is None:
        return [_diag(dataset_id, f"changes/{change_id.split(':', 1)[-1]}/change.json",
                      "change.not_found", f"Изменение не найдено: {change_id}")]
    if str(record.get("status")) == "applied":
        return [_diag(dataset_id, str(record_path(root, change_id).relative_to(root)),
                      "change.already_applied",
                      f"Изменение {change_id} уже применено; повторное применение запрещено")]

    diags: list[Diagnostic] = []
    for dep in record.get("relations") or []:
        if not isinstance(dep, dict) or dep.get("type_id") != "blocked_by":
            continue
        dep_id = str((dep.get("target") or {}).get("id") or "")
        dep_record = load_change(root, dep_id) if dep_id.startswith("change:") else None
        if dep_record is None or str(dep_record.get("status")) not in ("archived", "applied"):
            diags.append(_diag(
                dataset_id, str(record_path(root, change_id).relative_to(root)),
                "change.blocked_by_unresolved",
                f"Зависимость {dep_id} не завершена (нужен статус archived или applied)",
                severity="warning"))

    deltas = collect_deltas(root, change_id)
    by_target: dict[str, list[dict[str, Any]]] = {}
    for delta in deltas:
        by_target.setdefault(delta["target"], []).append(delta)

    for target, group in by_target.items():
        rel = str(record_path(root, change_id).relative_to(root))
        if not target:
            diags.append(_diag(dataset_id, rel, "change.delta_target_missing",
                               "Дельта без target: применять некуда"))
            continue
        if len(group) > 1 and any(d.get("order") is None for d in group):
            diags.append(_diag(
                dataset_id, rel, "change.apply_order_ambiguous",
                f"{len(group)} дельты на {target} без явного order — результат неоднозначен"))
        target_path = root / target
        if not target_path.is_file():
            diags.append(_diag(dataset_id, rel, "change.delta_target_missing",
                               f"Целевой файл дельты не существует: {target}"))
            continue
        try:
            current = target_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            diags.append(_diag(dataset_id, rel, "change.delta_target_missing",
                               f"Целевой файл не читается: {target}"))
            continue
        actual_hash = file_hash(target_path)
        for delta in group:
            expected = delta.get("base_hash")
            if isinstance(expected, str) and expected and expected != actual_hash:
                diags.append(_diag(
                    dataset_id, delta["path"], "change.base_hash_mismatch",
                    f"Файл {target} ушёл из-под дельты: ожидался {expected[:19]}…, "
                    f"сейчас {actual_hash[:19]}…",
                    evidence=f"base_hash дельты против текущего хеша файла"))
            result, errors = apply_ops(current, delta["ops"])
            for error in errors:
                diags.append(_diag(
                    dataset_id, delta["path"], error["code"],
                    f"Якорь не найден в {target}: {error['anchor']} (операция {error['op']})"))
            if not errors:
                diags.extend(_structure_after_apply(root, dataset_id, target, result,
                                                    descriptor_lookup))
            current = result
    return diags


def _structure_after_apply(root: Path, dataset_id: str, rel_path: str, text: str,
                           descriptor_lookup: Any) -> list[Diagnostic]:
    """Ломает ли пробное применение структуру документа.

    Проверяется сам получившийся документ против его ``doc_type`` (разделы и схема
    front matter), а не весь датасет: это детерминированно, дёшево и ловит реальный
    класс дефектов — дельта, после которой документ не соответствует своему типу.
    """
    if descriptor_lookup is None:
        return []
    from todoc.adapters.formats.markdown import parse_markdown
    from todoc.application.validator import _check_structure

    doc = parse_markdown(text)
    descriptor = descriptor_lookup(doc.front_matter, rel_path)
    if not isinstance(descriptor, dict):
        return []
    diags = list(_check_structure(dataset_id, rel_path, doc.headings, descriptor))
    schema = descriptor.get("schema_data")
    if isinstance(schema, dict) and doc.front_matter:
        for message in validate_against_schema(doc.front_matter, schema):
            _pointer, _, rest = message.partition(": ")
            diags.append(_diag(dataset_id, rel_path, "change.post_apply_invalid",
                               rest or message, evidence="схема doc_type после применения"))
    return diags


# --- verify: completeness / correctness / coherence --------------------------


def verify_change(root: Path, change_id: str) -> dict[str, Any]:
    """Детерминированный аналог ``converge``: три измерения, без модели (план §17.3).

    Результат воспроизводим и может быть гейтом в CI — в отличие от проверки моделью.
    """
    record = load_change(root, change_id)
    if record is None:
        return {"change_id": change_id, "found": False}
    baseline = record.get("baseline") if isinstance(record.get("baseline"), dict) else {}
    findings: list[dict[str, Any]] = []

    # completeness: задачи закрыты, артефакты действительно изменены
    tasks = change_dir(root, change_id) / "tasks.md"
    if tasks.is_file():
        try:
            body = tasks.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            body = ""
        unchecked = re.findall(r"^\s*[-*]\s+\[ \]", body, flags=re.M)
        if unchecked:
            findings.append({"dimension": "completeness", "severity": "error",
                             "message": f"Не закрыто задач: {len(unchecked)} в tasks.md"})
    base_hashes = baseline.get("artifacts") if isinstance(baseline.get("artifacts"), dict) else {}
    for artifact in record.get("artifacts") or []:
        path = root / str(artifact)
        known = base_hashes.get(str(artifact))
        if known is None:
            continue
        current = file_hash(path) if path.is_file() else ""
        if current == known:
            findings.append({"dimension": "completeness", "severity": "warning",
                             "message": f"Артефакт не изменён с момента открытия: {artifact}"})

    # correctness: текущее состояние соответствует дельтам (по якорям).
    # Смысл есть только после применения: у ещё не применённого изменения состояние
    # и обязано расходиться с дельтами, иначе проверка превращается в шум.
    status = str(record.get("status"))
    for delta in collect_deltas(root, change_id) if status in ("applied", "in_progress") else []:
        target = delta["target"]
        path = root / target if target else None
        if path is None or not path.is_file():
            findings.append({"dimension": "correctness", "severity": "error",
                             "message": f"Цель дельты отсутствует: {target or '(нет target)'}"})
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for operation in delta["ops"]:
            found = section_bounds(text, operation["anchor"]) is not None
            wanted = operation["op"] != "REMOVED"
            if found != wanted:
                findings.append({
                    "dimension": "correctness", "severity": "error",
                    "message": f"{operation['op']} {operation['anchor']}: якорь "
                               f"{'не найден' if wanted else 'всё ещё присутствует'} в {target}"})

    # coherence: диагностик не больше, чем было на момент открытия
    base_codes = baseline.get("diagnostics")
    if isinstance(base_codes, list):
        from todoc.service import DatasetContext

        context = DatasetContext(root)
        _folders, _docs, _records, _relations, diags = context.scan_and_validate()
        current_codes = sorted(f"{d['code']}:{d['path']}" for d in diags)
        extra = [c for c in current_codes if c not in set(base_codes)]
        if extra:
            findings.append({"dimension": "coherence", "severity": "error",
                             "message": f"Новых диагностик относительно открытия: {len(extra)}",
                             "items": extra[:10]})
    return {"change_id": change_id, "found": True, "status": record.get("status"),
            "findings": findings, "clean": not findings}


# --- применение: bundle-транзакция -------------------------------------------


def plan_apply(root: Path, change_id: str, dataset_id: str = "",
               descriptor_lookup: Any = None) -> dict[str, Any]:
    """План применения: что и как изменится. Ничего не пишет.

    Все файлы считаются заранее и проверяются до первой записи — это и делает применение
    атомарным: если план не собрался, на диске не меняется ничего (K39).
    """
    record = load_change(root, change_id)
    if record is None:
        raise ValidationError(f"Изменение не найдено: {change_id}", "change.not_found")
    blocking = validate_change(root, change_id, dataset_id, descriptor_lookup)
    errors = [d for d in blocking if d.severity == "error"]
    if errors:
        return {"change_id": change_id, "applicable": False, "files": [],
                "diagnostics": [d.to_dict() for d in blocking]}

    files: list[dict[str, Any]] = []
    current_by_target: dict[str, str] = {}
    for delta in collect_deltas(root, change_id):
        target = delta["target"]
        path = root / target
        if target not in current_by_target:
            current_by_target[target] = path.read_text(encoding="utf-8")
        result, _errors = apply_ops(current_by_target[target], delta["ops"])
        current_by_target[target] = result
    for target, text in current_by_target.items():
        path = root / target
        files.append({"path": target, "current_hash": file_hash(path),
                      "new_hash": "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest(),
                      "content": text})
    return {"change_id": change_id, "applicable": True, "files": files,
            "diagnostics": [d.to_dict() for d in blocking]}


def apply_change(root: Path, change_id: str, *, apply: bool = False,
                 history: Any = None, dataset_id: str = "",
                 descriptor_lookup: Any = None,
                 expected_hashes: dict[str, str] | None = None) -> dict[str, Any]:
    """Применяет дельты изменения одной транзакцией.

    Атомарность (K39): сначала считаются все новые содержимые и проверяются все дельты,
    и только затем идёт запись. Если запись файла не удалась, уже записанные файлы
    возвращаются к исходным байтам — частичного применения не остаётся.
    """
    from todoc.errors import ConflictError

    plan = plan_apply(root, change_id, dataset_id, descriptor_lookup)
    if not plan["applicable"]:
        return {"change_id": change_id, "applied": False, "files": [],
                "diagnostics": plan["diagnostics"]}
    if not apply:
        return {"change_id": change_id, "applied": False, "preview": True,
                "files": [{k: v for k, v in f.items() if k != "content"} for f in plan["files"]],
                "diagnostics": plan["diagnostics"]}

    for item in plan["files"]:
        expected = (expected_hashes or {}).get(item["path"])
        if expected is not None and expected != item["current_hash"]:
            raise ConflictError(
                f"Хеш {item['path']} разошёлся: ожидался {expected}, сейчас {item['current_hash']}",
                "write.hash_mismatch")

    written: list[tuple[Path, bytes]] = []
    try:
        for item in plan["files"]:
            path = root / item["path"]
            written.append((path, path.read_bytes()))
            atomic_write(path, item["content"])
            if history is not None:
                history.record(item["path"], written[-1][1], item["content"].encode("utf-8"),
                               "change.apply", f"change apply {change_id}")
    except OSError as exc:
        for path, original in reversed(written):
            try:
                path.write_bytes(original)
            except OSError:
                # Откат тоже не удался — сообщаем честно, а не делаем вид, что чисто.
                raise ValidationError(
                    f"Применение {change_id} не удалось ({exc}) и откат {path} тоже не удался",
                    "change.post_apply_invalid") from exc
        raise ValidationError(f"Применение {change_id} отклонено: {exc}; файлы возвращены "
                              f"в исходное состояние", "change.post_apply_invalid") from exc

    record = set_status(root, change_id, "applied", applied_at=_utc_now())
    return {"change_id": change_id, "applied": True, "status": record["status"],
            "files": [{k: v for k, v in f.items() if k != "content"} for f in plan["files"]],
            "diagnostics": plan["diagnostics"]}


def archive_change(root: Path, change_id: str, tag: str | None = None,
                   history_root: Path | None = None,
                   history: Any = None) -> dict[str, Any]:
    """Переводит изменение в ``archived``, уносит папку в ``changes/archive/`` (§4)
    и опционально ставит метку на последнее событие."""
    record = set_status(root, change_id, "archived", archived_at=_utc_now())
    result: dict[str, Any] = {"change_id": change_id, "status": record["status"],
                              "archived_at": record["archived_at"], "tag": None,
                              "path": None}

    # §4: архив — это ``changes/archive/<YYYY-MM-DD>-<change-id>/``. Дата берётся из
    # archived_at, чтобы имя папки не зависело от порядка обхода каталога.
    source = changes_dir(root) / change_id.split(":", 1)[-1]
    if source.is_dir():
        day = str(record["archived_at"])[:10]
        target = archive_dir(root) / f"{day}-{change_id.split(':', 1)[-1]}"
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            source.rename(target)
        except OSError:
            # Перенос не удался (например, другая ФС): изменение всё равно архивировано
            # по статусу, а папка осталась на месте. Молча делать вид нельзя.
            result["archive_warning"] = f"не удалось перенести папку в {target}"
        else:
            result["path"] = str(target.relative_to(root))
            if history is not None:
                moved = target / "change.json"
                history.record(str(moved.relative_to(root)), None, moved.read_bytes(),
                               "change.archive", f"change archive {change_id}")
    if tag and history_root is not None:
        from todoc.adapters.history import journal
        from todoc.application.history import add_tag

        events = journal.read_events(history_root)
        if events:
            add_tag(history_root, tag, events[-1]["rev"], f"archive {change_id}")
            result["tag"] = tag
    return result


def revert_change(root: Path, change_id: str, *, apply: bool = False,
                  history: Any = None) -> dict[str, Any]:
    """Откат применения: файлы возвращаются к состоянию на момент открытия.

    Восстановление идёт по базовой линии изменения, а не по обратным дельтам: обратная
    дельта не существует для REMOVED, а базовый хеш — существует всегда.
    """
    record = load_change(root, change_id)
    if record is None:
        raise ValidationError(f"Изменение не найдено: {change_id}", "change.not_found")
    if str(record.get("status")) != "applied":
        raise ValidationError(
            f"Откатывать можно только применённое изменение, сейчас {record.get('status')!r}",
            "change.id_invalid")
    baseline = record.get("baseline") if isinstance(record.get("baseline"), dict) else {}
    hashes = baseline.get("artifacts") if isinstance(baseline.get("artifacts"), dict) else {}
    files: list[dict[str, Any]] = []
    for artifact in record.get("artifacts") or []:
        path = root / str(artifact)
        files.append({"path": str(artifact), "exists": path.is_file(),
                      "current_hash": file_hash(path) if path.is_file() else "",
                      "baseline_hash": hashes.get(str(artifact), "")})
    if not apply:
        return {"change_id": change_id, "applied": False, "preview": True, "files": files}

    restored: list[tuple[Path, bytes]] = []
    try:
        for item in files:
            path = root / item["path"]
            data, status = _baseline_content(root, item["path"])
            if data is None:
                code = ("history.object_missing" if status == "object_missing"
                        else "history.revision_unknown")
                raise ValidationError(
                    f"Не удалось восстановить {item['path']} из истории ({status})", code)
            restored.append((path, path.read_bytes()) if path.is_file() else (path, b""))
            atomic_write(path, data.decode("utf-8"))
            if history is not None:
                history.record(item["path"], restored[-1][1], data, "change.revert",
                               f"change revert {change_id}")
    except (OSError, ValidationError) as exc:
        for path, original in reversed(restored):
            try:
                path.write_bytes(original)
            except OSError:
                raise ValidationError(
                    f"Откат {change_id} не удался ({exc}) и восстановление {path} тоже",
                    "change.post_apply_invalid") from exc
        if isinstance(exc, ValidationError):
            raise
        raise ValidationError(f"Откат {change_id} отклонён: {exc}", "change.post_apply_invalid") from exc

    record = set_status(root, change_id, "reverted", reverted_at=_utc_now())
    return {"change_id": change_id, "applied": True, "status": record["status"], "files": files}


def _baseline_content(root: Path, rel_path: str) -> tuple[bytes | None, str]:
    """Содержимое файла до первого события изменения — точка, к которой откатываем.

    Именно ``before_content``, а не ``content_at``: последний возвращает состояние
    **после** события, то есть уже изменённый файл, и откат оказался бы пустым действием.
    """
    from todoc.adapters.history import journal
    from todoc.application.history import before_content

    events = journal.read_events(root)
    first = next((e for e in events
                  if any(isinstance(i, dict) and i.get("path") == rel_path for i in e.get("paths") or [])),
                 None)
    if first is None:
        return None, "revision_unknown"
    return before_content(root, first.get("rev"), rel_path)
