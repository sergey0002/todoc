"""Фаза 2: записи изменений, дельты, проверка применимости, bundle-применение (K38, K39)."""

import json
import pathlib
import re

import pytest

from todoc.application import changes as C
from todoc.errors import ConflictError, ValidationError

DELTA = """---
target: notes/a.md
---

## MODIFIED: ## Суть

новое тело раздела

## REMOVED: ## Устаревшее
"""


@pytest.fixture()
def change_root(root):
    """Датасет с документом и открытым изменением на него."""
    notes = root / "notes"
    notes.mkdir()
    (notes / "a.md").write_text(
        '---\ntitle: "Д"\ndoc_type: note\n---\n\n# Д\n\n## Суть\n\nстарое\n\n'
        "## Устаревшее\n\nмусор\n", encoding="utf-8")
    record = C.open_change(root, "Обновить суть", artifacts=("notes/a.md",),
                           baseline={"artifacts": {}, "diagnostics": []})
    (C.deltas_dir(root, record["record_id"])).mkdir(parents=True, exist_ok=True)
    return root, record["record_id"]


class _Recorder:
    """Мини-рекодер: пишет событие в журнал, как это делает HistoryRecorder."""

    def __init__(self, root):
        self.root = root
        self.calls = []

    def record(self, rel_path, before, after, kind, basis=""):
        from todoc.application.history import record_write

        self.calls.append((rel_path, kind, basis))
        record_write(self.root, rel_path, before, after, kind=kind, basis=basis)


def _write_delta(root, change_id, name, body):
    path = C.deltas_dir(root, change_id) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


# --- идентификаторы ----------------------------------------------------------


@pytest.mark.parametrize("title,expected", [
    ("Обновить суть", "obnovit-sut"),
    ("Журнал и откат", "zhurnal-i-otkat"),
    ("Update the thing", "update-the-thing"),
    ("Фаза 2", "faza-2"),
])
def test_slugify_transliterates_cyrillic(title, expected):
    assert C.slugify(title) == expected


def test_slugify_is_deterministic_and_unique_for_punctuation():
    """Заголовок из знаков не должен давать одно имя для разных изменений."""
    first = C.slugify("!!!")
    second = C.slugify("???")
    assert first.startswith("change-") and first != second
    assert C.slugify("!!!") == first


# --- жизненный цикл ----------------------------------------------------------


def test_open_change_creates_record_and_folders(root):
    record = C.open_change(root, "Первое", artifacts=("notes/a.md",), blocked_by=("change:x",))
    assert record["record_id"] == "change:pervoe"
    assert record["status"] == "proposed"
    assert record["relations"] == [{"type_id": "blocked_by",
                                    "target": {"kind": "record", "id": "change:x"}}]
    assert C.deltas_dir(root, record["record_id"]).is_dir()


def test_open_change_refuses_duplicate(root):
    C.open_change(root, "Одно")
    with pytest.raises(ConflictError) as info:
        C.open_change(root, "Одно")
    assert info.value.code == "change.id_invalid"


