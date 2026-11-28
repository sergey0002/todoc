"""CLI-контракт Фазы 2: change list/open/show/validate/verify/apply/archive/revert и context."""

import json

import pytest
from click.testing import CliRunner

from todoc.cli import cli
from todoc.errors import TodocError

DELTA = """---
target: notes/a.md
---

## MODIFIED: ## Суть

новое тело раздела

## REMOVED: ## Устаревшее
"""


def _run(runner, args):
    result = runner.invoke(cli, args)
    if isinstance(result.exception, TodocError):
        result.exit_code = result.exception.exit_code
    return result


def _json(result):
    return json.loads(result.output)


@pytest.fixture()
def kb(root):
    notes = root / "notes"
    notes.mkdir()
    (notes / "a.md").write_text(
        '---\ntitle: "Д"\ndoc_type: note\n---\n\n# Д\n\n## Суть\n\nстарое\n\n'
        "## Устаревшее\n\nмусор\n", encoding="utf-8")
    runner = CliRunner()
    _run(runner, ["--root", str(root), "index", "rebuild", "--apply"])
    opened = _run(runner, ["--root", str(root), "change", "open", "--apply", "--title", "Обновить суть",
                           "--artifact", "notes/a.md"])
    assert opened.exit_code == 0, opened.output
    data = _json(opened)["data"]["result"]
    deltas = root / "changes" / data["change_id"].split(":", 1)[-1] / "deltas"
    deltas.mkdir(parents=True, exist_ok=True)
    (deltas / "d.md").write_text(DELTA, encoding="utf-8")
    return {"root": root, "id": data["change_id"], "path": data["path"],
            "doc": notes / "a.md", "deltas": deltas}


# --- open / list / show ------------------------------------------------------


def test_open_reports_path_and_status(root):
    data = _json(_run(CliRunner(), ["--root", str(root), "change", "open", "--apply", "--title", "Первое"]))["data"]["result"]
    assert data["change_id"] == "change:pervoe"
    assert data["status"] == "proposed"
    assert data["path"] == "changes/pervoe/change.json"


def test_open_preview_does_not_write_and_detects_changed_artifact(root, sample_md):
    runner = CliRunner()
    args = ["--root", str(root), "change", "open", "--title", "Новое", "--artifact", "notes/design.md"]
    draft = _json(_run(runner, args))["data"]["result"]
    assert draft["preview"] and not (root / "changes").exists()
    assert not (root / ".todoc/cache").exists()
    sample_md.write_text("# Новая базовая линия\n", encoding="utf-8")
    denied = _run(runner, [*args, "--apply", "--if-plan-hash", draft["plan_hash"]])
    assert denied.exception.code == "write.hash_mismatch"
    assert not (root / "changes").exists()


def test_open_cyrillic_title_is_transliterated(root):
    data = _json(_run(CliRunner(), ["--root", str(root), "change", "open", "--apply",
                                    "--title", "Журнал и откат"]))["data"]["result"]
    assert data["change_id"] == "change:zhurnal-i-otkat"


def test_open_duplicate_refused(root):
    runner = CliRunner()
    _run(runner, ["--root", str(root), "change", "open", "--apply", "--title", "Одно"])
    result = _run(runner, ["--root", str(root), "change", "open", "--apply", "--title", "Одно"])
    assert isinstance(result.exception, TodocError)
    assert result.exception.code == "change.id_invalid"


def test_list_and_filter(kb):
    runner = CliRunner()
    assert _json(_run(runner, ["--root", str(kb["root"]), "change", "list"]))["data"]["meta"]["total"] == 1
    assert _json(_run(runner, ["--root", str(kb["root"]), "change", "list",
                               "--status", "proposed"]))["data"]["meta"]["total"] == 1
    assert _json(_run(runner, ["--root", str(kb["root"]), "change", "list",
                               "--status", "applied"]))["data"]["meta"]["total"] == 0


def test_list_does_not_leak_baseline(kb):
    items = _json(_run(CliRunner(), ["--root", str(kb["root"]), "change", "list"]))["data"]["result"]["items"]
    assert "baseline" not in items[0]


