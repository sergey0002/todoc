"""Фаза 2: `todoc context` — один вызов, весь контекст, в пределах бюджета."""

import pytest

from todoc.application import changes as C
from todoc.application.context import build_context

DELTA = "---\ntarget: notes/a.md\n---\n\n## MODIFIED: ## Суть\n\nновое тело\n"


@pytest.fixture()
def task(root):
    notes = root / "notes"
    notes.mkdir()
    (notes / "a.md").write_text(
        '---\ntitle: "Д"\ndoc_type: note\n---\n\n# Д\n\n## Суть\n\nстарое\n', encoding="utf-8")
    record = C.open_change(root, "Обновить суть", artifacts=("notes/a.md",),
                           baseline={"artifacts": {}, "diagnostics": []})
    change_id = record["record_id"]
    deltas = C.deltas_dir(root, change_id)
    deltas.mkdir(parents=True, exist_ok=True)
    (deltas / "d.md").write_text(DELTA, encoding="utf-8")
    return root, change_id


def _set_baseline(root, change_id):
    """Пишет в запись реальные хеши артефактов — иначе диффу не с чем сравнивать."""
    import json

    from todoc.adapters.filesystem.scanner import file_hash

    path = C.record_path(root, change_id)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["baseline"] = {"artifacts": {a: file_hash(root / a) for a in data.get("artifacts") or []
                                      if (root / a).is_file()},
                        "diagnostics": []}
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def test_context_collects_record_deltas_and_files(task):
    root, change_id = task
    result = build_context(root, "ds", change_id=change_id, budget=8000)
    assert result["record"]["title"] == "Обновить суть"
    assert len(result["deltas"]) == 1
    assert result["deltas"][0]["target"] == "notes/a.md"
    assert [f["path"] for f in result["files"]] == ["notes/a.md"]
    assert result["truncated"] is False


def test_context_unknown_change(task):
    root, _change_id = task
    result = build_context(root, "ds", change_id="change:net", budget=1000)
    assert result["error"] == "change.not_found"


def test_context_budget_truncates_files(task):
    root, change_id = task
    result = build_context(root, change_id=change_id, dataset_id="ds", budget=200)
    assert result["truncated"] is True
    assert result["used_chars"] <= 200


def test_context_by_tag(task):
    root, change_id = task
    from todoc.adapters.history import journal
    from todoc.application.history import add_tag

    rev = journal.append_event(root, {"kind": "doc.edit", "paths": [{"path": "notes/a.md"}]})
    add_tag(root, "rel-1", rev, "релиз")
    result = build_context(root, "ds", tag="rel-1", budget=4000)
    assert result["events_total"] == 1
    assert result["events"][0]["rev"] == rev


def test_context_without_change_or_tag(task):
    root, _change_id = task
    result = build_context(root, "ds", budget=4000)
    assert result["record"] is None
    assert result["deltas"] == []


def test_context_with_diff(task):
    root, change_id = task
    C.apply_change(root, change_id, apply=True)
    result = build_context(root, "ds", change_id=change_id, budget=8000, with_diff=True)
    assert "diffs" in result


def test_context_diff_budget_truncates(task):
    """Дифф добавляется последним, поэтому урезается он, а не структура контекста."""
    root, change_id = task
    _set_baseline(root, change_id)
    C.apply_change(root, change_id, apply=True)
    full = build_context(root, "ds", change_id=change_id, budget=8000, with_diff=True)
    assert full["truncated"] is False and full["diffs"]
    tight = build_context(root, "ds", change_id=change_id, budget=400, with_diff=True)
    assert tight["truncated"] is True
    assert tight["used_chars"] <= 400


def test_context_diff_without_history_reports_status(task):
    root, change_id = task
    _set_baseline(root, change_id)
    C.apply_change(root, change_id, apply=True)
    from todoc.adapters.history import journal

    if journal.journal_path(root).is_file():
        journal.journal_path(root).unlink()
    result = build_context(root, "ds", change_id=change_id, budget=8000, with_diff=True)
    assert result["diffs"][0]["status"] == "revision_unknown"


def test_context_diff_skips_path_without_baseline(task):
    """Без базового хеша сравнивать не с чем — файл не выдаётся как «неизвестно»."""
    root, change_id = task
    C.apply_change(root, change_id, apply=True)
    result = build_context(root, "ds", change_id=change_id, budget=8000, with_diff=True)
    assert result["diffs"] == []