def test_load_change_missing_and_broken(root):
    assert C.load_change(root, "change:net") is None
    path = C.record_path(root, "change:bitiy")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{ не json", encoding="utf-8")
    assert C.load_change(root, "change:bitiy") is None


def test_load_change_ignores_non_dict(root):
    path = C.record_path(root, "change:spisok")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("[1, 2]", encoding="utf-8")
    assert C.load_change(root, "change:spisok") is None


def test_list_changes_filters_by_status(change_root):
    root, change_id = change_root
    assert len(C.list_changes(root)) == 1
    assert len(C.list_changes(root, status="proposed")) == 1
    assert C.list_changes(root, status="applied") == []


def test_list_changes_empty_dataset(root):
    assert C.list_changes(root) == []


def test_list_changes_skips_folder_without_record(root):
    (C.changes_dir(root) / "pusto").mkdir(parents=True)
    assert C.list_changes(root) == []


def test_set_status_validates_value(change_root):
    root, change_id = change_root
    with pytest.raises(ValidationError) as info:
        C.set_status(root, change_id, "недопустимый")
    assert info.value.code == "change.id_invalid"


def test_set_status_missing_change(root):
    with pytest.raises(ValidationError) as info:
        C.set_status(root, "change:net", "applied")
    assert info.value.code == "change.not_found"


# --- разбор и применение дельт ------------------------------------------------


def test_parse_delta_reads_operations():
    delta = C.parse_delta(DELTA)
    assert delta["target"] == "notes/a.md"
    assert [(o["op"], o["anchor"]) for o in delta["ops"]] == [
        ("MODIFIED", "## Суть"), ("REMOVED", "## Устаревшее")]


def test_parse_delta_ignores_unknown_operation():
    delta = C.parse_delta("---\ntarget: a.md\n---\n\n## UNKNOWN: ## Цель\n\nтело\n")
    assert delta["ops"] == []


def test_parse_delta_reads_order():
    delta = C.parse_delta("---\ntarget: a.md\norder: 3\n---\n\n## ADDED: ## Новое\n\nтело\n")
    assert delta["order"] == 3


def test_apply_ops_modified_and_removed():
    text = "# Д\n\n## Суть\n\nстарое\n\n## Устаревшее\n\nмусор\n\n## Итоги\n\nконец\n"
    result, errors = C.apply_ops(text, C.parse_delta(DELTA)["ops"])
    assert errors == []
    assert "новое тело раздела" in result
    assert "## Устаревшее" not in result and "мусор" not in result
    assert "## Итоги" in result


def test_apply_ops_added_appends_section():
    result, errors = C.apply_ops("# Д\n\n## Суть\n\nстарое\n",
                                 [{"op": "ADDED", "anchor": "## Журнал", "body": "тело журнала"}])
    assert errors == []
    assert result.endswith("## Журнал\n\nтело журнала\n")


def test_apply_ops_added_without_body():
    result, _errors = C.apply_ops("# Д\n", [{"op": "ADDED", "anchor": "## Пусто", "body": ""}])
    assert result.endswith("## Пусто\n")


def test_apply_ops_reports_missing_anchor():
    result, errors = C.apply_ops("# Д\n\n## Суть\n\nстарое\n",
                                 [{"op": "MODIFIED", "anchor": "## Нет", "body": "x"}])
    assert [e["code"] for e in errors] == ["change.delta_anchor_missing"]


def test_collect_deltas_sorts_by_order_then_name(change_root):
    root, change_id = change_root
    _write_delta(root, change_id, "b.md", "---\ntarget: notes/a.md\norder: 2\n---\n\n## ADDED: ## X\n\nт\n")
    _write_delta(root, change_id, "a.md", "---\ntarget: notes/a.md\norder: 1\n---\n\n## ADDED: ## Y\n\nт\n")
    assert [d["path"].split("/")[-1] for d in C.collect_deltas(root, change_id)] == ["a.md", "b.md"]


def test_collect_deltas_without_folder(root):
    assert C.collect_deltas(root, "change:net") == []


def test_collect_deltas_skips_unreadable(change_root):
    root, change_id = change_root
    path = _write_delta(root, change_id, "x.md", "---\ntarget: notes/a.md\n---\n\n## ADDED: ## Z\n\nт\n")
    path.chmod(0)
    try:
        assert C.collect_deltas(root, change_id) == []
    finally:
        path.chmod(0o644)


# --- проверка применимости (K38) ---------------------------------------------


def test_validate_detects_missing_anchor(change_root):
    root, change_id = change_root
    _write_delta(root, change_id, "d.md",
                 "---\ntarget: notes/a.md\n---\n\n## MODIFIED: ## НетТакого\n\nтело\n")
    codes = [d.code for d in C.validate_change(root, change_id)]
    assert "change.delta_anchor_missing" in codes


def test_validate_detects_base_hash_mismatch(change_root):
    root, change_id = change_root
    _write_delta(root, change_id, "d.md",
                 "---\ntarget: notes/a.md\nbase_hash: sha256:" + "0" * 64 +
                 "\n---\n\n## MODIFIED: ## Суть\n\nтело\n")
    codes = [d.code for d in C.validate_change(root, change_id)]
    assert "change.base_hash_mismatch" in codes


def test_validate_detects_missing_target(change_root):
    root, change_id = change_root
    _write_delta(root, change_id, "d.md", "---\ntarget: notes/net.md\n---\n\n## MODIFIED: ## Суть\n\nт\n")
    codes = [d.code for d in C.validate_change(root, change_id)]
    assert "change.delta_target_missing" in codes


def test_validate_detects_delta_without_target(change_root):
    root, change_id = change_root
    _write_delta(root, change_id, "d.md", "---\ndoc_type: delta\n---\n\n## MODIFIED: ## Суть\n\nт\n")
    codes = [d.code for d in C.validate_change(root, change_id)]
    assert "change.delta_target_missing" in codes


def test_validate_detects_ambiguous_order(change_root):
    root, change_id = change_root
    for name in ("d1.md", "d2.md"):
        _write_delta(root, change_id, name, "---\ntarget: notes/a.md\n---\n\n## MODIFIED: ## Суть\n\nт\n")
    codes = [d.code for d in C.validate_change(root, change_id)]
    assert "change.apply_order_ambiguous" in codes


def test_validate_accepts_explicit_order(change_root):
    root, change_id = change_root
    _write_delta(root, change_id, "d1.md",
                 "---\ntarget: notes/a.md\norder: 1\n---\n\n## MODIFIED: ## Суть\n\nпервое\n")
    _write_delta(root, change_id, "d2.md",
                 "---\ntarget: notes/a.md\norder: 2\n---\n\n## MODIFIED: ## Суть\n\nвторое\n")
    assert C.validate_change(root, change_id) == []


def test_validate_on_correct_delta_has_no_errors(change_root):
    root, change_id = change_root
    _write_delta(root, change_id, "d.md", DELTA)
    assert C.validate_change(root, change_id) == []


def test_validate_reports_unknown_change(root):
    diags = C.validate_change(root, "change:net")
    assert [d.code for d in diags] == ["change.not_found"]


def test_validate_reports_unreadable_target(change_root):
    root, change_id = change_root
    _write_delta(root, change_id, "d.md", DELTA)
    (root / "notes" / "a.md").chmod(0)
    try:
        codes = [d.code for d in C.validate_change(root, change_id)]
        assert "change.delta_target_missing" in codes
    finally:
        (root / "notes" / "a.md").chmod(0o644)


def test_validate_reports_already_applied(change_root):
    root, change_id = change_root
    _write_delta(root, change_id, "d.md", DELTA)
    C.set_status(root, change_id, "applied")
    assert [d.code for d in C.validate_change(root, change_id)] == ["change.already_applied"]


def test_validate_rejects_target_outside_root(change_root, tmp_path, monkeypatch):
    root, change_id = change_root
    secret = tmp_path / "secret.md"
    secret.write_text("SECRET", encoding="utf-8")
    _write_delta(root, change_id, "d.md",
                 "---\ntarget: ../secret.md\n---\n\n## MODIFIED: ## Суть\n\nт\n")
    real_read = pathlib.Path.read_text

    def guarded(self, *args, **kwargs):
        if self.resolve() == secret.resolve():
            raise AssertionError("outside target must not be read")
        return real_read(self, *args, **kwargs)

    monkeypatch.setattr(pathlib.Path, "read_text", guarded)
    diags = C.validate_change(root, change_id)
    assert [d.code for d in diags] == ["change.delta_target_outside_root"]


def test_validate_rejects_absolute_and_symlink_targets(change_root, tmp_path):
    root, change_id = change_root
    outside = tmp_path / "outside.md"
    outside.write_text("OUT", encoding="utf-8")
    _write_delta(root, change_id, "abs.md",
                 f"---\ntarget: {outside.as_posix()}\n---\n\n## MODIFIED: ## Суть\n\nт\n")
    _write_delta(root, change_id, "blank.md", "---\ntarget: '  '\n---\n\n## MODIFIED: ## Суть\n\nт\n")
    codes = [d.code for d in C.validate_change(root, change_id)]
    assert codes == ["change.delta_target_outside_root"] * 2

    link = root / "notes" / "link.md"
    try:
        link.symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks are not available")
    _write_delta(root, change_id, "link.md",
                 "---\ntarget: notes/link.md\n---\n\n## MODIFIED: ## Суть\n\nт\n")
    codes = [d.code for d in C.validate_change(root, change_id)]
    assert "change.delta_target_outside_root" in codes


def test_plan_apply_keeps_targets_inside_root(change_root):
    root, change_id = change_root
    _write_delta(root, change_id, "d.md", DELTA)
    plan = C.plan_apply(root, change_id)
    assert plan["applicable"] is True
    assert [item["path"] for item in plan["files"]] == ["notes/a.md"]


def test_validate_warns_on_unresolved_dependency(root):
    record = C.open_change(root, "Зависимое", blocked_by=("change:blokir",))
    C.record_path(root, record["record_id"]).parent.joinpath("deltas").mkdir(exist_ok=True)
    diags = C.validate_change(root, record["record_id"])
    assert [d.code for d in diags] == ["change.blocked_by_unresolved"]
    assert diags[0].severity == "warning"


def test_validate_accepts_archived_dependency(root):
    blocker = C.open_change(root, "Блокер")
    C.set_status(root, blocker["record_id"], "archived")
    record = C.open_change(root, "Зависимое", blocked_by=(blocker["record_id"],))
    assert C.validate_change(root, record["record_id"]) == []


def test_validate_ignores_other_relations(root):
    record = C.open_change(root, "Прочее")
    path = C.record_path(root, record["record_id"])
    data = json.loads(path.read_text(encoding="utf-8"))
    data["relations"] = [{"type_id": "supports", "target": {"id": "note:x"}}, "не словарь"]
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    assert C.validate_change(root, record["record_id"]) == []


def test_validate_checks_structure_after_apply(change_root):
    """Пробное применение ломает структуру — validate это ловит до записи."""
    root, change_id = change_root
    _write_delta(root, change_id, "d.md",
                 "---\ntarget: notes/a.md\n---\n\n## REMOVED: ## Суть\n")

    def lookup(_front_matter, _rel_path):
        return {"required_sections": ["## Суть"]}

    codes = [d.code for d in C.validate_change(root, change_id, descriptor_lookup=lookup)]
    assert "markdown.section.missing" in codes


def test_validate_structure_check_skips_without_descriptor(change_root):
    root, change_id = change_root
    _write_delta(root, change_id, "d.md", "---\ntarget: notes/a.md\n---\n\n## REMOVED: ## Суть\n")
    assert C.validate_change(root, change_id, descriptor_lookup=lambda *_a: None) == []


def test_structure_after_apply_checks_schema(change_root):
    root, change_id = change_root
    _write_delta(root, change_id, "d.md", "---\ntarget: notes/a.md\n---\n\n## ADDED: ## Новое\n\nт\n")

    def lookup(_front_matter, _rel_path):
        return {"schema_data": {"type": "object", "required": ["обязательное"]}}

    codes = [d.code for d in C.validate_change(root, change_id, descriptor_lookup=lookup)]
    assert "change.post_apply_invalid" in codes


# --- применение: атомарность (K39) -------------------------------------------


def test_apply_preview_writes_nothing(change_root):
    root, change_id = change_root
    _write_delta(root, change_id, "d.md", DELTA)
    before = (root / "notes" / "a.md").read_bytes()
    result = C.apply_change(root, change_id)
    assert result["applied"] is False and result["preview"] is True
    assert (root / "notes" / "a.md").read_bytes() == before
    assert "content" not in result["files"][0]


def test_apply_writes_files_and_sets_status(change_root):
    root, change_id = change_root
    _write_delta(root, change_id, "d.md", DELTA)

    class Recorder:
        def __init__(self):
            self.calls = []

        def record(self, rel_path, before, after, kind, basis=""):
            self.calls.append((rel_path, kind, basis))

    recorder = Recorder()
    result = C.apply_change(root, change_id, apply=True, history=recorder)
    assert result["applied"] is True and result["status"] == "applied"
    assert "новое тело раздела" in (root / "notes" / "a.md").read_text(encoding="utf-8")
    assert recorder.calls == [("notes/a.md", "change.apply", f"change apply {change_id}")]


def test_apply_is_atomic_on_write_failure(change_root, monkeypatch):
    """K39: сбой на втором файле возвращает первый к исходным байтам."""
    root, change_id = change_root
    (root / "notes" / "b.md").write_text(
        '---\ntitle: "Б"\ndoc_type: note\n---\n\n# Б\n\n## Суть\n\nстарое б\n', encoding="utf-8")
    _write_delta(root, change_id, "a.md",
                 "---\ntarget: notes/a.md\norder: 1\n---\n\n## MODIFIED: ## Суть\n\nновое а\n")
    _write_delta(root, change_id, "b.md",
                 "---\ntarget: notes/b.md\norder: 2\n---\n\n## MODIFIED: ## Суть\n\nновое б\n")
    before_a = (root / "notes" / "a.md").read_bytes()
    before_b = (root / "notes" / "b.md").read_bytes()

    from todoc.adapters.filesystem import scanner

    real = scanner.atomic_write
    calls = {"n": 0}

    def flaky(path, text):
        calls["n"] += 1
        if calls["n"] == 2:
            raise OSError("диск отвалился")
        return real(path, text)

    import todoc.application.changes as changes_module

    monkeypatch.setattr(changes_module, "atomic_write", flaky)
    with pytest.raises(ValidationError) as info:
        C.apply_change(root, change_id, apply=True)
    assert info.value.code == "change.post_apply_invalid"
    assert (root / "notes" / "a.md").read_bytes() == before_a
    assert (root / "notes" / "b.md").read_bytes() == before_b
    assert C.load_change(root, change_id)["status"] == "proposed"


def test_apply_reports_when_rollback_also_fails(change_root, monkeypatch):
    root, change_id = change_root
    _write_delta(root, change_id, "a.md",
                 "---\ntarget: notes/a.md\norder: 1\n---\n\n## MODIFIED: ## Суть\n\nновое а\n")
    _write_delta(root, change_id, "b.md",
                 "---\ntarget: notes/b.md\norder: 2\n---\n\n## MODIFIED: ## Суть\n\nновое б\n")
    (root / "notes" / "b.md").write_text("# Б\n\n## Суть\n\nб\n", encoding="utf-8")

    import todoc.application.changes as changes_module

    from todoc.adapters.filesystem import scanner

    real = scanner.atomic_write
    state = {"n": 0}

    def broken(path, text):
        state["n"] += 1
        if state["n"] == 1:
            return real(path, text)          # первый файл записывается
        raise OSError("запись невозможна")   # второй файл падает

    monkeypatch.setattr(changes_module, "atomic_write", broken)
    # Откат идёт через Path.write_bytes, а не atomic_write — роняем именно его,
    # иначе проверка прошла бы по ветке успешного восстановления.
    real_write_bytes = pathlib.Path.write_bytes

    def broken_restore(self, data):
        if self.name.endswith(".md"):
            raise OSError("восстановление невозможно")
        return real_write_bytes(self, data)

    monkeypatch.setattr(pathlib.Path, "write_bytes", broken_restore)
    with pytest.raises(ValidationError) as info:
        C.apply_change(root, change_id, apply=True)
    assert "откат" in info.value.message


def test_apply_rejects_when_plan_is_not_applicable(change_root):
    root, change_id = change_root
    _write_delta(root, change_id, "d.md", "---\ntarget: notes/net.md\n---\n\n## MODIFIED: ## Суть\n\nт\n")
    result = C.apply_change(root, change_id, apply=True)
    assert result["applied"] is False and result["files"] == []


def test_apply_enforces_expected_hash(change_root):
    root, change_id = change_root
    _write_delta(root, change_id, "d.md", DELTA)
    with pytest.raises(ConflictError) as info:
        C.apply_change(root, change_id, apply=True,
                       expected_hashes={"notes/a.md": "sha256:неверный"})
    assert info.value.code == "write.hash_mismatch"


def test_plan_apply_reports_diagnostics_for_unknown_change(root):
    with pytest.raises(ValidationError) as info:
        C.plan_apply(root, "change:net")
    assert info.value.code == "change.not_found"


# --- verify ------------------------------------------------------------------


def test_verify_unknown_change(root):
    assert C.verify_change(root, "change:net") == {"change_id": "change:net", "found": False}


def test_verify_flags_unchecked_tasks(change_root):
    root, change_id = change_root
    (C.change_dir(root, change_id) / "tasks.md").write_text(
        "- [x] сделано\n- [ ] не сделано\n", encoding="utf-8")
    result = C.verify_change(root, change_id)
    assert any(f["dimension"] == "completeness" and "Не закрыто задач: 1" in f["message"]
               for f in result["findings"])
    assert result["clean"] is False


def test_verify_flags_untouched_artifact(change_root):
    root, change_id = change_root
    record = C.load_change(root, change_id)
    from todoc.adapters.filesystem.scanner import file_hash

    record["baseline"] = {"artifacts": {"notes/a.md": file_hash(root / "notes" / "a.md")}}
    C.record_path(root, change_id).write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
    result = C.verify_change(root, change_id)
    assert any("не изменён" in f["message"] for f in result["findings"])


def test_verify_correctness_reports_missing_anchor(change_root):
    root, change_id = change_root
    _write_delta(root, change_id, "d.md",
                 "---\ntarget: notes/a.md\n---\n\n## MODIFIED: ## НетТакого\n\nт\n")
    C.set_status(root, change_id, "applied")  # correctness проверяется после применения
    result = C.verify_change(root, change_id)
    assert any(f["dimension"] == "correctness" for f in result["findings"])


def test_verify_correctness_reports_still_present_removed(change_root):
    root, change_id = change_root
    _write_delta(root, change_id, "d.md", "---\ntarget: notes/a.md\n---\n\n## REMOVED: ## Суть\n")
    C.set_status(root, change_id, "applied")
    result = C.verify_change(root, change_id)
    assert any("всё ещё присутствует" in f["message"] for f in result["findings"])


def test_verify_correctness_reports_missing_target(change_root):
    root, change_id = change_root
    _write_delta(root, change_id, "d.md", "---\ntarget: notes/net.md\n---\n\n## ADDED: ## Новое\n\nт\n")
    C.set_status(root, change_id, "applied")
    result = C.verify_change(root, change_id)
    assert any("Цель дельты отсутствует" in f["message"] for f in result["findings"])


def test_verify_skips_correctness_before_apply(change_root):
    """Неприменённое изменение расходится с дельтами по определению — это не ошибка."""
    root, change_id = change_root
    _write_delta(root, change_id, "d.md",
                 "---\ntarget: notes/a.md\n---\n\n## MODIFIED: ## НетТакого\n\nт\n")
    result = C.verify_change(root, change_id)
    assert [f["dimension"] for f in result["findings"]] != ["correctness"]
    assert not any(f["dimension"] == "correctness" for f in result["findings"])


def test_verify_clean_when_nothing_is_wrong(change_root):
    root, change_id = change_root
    result = C.verify_change(root, change_id)
    assert result["clean"] is True and result["findings"] == []


def test_verify_skips_unreadable_target(change_root):
    root, change_id = change_root
    _write_delta(root, change_id, "d.md", DELTA)
    (root / "notes" / "a.md").chmod(0)
    try:
        result = C.verify_change(root, change_id)
        assert result["found"] is True
    finally:
        (root / "notes" / "a.md").chmod(0o644)


def test_verify_baseline_without_diagnostics_is_ignored(change_root):
    root, change_id = change_root
    record = C.load_change(root, change_id)
    record["baseline"] = "не словарь"
    C.record_path(root, change_id).write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
    assert C.verify_change(root, change_id)["clean"] is True


# --- архивация и откат -------------------------------------------------------


def test_archive_sets_status_and_tag(change_root):
    root, change_id = change_root
    from todoc.adapters.history import journal

    journal.append_event(root, {"kind": "doc.edit", "paths": []})
    result = C.archive_change(root, change_id, "rel-1", root)
    assert result["status"] == "archived" and result["tag"] == "rel-1"


def test_archive_without_tag(change_root):
    root, change_id = change_root
    result = C.archive_change(root, change_id)
    assert result["status"] == "archived" and result["tag"] is None


def test_archive_with_tag_but_empty_journal(change_root):
    root, change_id = change_root
    result = C.archive_change(root, change_id, "rel-2", root)
    assert result["tag"] is None


def test_revert_requires_applied_status(change_root):
    root, change_id = change_root
    with pytest.raises(ValidationError) as info:
        C.revert_change(root, change_id)
    assert info.value.code == "change.id_invalid"


def test_revert_unknown_change(root):
    with pytest.raises(ValidationError) as info:
        C.revert_change(root, "change:net")
    assert info.value.code == "change.not_found"


def test_revert_preview_and_apply(change_root):
    root, change_id = change_root
    _write_delta(root, change_id, "d.md", DELTA)
    original = (root / "notes" / "a.md").read_bytes()
    C.apply_change(root, change_id, apply=True, history=_Recorder(root))
    assert (root / "notes" / "a.md").read_bytes() != original

    preview = C.revert_change(root, change_id)
    assert preview["applied"] is False and preview["preview"] is True
    assert (root / "notes" / "a.md").read_bytes() != original

    result = C.revert_change(root, change_id, apply=True)
    assert result["applied"] is True and result["status"] == "reverted"
    assert (root / "notes" / "a.md").read_bytes() == original


def test_revert_without_history_reports_missing(change_root):
    root, change_id = change_root
    _write_delta(root, change_id, "d.md", DELTA)
    C.apply_change(root, change_id, apply=True, history=_Recorder(root))
    # журнал очищен — восстанавливать не из чего
    from todoc.adapters.history import journal

    if journal.journal_path(root).is_file():
        journal.journal_path(root).unlink()
    with pytest.raises(ValidationError) as info:
        C.revert_change(root, change_id, apply=True)
    assert info.value.code == "history.revision_unknown"


def test_baseline_content_unknown_revision(change_root):
    root, _change_id = change_root
    data, status = C._baseline_content(root, "notes/a.md")
    assert data is None and status == "revision_unknown"


# --- оставшиеся ветки --------------------------------------------------------


def test_list_changes_skips_files_in_changes_dir(root):
    C.changes_dir(root).mkdir(parents=True, exist_ok=True)
    (C.changes_dir(root) / "не-папка.txt").write_text("мусор", encoding="utf-8")
    assert C.list_changes(root) == []


def test_parse_delta_ignores_headings_without_colon():
    """Заголовок без двоеточия и не второго уровня операцией не считается."""
    delta = C.parse_delta("---\ntarget: a.md\n---\n\n### ADDED: ## Цель\n\nтело\n\n## Просто\n\nтекст\n")
    assert delta["ops"] == []


def test_verify_survives_unreadable_tasks(change_root):
    root, change_id = change_root
    tasks = C.change_dir(root, change_id) / "tasks.md"
    tasks.write_text("- [ ] задача\n", encoding="utf-8")
    tasks.chmod(0)
    try:
        result = C.verify_change(root, change_id)
        assert result["found"] is True
    finally:
        tasks.chmod(0o644)


def test_verify_correctness_survives_unreadable_target(change_root):
    root, change_id = change_root
    _write_delta(root, change_id, "d.md", DELTA)
    C.set_status(root, change_id, "applied")
    (root / "notes" / "a.md").chmod(0)
    try:
        result = C.verify_change(root, change_id)
        assert result["found"] is True
    finally:
        (root / "notes" / "a.md").chmod(0o644)


def test_revert_reports_when_restore_fails(change_root, monkeypatch):
    """Сбой записи при откате: файлы возвращаются, ошибка объясняет произошедшее."""
    root, change_id = change_root
    _write_delta(root, change_id, "d.md", DELTA)
    C.apply_change(root, change_id, apply=True, history=_Recorder(root))

    import todoc.application.changes as changes_module

    from todoc.adapters.filesystem import scanner

    real = scanner.atomic_write

    def broken(path, text):
        raise OSError("запись невозможна")

    monkeypatch.setattr(changes_module, "atomic_write", broken)
    with pytest.raises(ValidationError) as info:
        C.revert_change(root, change_id, apply=True)
    assert "отклонён" in info.value.message or "откат" in info.value.message


def test_revert_reports_when_rollback_also_fails(change_root, monkeypatch):
    root, change_id = change_root
    _write_delta(root, change_id, "d.md", DELTA)
    C.apply_change(root, change_id, apply=True, history=_Recorder(root))

    import todoc.application.changes as changes_module

    def broken(path, text):
        raise OSError("запись невозможна")

    real_write_bytes = pathlib.Path.write_bytes

    def broken_restore(self, data):
        if self.name.endswith(".md"):
            raise OSError("восстановление невозможно")
        return real_write_bytes(self, data)

    monkeypatch.setattr(changes_module, "atomic_write", broken)
    monkeypatch.setattr(pathlib.Path, "write_bytes", broken_restore)
    with pytest.raises(ValidationError) as info:
        C.revert_change(root, change_id, apply=True)
    assert info.value.code == "change.post_apply_invalid"
    assert "восстановление" in info.value.message


def test_parse_delta_body_includes_nested_subsections():
    """Подраздел глубже операции принадлежит её телу: цикл доходит до конца без break."""
    text = ("---\ntarget: notes/a.md\n---\n\n"
            "## ADDED: ## Новое\n\nоснова\n\n### Детали\n\nуточнение\n")
    delta = C.parse_delta(text)
    assert len(delta["ops"]) == 1
    assert "### Детали" in delta["ops"][0]["body"]
    assert "уточнение" in delta["ops"][0]["body"]


def test_verify_notes_artifact_changed_since_open(root):
    """Изменённый артефакт — норма: предупреждение «не изменён» не выдаётся."""
    notes = root / "notes"
    notes.mkdir()
    (notes / "a.md").write_text("---\ntitle: \"Д\"\ndoc_type: note\n---\n\n# Д\n\n## Суть\n\nновое\n",
                                encoding="utf-8")
    from todoc.adapters.filesystem.scanner import file_hash

    record = C.open_change(root, "Изменён сразу", artifacts=("notes/a.md",),
                           baseline={"artifacts": {"notes/a.md": "sha256:" + "0" * 64},
                                     "diagnostics": []})
    (notes / "a.md").write_text("---\ntitle: \"Д\"\ndoc_type: note\n---\n\n# Д\n\n## Суть\n\nещё\n",
                                encoding="utf-8")
    result = C.verify_change(root, record["record_id"])
    assert result["found"] is True
    assert not [f for f in result["findings"] if "не изменён" in f["message"]]
    assert file_hash(notes / "a.md") != "sha256:" + "0" * 64


def test_verify_correctness_is_silent_when_document_matches_deltas(change_root):
    """После корректного применения якоря на месте: correctness ничего не находит."""
    root, change_id = change_root
    _write_delta(root, change_id, "d.md", DELTA)
    C.apply_change(root, change_id, apply=True, history=_Recorder(root))
    result = C.verify_change(root, change_id)
    assert result["status"] == "applied"
    assert [f for f in result["findings"] if f["dimension"] == "correctness"] == []


def test_plan_apply_stacks_two_deltas_on_one_target(change_root):
    """Две дельты на один файл накладываются по порядку, а не каждая на исходник."""
    root, change_id = change_root
    _write_delta(root, change_id, "01-first.md",
                 "---\ntarget: notes/a.md\norder: 1\n---\n\n## MODIFIED: ## Суть\n\nшаг один\n")
    _write_delta(root, change_id, "02-second.md",
                 "---\ntarget: notes/a.md\norder: 2\n---\n\n## MODIFIED: ## Суть\n\nшаг два\n")
    plan = C.plan_apply(root, change_id, "ds", None)
    assert plan["applicable"] is True
    planned = [f for f in plan["files"] if f["path"] == "notes/a.md"]
    assert len(planned) == 1, "две дельты на один файл дают один запланированный файл"
    assert "шаг два" in planned[0]["content"]
    assert "шаг один" not in planned[0]["content"]


def test_k46_verify_is_reproducible(change_root):
    """K46: два запуска на неизменном состоянии дают идентичный результат."""
    root, change_id = change_root
    _write_delta(root, change_id, "d.md", DELTA)
    first = C.verify_change(root, change_id)
    second = C.verify_change(root, change_id)
    assert first == second
    assert first["findings"] == second["findings"]


# --- раскладка §4: архив, шаблоны, повреждённые записи ------------------------


def test_open_change_creates_proposal_and_tasks(root):
    """§4: proposal.md и tasks.md создаются вместе с записью."""
    record = C.open_change(root, "С шаблонами")
    folder = C.change_dir(root, record["record_id"])
    assert (folder / "proposal.md").is_file()
    assert (folder / "tasks.md").is_file()
    # Шаблон не выдумывает незакрытую задачу: иначе каждое изменение «неполно».
    # Считаем именно пункты тем же регулярным выражением, что и verify, — строка
    # подсказки `- [ ] …` в тексте пунктом не является.
    body = (folder / "tasks.md").read_text(encoding="utf-8")
    assert re.findall(r"^\s*[-*]\s+\[ \]", body, flags=re.M) == []


def test_open_change_keeps_existing_proposal_and_tasks(root):
    """Свои proposal.md и tasks.md не перезаписываются."""
    folder = C.changes_dir(root) / "svoimi-rukami"
    (folder / "deltas").mkdir(parents=True)
    (folder / "proposal.md").write_text("своё предложение\n", encoding="utf-8")
    (folder / "tasks.md").write_text("- [x] своё\n", encoding="utf-8")
    (folder / "change.json").unlink(missing_ok=True)
    C.open_change(root, "Своими руками")
    assert (folder / "proposal.md").read_text(encoding="utf-8") == "своё предложение\n"
    assert (folder / "tasks.md").read_text(encoding="utf-8") == "- [x] своё\n"


def test_archive_moves_folder_and_stays_readable(change_root):
    """§4: архив — changes/archive/<дата>-<id>/, и изменение остаётся читаемым."""
    root, change_id = change_root
    result = C.archive_change(root, change_id)
    assert result["status"] == "archived"
    assert result["path"] and result["path"].startswith("changes/archive/")
    assert not (C.changes_dir(root) / change_id.split(":", 1)[-1]).exists()
    # После переноса запись находится по тому же id.
    assert C.load_change(root, change_id)["status"] == "archived"
    assert C.change_dir(root, change_id).name == result["path"].rsplit("/", 1)[-1]
    assert [r["record_id"] for r in C.list_changes(root)] == [change_id]
    assert [r["record_id"] for r in C.list_changes(root, status="archived")] == [change_id]


def test_archive_without_history_records_no_event(change_root):
    root, change_id = change_root
    result = C.archive_change(root, change_id, history=None)
    assert result["status"] == "archived"


def test_archive_reports_when_move_fails(change_root, monkeypatch):
    """Перенос не удался: статус выставлен, но это сказано, а не скрыто."""
    root, change_id = change_root

    def broken(self, target):
        raise OSError("другая файловая система")

    monkeypatch.setattr(pathlib.Path, "rename", broken)
    result = C.archive_change(root, change_id)
    assert result["status"] == "archived"
    assert "не удалось перенести" in result["archive_warning"]
    assert C.load_change(root, change_id) is not None


def test_repeated_archive_does_not_move_anything(change_root):
    """Повторный архив: активной папки уже нет, переносить нечего — и это не ошибка."""
    root, change_id = change_root
    first = C.archive_change(root, change_id)
    assert first["path"] and first["path"].startswith("changes/archive/")
    second = C.archive_change(root, change_id)
    assert second["status"] == "archived"
    assert second["path"] is None
    assert "archive_warning" not in second
    # Запись по-прежнему читается из архива.
    assert C.load_change(root, change_id)["status"] == "archived"


def test_list_changes_skips_broken_records(root):
    """Битая или не-словарная запись не роняет список и не попадает в него."""
    base = C.changes_dir(root)
    (base / "bitoe").mkdir(parents=True)
    (base / "bitoe" / "change.json").write_text("{ не json", encoding="utf-8")
    (base / "spisok").mkdir(parents=True)
    (base / "spisok" / "change.json").write_text("[1, 2]", encoding="utf-8")
    (base / "bez-fayla").mkdir(parents=True)
    assert C.list_changes(root) == []


def test_verify_without_tasks_file_reports_nothing_about_tasks(change_root):
    root, change_id = change_root
    (C.change_dir(root, change_id) / "tasks.md").unlink()
    result = C.verify_change(root, change_id)
    assert result["found"] is True
    assert not [f for f in result["findings"] if "tasks.md" in f["message"]]


def test_change_dir_falls_back_when_archive_holds_other_changes(change_root):
    """В архиве есть чужие папки: своя не найдена — возвращается активный путь."""
    root, change_id = change_root
    C.archive_change(root, change_id)
    # Архив существует, но искомого изменения в нём нет.
    assert C.archive_dir(root).is_dir()
    other = C.change_dir(root, "change:drugoe")
    assert other == C.changes_dir(root) / "drugoe"
    assert not other.exists()
    # Посторонний файл в архиве не ломает обход.
    (C.archive_dir(root) / "ne-papka.txt").write_text("мусор", encoding="utf-8")
    assert C.change_dir(root, "change:drugoe") == other