def test_show_returns_record_and_deltas(kb):
    data = _json(_run(CliRunner(), ["--root", str(kb["root"]), "change", "show", kb["id"]]))["data"]["result"]
    assert data["record"]["record_id"] == kb["id"]
    assert [(o["op"], o["anchor"]) for o in data["deltas"][0]["ops"]] == [
        ("MODIFIED", "## Суть"), ("REMOVED", "## Устаревшее")]


def test_show_unknown_change(kb):
    result = _run(CliRunner(), ["--root", str(kb["root"]), "change", "show", "change:net"])
    assert isinstance(result.exception, TodocError)
    assert result.exception.code == "change.not_found"


# --- validate / verify -------------------------------------------------------


def test_validate_reports_applicable(kb):
    data = _json(_run(CliRunner(), ["--root", str(kb["root"]), "change", "validate", kb["id"]]))["data"]["result"]
    assert data["applicable"] is True and data["errors"] == 0


def test_validate_emits_diagnostics_in_envelope(kb):
    (kb["deltas"] / "bad.md").write_text(
        "---\ntarget: notes/net.md\n---\n\n## MODIFIED: ## Суть\n\nт\n", encoding="utf-8")
    envelope = _json(_run(CliRunner(), ["--root", str(kb["root"]), "change", "validate", kb["id"]]))
    assert envelope["data"]["result"]["applicable"] is False
    assert [d["code"] for d in envelope["diagnostics"]] == ["change.delta_target_missing"]


def test_verify_flags_untouched_artifact(kb):
    """Свежее изменение ещё ничего не поменяло — это честный warning, а не «чисто»."""
    data = _json(_run(CliRunner(), ["--root", str(kb["root"]), "change", "verify", kb["id"]]))["data"]["result"]
    assert data["found"] is True and data["clean"] is False
    assert [f["dimension"] for f in data["findings"]] == ["completeness"]
    assert data["findings"][0]["severity"] == "warning"


def test_verify_unknown_change(kb):
    result = _run(CliRunner(), ["--root", str(kb["root"]), "change", "verify", "change:net"])
    assert isinstance(result.exception, TodocError)
    assert result.exception.code == "change.not_found"


def test_verify_reports_unchecked_tasks(kb):
    tasks = kb["deltas"].parent / "tasks.md"
    tasks.write_text("- [x] готово\n- [ ] не готово\n", encoding="utf-8")
    data = _json(_run(CliRunner(), ["--root", str(kb["root"]), "change", "verify", kb["id"]]))["data"]["result"]
    assert data["clean"] is False
    assert any(f["dimension"] == "completeness" for f in data["findings"])


# --- apply -------------------------------------------------------------------


def test_apply_preview_writes_nothing(kb):
    before = kb["doc"].read_bytes()
    data = _json(_run(CliRunner(), ["--root", str(kb["root"]), "change", "apply", kb["id"]]))["data"]["result"]
    assert data["applied"] is False and data["preview"] is True
    assert kb["doc"].read_bytes() == before


def test_apply_writes_and_records_history(kb):
    runner = CliRunner()
    data = _json(_run(runner, ["--root", str(kb["root"]), "change", "apply", kb["id"], "--apply"]))["data"]["result"]
    assert data["applied"] is True and data["status"] == "applied"
    assert "новое тело раздела" in kb["doc"].read_text(encoding="utf-8")
    assert "## Устаревшее" not in kb["doc"].read_text(encoding="utf-8")
    events = _json(_run(runner, ["--root", str(kb["root"]), "log"]))["data"]["result"]["items"]
    assert any(e["kind"] == "change.apply" and f"change apply {kb['id']}" in e["basis"]
               for e in events)


def test_apply_twice_is_refused(kb):
    runner = CliRunner()
    _run(runner, ["--root", str(kb["root"]), "change", "apply", kb["id"], "--apply"])
    second = _json(_run(runner, ["--root", str(kb["root"]), "change", "apply", kb["id"], "--apply"]))
    assert second["data"]["result"]["applied"] is False
    assert [d["code"] for d in second["diagnostics"]] == ["change.already_applied"]