def test_context_skips_missing_artifact(root):
    record = C.open_change(root, "Нет файла", artifacts=("notes/net.md",))
    result = build_context(root, "ds", change_id=record["record_id"], budget=4000)
    assert result["files"] == []


def test_context_skips_unreadable_file(root):
    notes = root / "notes"
    notes.mkdir()
    target = notes / "locked.md"
    target.write_text("секрет", encoding="utf-8")
    target.chmod(0)
    try:
        record = C.open_change(root, "Закрытый", artifacts=("notes/locked.md",))
        result = build_context(root, "ds", change_id=record["record_id"], budget=4000)
        assert result["files"] == []
    finally:
        target.chmod(0o644)


def test_context_baseline_not_a_dict(task):
    root, change_id = task
    import json

    path = C.record_path(root, change_id)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["baseline"] = "не словарь"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    result = build_context(root, "ds", change_id=change_id, budget=8000, with_diff=True)
    assert result["diffs"] == []


def test_context_tiny_budget_truncates_record(task):
    root, change_id = task
    result = build_context(root, "ds", change_id=change_id, budget=10)
    assert result["record"] is None and result["truncated"] is True


def test_context_diff_budget_breaks_on_large_diff(task):
    """Дифф, не влезший в остаток бюджета, взводит флаг и не превышает его."""
    from todoc.application.history import record_write

    root, change_id = task
    path = root / "notes" / "a.md"
    head = '---\ntitle: "Д"\ndoc_type: note\n---\n\n# Д\n\n## Суть\n\n'
    original = head + "".join(f"строка {i}\n" for i in range(200))
    path.write_text(original, encoding="utf-8")
    _set_baseline(root, change_id)
    modified = head + "".join(f"изменённая {i}\n" for i in range(200))
    # Событие с настоящим образом «до»: без него диффу не с чем сравнивать.
    record_write(root, "notes/a.md", original.encode("utf-8"), modified.encode("utf-8"),
                 kind="doc.edit")
    path.write_text(modified, encoding="utf-8")

    # Бюджет берём от измеренного расхода без диффов: остаток заведомо меньше диффа,
    # поэтому срабатывает именно ветка прерывания, а не ранний выход по бюджету.
    without = build_context(root, "ds", change_id=change_id, budget=100000, with_diff=False)
    budget = without["used_chars"] + 5
    result = build_context(root, "ds", change_id=change_id, budget=budget, with_diff=True)
    assert result["truncated"] is True
    assert result["used_chars"] <= budget
    assert result["diffs"] == []


def test_context_diff_reports_missing_before_image(task):
    """Файл создан, а не изменён: образа «до» нет, и это сказано явно, а не пустым диффом."""
    from todoc.application.history import record_write

    root, change_id = task
    path = root / "notes" / "a.md"
    original = path.read_text(encoding="utf-8")
    record_write(root, "notes/a.md", None, original.encode("utf-8"), kind="doc.create")
    _set_baseline(root, change_id)
    path.write_text(original + "\nдобавлено\n", encoding="utf-8")
    result = build_context(root, "ds", change_id=change_id, budget=8000, with_diff=True)
    assert result["diffs"] == [{"path": "notes/a.md", "status": "no_before"}]


def test_context_caps_diff_by_max_diff_lines(task):
    """``max_diff_lines`` режет один огромный дифф, и это видно во флаге truncated."""
    from todoc.application.history import record_write

    root, change_id = task
    path = root / "notes" / "a.md"
    head = '---\ntitle: "Д"\ndoc_type: note\n---\n\n# Д\n\n## Суть\n\n'
    original = head + "".join(f"строка {i}\n" for i in range(50))
    path.write_text(original, encoding="utf-8")
    _set_baseline(root, change_id)
    modified = head + "".join(f"изменённая {i}\n" for i in range(50))
    record_write(root, "notes/a.md", original.encode("utf-8"), modified.encode("utf-8"),
                 kind="doc.edit")
    path.write_text(modified, encoding="utf-8")

    full = build_context(root, "ds", change_id=change_id, budget=100000, with_diff=True)
    assert full["truncated"] is False and full["diffs"][0]["lines"] > 5

    capped = build_context(root, "ds", change_id=change_id, budget=100000, with_diff=True,
                           max_diff_lines=4)
    assert capped["truncated"] is True
    assert capped["diffs"][0]["lines"] == 4
