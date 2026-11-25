"""CLI-контракт Фазы 1: log, show, diff, blame, revert, tag, history gc/adopt/export."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

from todoc.cli import cli
from todoc.errors import TodocError


def _run(runner, args):
    result = runner.invoke(cli, args)
    if isinstance(result.exception, TodocError):
        result.exit_code = result.exception.exit_code
    return result


def _json(result):
    return json.loads(result.output)


def _run_cli(root, args):
    env = dict(os.environ)
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[2] / "src")
    return subprocess.run([sys.executable, "-m", "todoc", "--root", str(root), *args],
                          capture_output=True, text=True, env=env, timeout=120)


@pytest.fixture()
def kb(root):
    """Датасет с одним документом и одной уже сделанной правкой в журнале."""
    notes = root / "notes"
    notes.mkdir()
    doc = notes / "a.md"
    doc.write_text('---\ntitle: "Заметка"\ndoc_type: note\n---\n\n# Заметка\n\n## Решение\n\n'
                   "первая версия\n\n## Итоги\n\nитоги\n", encoding="utf-8")
    runner = CliRunner()
    _run(runner, ["--root", str(root), "index", "rebuild"])
    patch = root / "patch.json"
    patch.write_text(json.dumps({"ops": [{"line": 11, "text": "вторая версия"}]}), encoding="utf-8")
    result = _run(runner, ["--root", str(root), "docs", "edit", "--id", "doc:notes/a.md",
                           "--patch-file", str(patch), "--apply"])
    assert result.exit_code == 0, result.output
    return {"doc": doc, "patch": patch}


def _first_rev(root):
    proc = _run_cli(root, ["log", "--limit", "50"])
    return json.loads(proc.stdout)["data"]["events"][-1]["rev"]


# --- log ---------------------------------------------------------------------


def test_log_lists_events(root, kb):
    data = _json(_run(CliRunner(), ["--root", str(root), "log"]))["data"]
    assert data["total"] == 1
    assert data["events"][0]["kind"] == "doc.edit"
    assert data["events"][0]["paths"][0]["ranges"] == [[11, 11]]


def test_log_section_requires_path(root, kb):
    runner = CliRunner()
    result = runner.invoke(cli, ["--root", str(root), "log", "--section", "## Решение"])
    assert isinstance(result.exception, TodocError)
    assert result.exception.exit_code == 2


def test_log_by_section(root, kb):
    data = _json(_run(CliRunner(), ["--root", str(root), "log", "--path", "notes/a.md",
                                    "--section", "## Решение"]))["data"]
    assert data["total"] == 1
    other = _json(_run(CliRunner(), ["--root", str(root), "log", "--path", "notes/a.md",
                                     "--section", "## Итоги"]))["data"]
    assert other["total"] == 0


def test_log_pagination_reports_truncated(root, kb):
    runner = CliRunner()
    for i in range(3):
        kb["patch"].write_text(json.dumps({"ops": [{"line": 11, "text": f"версия {i}"}]}), encoding="utf-8")
        _run(runner, ["--root", str(root), "docs", "edit", "--id", "doc:notes/a.md",
                      "--patch-file", str(kb["patch"]), "--apply"])
    data = _json(_run(runner, ["--root", str(root), "log", "--limit", "2"]))["data"]
    assert data["total"] == 4 and len(data["events"]) == 2 and data["truncated"] is True


def test_log_filter_by_kind_and_tag(root, kb):
    runner = CliRunner()
    assert _json(_run(runner, ["--root", str(root), "log", "--kind", "doc.fix"]))["data"]["total"] == 0
    rev = _first_rev(root)
    _run(runner, ["--root", str(root), "tag", "v1", "--rev", rev, "--message", "релиз"])
    assert _json(_run(runner, ["--root", str(root), "log", "--tag", "v1"]))["data"]["total"] == 1


# --- show / diff / blame -----------------------------------------------------


def test_show_returns_content(root, kb):
    rev = _first_rev(root)
    data = _json(_run(CliRunner(), ["--root", str(root), "show", rev, "--path", "notes/a.md"]))["data"]
    assert "первая версия" in data["content"]


def test_show_budget_limits_output(root, kb):
    data = _json(_run(CliRunner(), ["--root", str(root), "show", "--path", "notes/a.md",
                                    "--budget", "20"]))["data"]
    assert len(data["content"]) == 20


def test_show_unknown_revision_envelope(root, kb):
    proc = _run_cli(root, ["show", "неттакойрев", "--path", "notes/a.md"])
    assert proc.returncode == 6, proc.stderr
    assert json.loads(proc.stdout)["ok"] is False


def test_diff_detects_change(root, kb):
    rev = _first_rev(root)
    data = _json(_run(CliRunner(), ["--root", str(root), "diff", rev, "--path", "notes/a.md"]))["data"]
    assert data["changed"] is True and data["lines"] > 0


def test_diff_identical_is_empty(root, kb):
    rev = _first_rev(root)
    data = _json(_run(CliRunner(), ["--root", str(root), "diff", rev, rev, "--path", "notes/a.md"]))["data"]
    assert data["changed"] is False


def test_blame_lists_events(root, kb):
    data = _json(_run(CliRunner(), ["--root", str(root), "blame", "--path", "notes/a.md"]))["data"]
    assert len(data["entries"]) == 1
    assert data["entries"][0]["kind"] == "doc.edit"


def test_blame_by_section(root, kb):
    inside = _json(_run(CliRunner(), ["--root", str(root), "blame", "--path", "notes/a.md",
                                      "--section", "## Решение"]))["data"]
    assert len(inside["entries"]) == 1
    outside = _json(_run(CliRunner(), ["--root", str(root), "blame", "--path", "notes/a.md",
                                       "--section", "## Итоги"]))["data"]
    assert outside["entries"] == []


# --- revert ------------------------------------------------------------------


def test_revert_preview_then_apply(root, kb):
    runner = CliRunner()
    rev = _first_rev(root)
    before = kb["doc"].read_bytes()

    preview = _json(_run(runner, ["--root", str(root), "revert", rev, "--path", "notes/a.md"]))["data"]
    assert preview["applied"] is False
    assert kb["doc"].read_bytes() == before

    applied = _json(_run(runner, ["--root", str(root), "revert", rev, "--path", "notes/a.md",
                                  "--apply"]))["data"]
    assert applied["applied"] is True
    assert "первая версия" in kb["doc"].read_text(encoding="utf-8")


def test_revert_expected_hash_mismatch(root, kb):
    runner = CliRunner()
    rev = _first_rev(root)
    result = runner.invoke(cli, ["--root", str(root), "revert", rev, "--path", "notes/a.md",
                                 "--apply", "--expected-hash", "sha256:неверный"])
    assert isinstance(result.exception, TodocError)
    assert result.exception.code == "write.hash_mismatch"


def test_revert_writes_its_own_event(root, kb):
    runner = CliRunner()
    rev = _first_rev(root)
    _run(runner, ["--root", str(root), "revert", rev, "--path", "notes/a.md", "--apply"])
    assert _json(_run(runner, ["--root", str(root), "log"]))["data"]["total"] == 2


def test_revert_unknown_revision(root, kb):
    proc = _run_cli(root, ["revert", "неттакойрев", "--path", "notes/a.md"])
    assert proc.returncode == 6, proc.stderr


# --- tag ---------------------------------------------------------------------


def test_tag_on_last_event(root, kb):
    data = _json(_run(CliRunner(), ["--root", str(root), "tag", "rel-1", "--message", "первый"]))["data"]
    assert data["tag"] == "rel-1" and data["message"] == "первый"


def test_tag_on_empty_journal(root):
    runner = CliRunner()
    result = runner.invoke(cli, ["--root", str(root), "tag", "x"])
    assert isinstance(result.exception, TodocError)
    assert result.exception.code == "history.revision_unknown"


# --- history gc / adopt / export ---------------------------------------------


def test_history_gc_dry_run_and_apply(root, kb):
    runner = CliRunner()
    dry = _json(_run(runner, ["--root", str(root), "history", "gc", "--dry-run"]))["data"]
    assert dry["dry_run"] is True and dry["kept_events"] == 1
    real = _json(_run(runner, ["--root", str(root), "history", "gc"]))["data"]
    assert real["dry_run"] is False and real["kept_events"] == 1


def test_history_gc_purge_before(root, kb):
    data = _json(_run(CliRunner(), ["--root", str(root), "history", "gc",
                                    "--purge-before", "2099-01-01T00:00:00Z"]))["data"]
    assert data["removed_events"] == 1 and data["kept_events"] == 0


def test_history_gc_keep_objects(root, kb):
    data = _json(_run(CliRunner(), ["--root", str(root), "history", "gc", "--keep-objects", "0"]))["data"]
    assert data["kept_events"] == 1


def test_history_adopt(root):
    runner = CliRunner()
    notes = root / "notes"
    notes.mkdir()
    (notes / "a.md").write_text("---\ntitle: \"А\"\n---\n\nтекст\n", encoding="utf-8")
    _run(runner, ["--root", str(root), "index", "rebuild"])
    data = _json(_run(runner, ["--root", str(root), "history", "adopt"]))["data"]
    assert data["paths"] >= 1
    assert _json(_run(runner, ["--root", str(root), "log"]))["data"]["events"][0]["kind"] == "snapshot"


def test_history_export(root, kb):
    target = root / "backup"
    data = _json(_run(CliRunner(), ["--root", str(root), "history", "export", "--to", "backup"]))["data"]
    assert data["exported"] >= 2
    assert (target / "journal.jsonl").is_file()


def test_history_export_outside_root_refused(root, kb, tmp_path):
    runner = CliRunner()
    result = runner.invoke(cli, ["--root", str(root), "history", "export", "--to", str(tmp_path / "x")])
    assert isinstance(result.exception, TodocError)
    assert result.exception.code == "access.outside_data_root"


# --- сквозные K47, K48 -------------------------------------------------------


def test_history_commands_never_prompt(root, kb):
    """K47: ни одна новая команда не требует TTY при --no-input."""
    runner = CliRunner()
    rev = _first_rev(root)
    for args in (["log"], ["show", "--path", "notes/a.md"], ["blame", "--path", "notes/a.md"],
                 ["diff", rev, "--path", "notes/a.md"], ["revert", rev, "--path", "notes/a.md"],
                 ["history", "gc", "--dry-run"]):
        result = _run(runner, ["--root", str(root), "--no-input", *args])
        assert result.exit_code == 0, (args, result.output)


def test_history_errors_are_envelopes(root, kb):
    """K48: ошибка — один конверт ok:false в stdout и ненулевой exit code."""
    for args, code in ((["show", "нет", "--path", "notes/a.md"], 6),
                       (["log", "--section", "## Решение"], 2),
                       (["revert", "нет", "--path", "notes/a.md"], 6)):
        proc = _run_cli(root, args)
        assert proc.returncode == code, (args, proc.stderr)
        envelope = json.loads(proc.stdout)
        assert envelope["ok"] is False and envelope["next_actions"]


# --- ветки ошибок CLI --------------------------------------------------------


def test_show_missing_path(root, kb):
    result = _run(CliRunner(), ["--root", str(root), "show", "--path", "нет.md"])
    assert isinstance(result.exception, TodocError)
    assert result.exception.code == "history.revision_unknown"


def test_diff_unavailable_side(root, kb):
    rev = _first_rev(root)
    result = _run(CliRunner(), ["--root", str(root), "diff", rev, "--path", "нет.md"])
    assert isinstance(result.exception, TodocError)
    assert result.exception.code == "history.revision_unknown"


def test_diff_budget_truncates_output(root, kb):
    rev = _first_rev(root)
    data = _json(_run(CliRunner(), ["--root", str(root), "diff", rev, "--path", "notes/a.md",
                                    "--budget", "40"]))["data"]
    assert 0 < data["lines"] <= 1


def test_revert_of_creation_has_no_before(root):
    """Откат создания файла: файла до события не было — отдельная ошибка, не падение."""
    runner = CliRunner()
    created = _run(runner, ["--root", str(root), "docs", "new", "--title", "Новый"])
    assert created.exit_code == 0, created.output
    events = _json(_run(runner, ["--root", str(root), "log", "--limit", "50"]))["data"]["events"]
    created = [e for e in events if e["kind"] == "doc.create"]
    assert created, events
    path = created[-1]["paths"][0]["path"]
    result = _run(runner, ["--root", str(root), "revert", created[-1]["rev"], "--path", path])
    assert isinstance(result.exception, TodocError)
    assert result.exception.code == "history.revision_unknown"


# --- режим observed через CLI ------------------------------------------------


def test_external_edit_is_observed(root, kb):
    """K-требование Фазы 1: внешняя правка мимо CLI попадает в журнал."""
    runner = CliRunner()
    _run(runner, ["--root", str(root), "history", "adopt"])
    before_events = _json(_run(runner, ["--root", str(root), "log", "--limit", "50"]))["data"]["total"]

    kb["doc"].write_text(kb["doc"].read_text(encoding="utf-8") + "внешняя строка\n", encoding="utf-8")
    _run(runner, ["--root", str(root), "index", "rebuild"])
    events = _json(_run(runner, ["--root", str(root), "log", "--limit", "50"]))["data"]["events"]
    assert len(events) == before_events + 1
    assert events[0]["kind"] == "external.change"
    assert events[0]["actor"] == "external"


def test_read_commands_do_not_grow_journal(root, kb):
    """Запуск команд сам по себе не пишет событий: журнал растёт только от фактов."""
    runner = CliRunner()
    _run(runner, ["--root", str(root), "history", "adopt"])
    total = _json(_run(runner, ["--root", str(root), "log", "--limit", "50"]))["data"]["total"]
    for args in (["index", "rebuild"], ["index", "rebuild"], ["docs", "tree"],
                 ["index", "status"], ["stale"], ["log"]):
        _run(runner, ["--root", str(root), *args])
    assert _json(_run(runner, ["--root", str(root), "log", "--limit", "50"]))["data"]["total"] == total


def test_observed_mode_off(root, kb):
    """`history.mode: off` отключает наблюдение, журнал остаётся пустым от внешних правок."""
    runner = CliRunner()
    config = root / ".todoc" / "dataset.json"
    data = json.loads(config.read_text(encoding="utf-8"))
    data["history"] = {"mode": "off"}
    config.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    _run(runner, ["--root", str(root), "history", "adopt"])
    kb["doc"].write_text(kb["doc"].read_text(encoding="utf-8") + "внешняя строка\n", encoding="utf-8")
    _run(runner, ["--root", str(root), "index", "rebuild"])
    events = _json(_run(runner, ["--root", str(root), "log", "--limit", "50"]))["data"]["events"]
    # doc.edit оставлен фикстурой; важно, что внешней правки в журнале нет
    assert [e["kind"] for e in events] == ["snapshot", "doc.edit"]


def test_diff_unknown_second_revision(root, kb):
    """Правая сторона недоступна — отдельная ветка, а не сообщение про левую."""
    result = _run(CliRunner(), ["--root", str(root), "diff", _first_rev(root), "неттакойрев",
                                "--path", "notes/a.md"])
    assert isinstance(result.exception, TodocError)
    assert result.exception.code == "history.revision_unknown"


def test_revert_of_baseline_says_why(root, kb):
    """Базовая линия: сообщение объясняет, что состояния «до» не существует."""
    runner = CliRunner()
    _run(runner, ["--root", str(root), "history", "adopt"])
    events = _json(_run(runner, ["--root", str(root), "log", "--kind", "snapshot"]))["data"]["events"]
    result = _run(runner, ["--root", str(root), "revert", events[0]["rev"], "--path", "notes/a.md"])
    assert isinstance(result.exception, TodocError)
    assert "нет состояния «до»" in result.exception.message


def test_show_binary_content_reports_unreadable(root, kb):
    runner = CliRunner()
    rev = _first_rev(root)
    broken = b"\xff\xfe\x00" + "бинарь".encode("utf-8")
    kb["doc"].write_bytes(broken)
    kb["patch"].write_text(json.dumps({"ops": [{"line": 11, "text": "после"}]}), encoding="utf-8")
    _run(runner, ["--root", str(root), "docs", "edit", "--id", "doc:notes/a.md",
                  "--patch-file", str(kb["patch"]), "--apply"])
    result = _run(runner, ["--root", str(root), "show", rev, "--path", "notes/a.md"])
    assert isinstance(result.exception, TodocError)
    assert result.exception.code == "history.journal_unreadable"


def test_missing_patch_file_is_envelope(root, kb):
    """Отсутствующий --patch-file — конверт usage.error, а не трейсбек (P11)."""
    proc = _run_cli(root, ["docs", "edit", "--id", "doc:notes/a.md",
                           "--patch-file", str(root / "нет.json"), "--apply"])
    assert proc.returncode == 2, proc.stderr
    envelope = json.loads(proc.stdout)
    assert envelope["ok"] is False
    assert envelope["diagnostics"][0]["code"] == "usage.error"


def test_missing_patch_file_raises_usage_error_in_process(root, kb):
    """Тот же случай in-process: CliRunner видит TodocError, а не FileNotFoundError."""
    result = _run(CliRunner(), ["--root", str(root), "docs", "edit", "--id", "doc:notes/a.md",
                                "--patch-file", str(root / "нет.json"), "--apply"])
    assert isinstance(result.exception, TodocError)
    assert result.exception.code == "usage.error"
    assert result.exception.exit_code == 2


def test_show_reports_lost_snapshot(root, kb):
    """Утраченный снимок — history.object_missing, а не общая ошибка ревизии."""
    from todoc.adapters.history import journal as _journal
    from todoc.adapters.history import objects as _objects

    rev = _first_rev(root)
    kb["patch"].write_text(json.dumps({"ops": [{"line": 11, "text": "третья версия"}]}), encoding="utf-8")
    _run(CliRunner(), ["--root", str(root), "docs", "edit", "--id", "doc:notes/a.md",
                       "--patch-file", str(kb["patch"]), "--apply"])
    later = _journal.read_events(root)[-1]
    _objects.remove_object(root, later["paths"][0]["before"])
    result = _run(CliRunner(), ["--root", str(root), "show", rev, "--path", "notes/a.md"])
    assert isinstance(result.exception, TodocError)
    assert result.exception.code == "history.object_missing"


def test_revert_of_old_revision_warns_range_conflict(kb):
    """Файл менялся после откатываемой ревизии: предупреждение в конверте, откат возможен."""
    runner = CliRunner()
    root = kb["doc"].parent.parent
    first = _json(_run(runner, ["--root", str(root), "log"]))["data"]["events"][0]["rev"]
    patch = root / "patch2.json"
    patch.write_text(json.dumps({"ops": [{"line": 12, "text": "третья версия"}]}), encoding="utf-8")
    assert _run(runner, ["--root", str(root), "docs", "edit", "--id", "doc:notes/a.md",
                         "--patch-file", str(patch), "--apply"]).exit_code == 0

    envelope = _json(_run(runner, ["--root", str(root), "revert", first, "--path", "notes/a.md",
                                   "--apply"]))
    assert envelope["ok"] is True, "конфликт — предупреждение, а не отказ"
    assert envelope["data"]["range_conflict"] is True
    codes = [d["code"] for d in envelope["diagnostics"]]
    assert codes == ["history.range_conflict"]
    assert envelope["diagnostics"][0]["severity"] == "warning"


def test_revert_of_latest_revision_has_no_conflict(kb):
    runner = CliRunner()
    root = kb["doc"].parent.parent
    latest = _json(_run(runner, ["--root", str(root), "log"]))["data"]["events"][-1]["rev"]
    envelope = _json(_run(runner, ["--root", str(root), "revert", latest, "--path", "notes/a.md"]))
    assert envelope["data"]["range_conflict"] is False
    assert envelope["diagnostics"] == []