def test_apply_if_hash_mismatch(kb):
    result = _run(CliRunner(), ["--root", str(kb["root"]), "change", "apply", kb["id"], "--apply",
                                "--if-hash", "notes/a.md=sha256:неверный"])
    assert isinstance(result.exception, TodocError)
    assert result.exception.code == "write.hash_mismatch"


def test_apply_if_hash_without_value(kb):
    result = _run(CliRunner(), ["--root", str(kb["root"]), "change", "apply", kb["id"], "--apply",
                                "--if-hash", "notes/a.md"])
    assert isinstance(result.exception, TodocError)
    assert result.exception.code == "usage.error"


def test_apply_rejected_delta_changes_nothing(kb):
    (kb["deltas"] / "bad.md").write_text(
        "---\ntarget: notes/net.md\n---\n\n## MODIFIED: ## Суть\n\nт\n", encoding="utf-8")
    before = kb["doc"].read_bytes()
    data = _json(_run(CliRunner(), ["--root", str(kb["root"]), "change", "apply", kb["id"],
                                    "--apply"]))["data"]["result"]
    assert data["applied"] is False
    assert kb["doc"].read_bytes() == before


def test_apply_refuses_delta_target_outside_root(kb):
    escape = kb["root"].parent / "escape.md"
    escape.write_text("OUTSIDE", encoding="utf-8")
    (kb["deltas"] / "evil.md").write_text(
        "---\ntarget: ../escape.md\n---\n\n## ADDED: X\n\nPWNED\n", encoding="utf-8")
    before = kb["doc"].read_bytes()
    result = _run(CliRunner(), ["--root", str(kb["root"]), "change", "apply", kb["id"], "--apply"])
    assert result.exit_code == 3
    assert [d["code"] for d in _json(result)["diagnostics"]] == ["change.delta_target_outside_root"]
    assert escape.read_text(encoding="utf-8") == "OUTSIDE"
    assert kb["doc"].read_bytes() == before


def test_validate_refuses_delta_target_outside_root(kb):
    (kb["deltas"] / "evil.md").write_text(
        "---\ntarget: ../../outside.md\n---\n\n## ADDED: X\n\nPWNED\n", encoding="utf-8")
    result = _run(CliRunner(), ["--root", str(kb["root"]), "change", "validate", kb["id"]])
    assert result.exit_code == 3
    assert [d["code"] for d in _json(result)["diagnostics"]] == ["change.delta_target_outside_root"]


# --- archive / revert --------------------------------------------------------


def test_archive_with_tag(kb):
    runner = CliRunner()
    _run(runner, ["--root", str(kb["root"]), "change", "apply", kb["id"], "--apply"])
    data = _json(_run(runner, ["--root", str(kb["root"]), "change", "archive", kb["id"], "--apply",
                               "--tag", "rel-1"]))["data"]["result"]
    assert data["status"] == "archived" and data["tag"] == "rel-1"
    tags = _json(_run(runner, ["--root", str(kb["root"]), "log", "--tag", "rel-1"]))["data"]
    assert tags["meta"]["total"] == 1


def test_revert_restores_original(kb):
    runner = CliRunner()
    original = kb["doc"].read_bytes()
    _run(runner, ["--root", str(kb["root"]), "change", "apply", kb["id"], "--apply"])
    preview = _json(_run(runner, ["--root", str(kb["root"]), "change", "revert", kb["id"]]))["data"]["result"]
    assert preview["applied"] is False and preview["preview"] is True
    assert kb["doc"].read_bytes() != original

    data = _json(_run(runner, ["--root", str(kb["root"]), "change", "revert", kb["id"], "--apply"]))["data"]["result"]
    assert data["applied"] is True and data["status"] == "reverted"
    assert kb["doc"].read_bytes() == original


def test_revert_requires_applied(kb):
    result = _run(CliRunner(), ["--root", str(kb["root"]), "change", "revert", kb["id"]])
    assert isinstance(result.exception, TodocError)
    assert result.exception.code == "change.id_invalid"


@pytest.mark.parametrize("command", ["show", "validate", "verify", "apply", "archive", "revert"])
@pytest.mark.parametrize("bad_id", ["change:../../x", "change:a/b", "change:", "/etc/passwd"])
def test_change_commands_reject_malformed_ids(kb, command, bad_id):
    result = _run(CliRunner(), ["--root", str(kb["root"]), "change", command, bad_id])
    assert result.exit_code == 2, (command, bad_id, result.output)
    assert result.exception.code == "usage.invalid_id"


def test_log_rejects_malformed_change_filter(kb):
    result = _run(CliRunner(), ["--root", str(kb["root"]), "log", "--change", "change:../x"])
    assert result.exit_code == 2
    assert [d["code"] for d in _json(result)["diagnostics"]] == ["usage.invalid_id"]


def test_malformed_id_does_not_touch_outside_paths(kb, tmp_path):
    sentinel = tmp_path / "sentinel.md"
    sentinel.write_text("SECRET", encoding="utf-8")
    result = _run(CliRunner(), ["--root", str(kb["root"]), "change", "archive",
                                "change:../sentinel.md", "--apply"])
    assert result.exit_code == 2
    assert sentinel.read_text(encoding="utf-8") == "SECRET"


# --- context -----------------------------------------------------------------


def test_context_requires_selector(kb):
    result = _run(CliRunner(), ["--root", str(kb["root"]), "context"])
    assert isinstance(result.exception, TodocError)
    assert result.exception.code == "usage.error"


def test_context_returns_everything_in_one_call(kb):
    data = _json(_run(CliRunner(), ["--root", str(kb["root"]), "context", "--change", kb["id"],
                                    "--budget", "8000"]))["data"]["result"]
    assert data["record"]["title"] == "Обновить суть"
    assert len(data["deltas"]) == 1
    assert [f["path"] for f in data["files"]] == ["notes/a.md"]
    assert data["truncated"] is False


def test_context_respects_budget(kb):
    data = _json(_run(CliRunner(), ["--root", str(kb["root"]), "context", "--change", kb["id"],
                                    "--budget", "200"]))["data"]["result"]
    assert data["truncated"] is True and data["used_chars"] <= 200


def test_context_by_tag(kb):
    runner = CliRunner()
    _run(runner, ["--root", str(kb["root"]), "change", "apply", kb["id"], "--apply"])
    _run(runner, ["--root", str(kb["root"]), "change", "archive", kb["id"], "--apply", "--tag", "rel-1"])
    data = _json(_run(runner, ["--root", str(kb["root"]), "context", "--tag", "rel-1"]))["data"]["result"]
    assert data["events_total"] >= 1


def test_context_with_diff(kb):
    runner = CliRunner()
    _run(runner, ["--root", str(kb["root"]), "change", "apply", kb["id"], "--apply"])
    data = _json(_run(runner, ["--root", str(kb["root"]), "context", "--change", kb["id"],
                               "--with-diff"]))["data"]["result"]
    assert "diffs" in data


# --- K47, K48: контракт агента -----------------------------------------------


def test_change_commands_never_prompt(kb):
    """K47: ни одна новая команда не требует TTY при --no-input."""
    runner = CliRunner()
    for args in (["change", "list"], ["change", "show", kb["id"]],
                 ["change", "validate", kb["id"]], ["change", "verify", kb["id"]],
                 ["change", "apply", kb["id"]], ["context", "--change", kb["id"]]):
        result = _run(runner, ["--root", str(kb["root"]), "--no-input", *args])
        assert result.exit_code == 0, (args, result.output)


def test_change_errors_are_envelopes(kb):
    """K48: ошибка — один конверт ok:false, а не трейсбек."""
    runner = CliRunner()
    for args in (["change", "show", "change:net"], ["change", "verify", "change:net"], ["context"]):
        out = _run(runner, ["--root", str(kb["root"]), *args])
        assert isinstance(out.exception, TodocError), (args, out.output)
        assert out.exception.exit_code in (2, 6)


# --- проверка структуры и схемы после применения ------------------------------

def _rewrite(kb, front_matter):
    """Меняет только front matter цели: разделы дельты должны остаться на месте."""
    kb["doc"].write_text(front_matter + "\n\n# Д\n\n## Суть\n\nстарое\n\n"
                         "## Устаревшее\n\nмусор\n", encoding="utf-8")



def _note_type_dir(kb):
    return kb["root"] / ".todoc" / "doc_types" / "note"


def test_validate_checks_target_structure_after_apply(kb):
    """Дельта, после которой документ теряет обязательный раздел, не применяется."""
    (kb["deltas"] / "d.md").write_text(
        "---\ntarget: notes/a.md\n---\n\n## REMOVED: ## Суть\n", encoding="utf-8")
    envelope = _json(_run(CliRunner(), ["--root", str(kb["root"]), "change", "validate", kb["id"]]))
    codes = [d["code"] for d in envelope["diagnostics"]]
    assert "markdown.section.missing" in codes
    assert envelope["data"]["result"]["applicable"] is False


def test_validate_checks_doc_type_schema_after_apply(kb):
    """Схема doc_type проверяет front matter получившегося документа."""
    (_note_type_dir(kb) / "schema.json").write_text(
        json.dumps({"type": "object", "required": ["owner"]}), encoding="utf-8")
    envelope = _json(_run(CliRunner(), ["--root", str(kb["root"]), "change", "validate", kb["id"]]))
    # Нарушение схемы после применения — это именно «после применения документ
    # не соответствует своему типу», поэтому код один: change.post_apply_invalid.
    found = [d for d in envelope["diagnostics"] if d["code"] == "change.post_apply_invalid"]
    assert found and "owner" in found[0]["message"]
    assert found[0]["evidence"] == "схема doc_type после применения"
    assert envelope["data"]["result"]["applicable"] is False


def test_validate_survives_broken_doc_type_schema(kb):
    """Нечитаемая схема не ломает проверку: она просто не применяется."""
    (_note_type_dir(kb) / "schema.json").write_text("{ это не json", encoding="utf-8")
    data = _json(_run(CliRunner(), ["--root", str(kb["root"]), "change", "validate",
                                    kb["id"]]))["data"]["result"]
    assert data["applicable"] is True


def test_validate_skips_structure_check_without_doc_type(kb):
    """Без типа документа проверять нечего — и это не ошибка."""
    _rewrite(kb, '---\ntitle: "Д"\n---')
    data = _json(_run(CliRunner(), ["--root", str(kb["root"]), "change", "validate",
                                    kb["id"]]))["data"]["result"]
    assert data["applicable"] is True


def test_validate_skips_unknown_doc_type(kb):
    """Незнакомый doc_type не имеет описателя: проверка структуры пропускается."""
    _rewrite(kb, '---\ntitle: "Д"\ndoc_type: несуществующий\n---')
    data = _json(_run(CliRunner(), ["--root", str(kb["root"]), "change", "validate",
                                    kb["id"]]))["data"]["result"]
    assert data["applicable"] is True


def test_descriptor_lookup_handles_unindexed_path(kb):
    """Файла нет в индексе: тип берётся только из front matter, иначе — ничего."""
    from todoc.cli import _descriptor_lookup
    from todoc.service import DatasetContext

    lookup = _descriptor_lookup(DatasetContext(kb["root"]))
    assert lookup({}, "notes/отсутствует.md") is None
    # Тип объявлен самим документом, поэтому индекс для него не указ.
    descriptor = lookup({"doc_type": "note"}, "notes/отсутствует.md")
    assert descriptor is not None and descriptor.get("type_id") == "note"


# --- K42, K43: контекст одним вызовом, в пределах бюджета ---------------------


@pytest.fixture()
def five_docs(root):
    """Засеянная задача из пяти документов (K42)."""
    notes = root / "notes"
    notes.mkdir()
    for i in range(1, 6):
        (notes / f"d{i}.md").write_text(
            f'---\ntitle: "Д{i}"\ndoc_type: note\n---\n\n# Д{i}\n\n## Суть\n\n'
            f"тело {i}\n\n## Старое\n\nмусор {i}\n", encoding="utf-8")
    runner = CliRunner()
    _run(runner, ["--root", str(root), "index", "rebuild", "--apply"])
    opened = _run(runner, ["--root", str(root), "change", "open", "--apply", "--title", "Пять документов",
                           *sum((["--artifact", f"notes/d{i}.md"] for i in range(1, 6)), [])])
    assert opened.exit_code == 0, opened.output
    data = _json(opened)["data"]["result"]
    deltas = root / "changes" / data["change_id"].split(":", 1)[-1] / "deltas"
    for i in range(1, 6):
        (deltas / f"d{i}.md").write_text(
            f"---\ntarget: notes/d{i}.md\norder: {i}\n---\n\n"
            f"## MODIFIED: ## Суть\n\nновое {i}\n\n## REMOVED: ## Старое\n", encoding="utf-8")
    return {"root": root, "id": data["change_id"]}


def test_k42_context_returns_all_artifacts_in_one_call(five_docs):
    """K42: полнота 1.0 — все пять артефактов и все пять дельт за один вызов."""
    envelope = _json(_run(CliRunner(), ["--root", str(five_docs["root"]), "context",
                                        "--change", five_docs["id"], "--budget", "20000"]))
    data = envelope["data"]["result"]
    artifacts = {f["path"] for f in data["files"]}
    expected = {f"notes/d{i}.md" for i in range(1, 6)}
    assert expected <= artifacts, f"потеряны артефакты: {expected - artifacts}"
    assert len(data["deltas"]) == 5
    assert data["truncated"] is False


def test_k43_context_without_diff_has_no_bodies_and_fits_budget(five_docs):
    """K43: без --with-diff тел диффов нет, а объём ответа не превышает бюджет."""
    for budget in (4000, 1200):
        envelope = _json(_run(CliRunner(), ["--root", str(five_docs["root"]), "context",
                                            "--change", five_docs["id"],
                                            "--budget", str(budget)]))
        data = envelope["data"]["result"]
        assert "diffs" not in data, "без --with-diff диффов быть не должно"
        assert data["used_chars"] <= budget
        assert len(json.dumps(data, ensure_ascii=False)) <= budget * 4



def test_change_list_filters_then_pages_and_binds_cursor_to_full_snapshot(kb):
    runner = CliRunner()
    root = kb["root"]
    for title in ("Два", "Три"):
        opened = _run(runner, ["change", "open", "--root", str(root), "--title", title, "--apply"])
        assert opened.exit_code == 0, opened.output
    args = ["change", "list", "--root", str(root), "--status", "archived|proposed",
            "--fields", "title", "--limit", "2", "--view", "tree"]
    first = _json(_run(runner, args))
    assert first["diagnostics"][0]["code"] == "view.fallback"
    assert first["data"]["meta"]["total"] == 3
    assert first["data"]["meta"]["actual_view"] == "flat"
    rows = first["data"]["result"]["items"]
    assert all(set(row) == {"record_id", "path", "title"} for row in rows)
    cursor = first["data"]["meta"]["next_cursor"]
    second = _json(_run(runner, [*args, "--cursor", cursor]))
    assert second["data"]["meta"]["next_cursor"] is None
    assert len({row["record_id"] for row in rows + second["data"]["result"]["items"]}) == 3
    opened = _run(runner, ["change", "open", "--root", str(root), "--title", "Четыре", "--apply"])
    assert opened.exit_code == 0, opened.output
    assert _run(runner, [*args, "--cursor", cursor]).exception.code == "cursor.invalid"


@pytest.mark.parametrize("content", ["{", "[]", '{"title":"No identity"}'])
def test_change_list_refuses_incomplete_source(root, content):
    path = root / "changes/test/change.json"
    path.parent.mkdir(parents=True)
    path.write_text(content, encoding="utf-8")
    result = _run(CliRunner(), ["change", "list", "--root", str(root), "--status", "archived"])
    assert result.exception.code == "change.unreadable"
