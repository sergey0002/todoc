# tests/unit/test_records_undo.py — план entity-catalog З4 (T3):
# records undo-relation — точечный откат ребра из ревизий журнала.
import json

from click.testing import CliRunner

from todoc.adapters.filesystem.scanner import file_hash
from todoc.adapters.history import journal
from todoc.cli import cli
from todoc.errors import TodocError
from todoc.service import HistoryRecorder


def _run(runner, args):
    result = runner.invoke(cli, args)
    if isinstance(result.exception, TodocError):
        result.exit_code = result.exception.exit_code
    return result


def _json(result):
    return json.loads(result.output)


def _init(runner, tmp_path):
    assert _run(runner, ["init", "--apply", "--root", str(tmp_path), "--no-input"]).exit_code == 0


def _record_text(record_id, relations):
    return json.dumps({"record_id": record_id, "entity_type": "document", "title": "Т",
                       "relations": relations}, ensure_ascii=False, indent=2) + "\n"


def _write_with_history(tmp_path, record_id, versions):
    """Пишет версии файла записи, каждую — через журнал (образ «до» + событие)."""
    rel = "records/documents/a.json"
    path = tmp_path / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    recorder = HistoryRecorder(tmp_path)
    before = None
    for text in versions:
        path.write_text(text, encoding="utf-8")
        recorder.record(rel, before, text.encode("utf-8"), "record.write")
        before = text.encode("utf-8")


def _rebuild(runner, tmp_path):
    assert _run(runner, ["index", "rebuild", "--apply", "--root", str(tmp_path)]).exit_code == 0


def test_undo_added_edge_preview_then_apply(tmp_path):
    runner = CliRunner()
    _init(runner, tmp_path)
    _write_with_history(tmp_path, "document:a", [
        _record_text("document:a", []),
        _record_text("document:a", [{"type_id": "supports", "target": {"kind": "record", "id": "document:b"}}]),
    ])
    _rebuild(runner, tmp_path)
    plan = _json(_run(runner, ["records", "undo-relation", "--root", str(tmp_path),
                               "--id", "document:a", "--pointer", "/relations/0"]))
    assert plan["ok"] and plan["data"]["result"]["preview"] is True
    p = plan["data"]["result"]["plan"]
    assert p["mode"] == "remove" and p["previous_present"] is False
    assert p["current"]["type_id"] == "supports"
    events_before = len(journal.read_events(tmp_path))
    hash_before = file_hash(tmp_path / "records/documents/a.json")
    applied = _json(_run(runner, ["records", "undo-relation", "--root", str(tmp_path),
                                  "--id", "document:a", "--pointer", "/relations/0",
                                  "--apply", "--expected-hash", hash_before]))
    assert applied["ok"], applied
    data = json.loads((tmp_path / "records/documents/a.json").read_text(encoding="utf-8"))
    assert data["relations"] == []
    assert applied["data"]["result"]["new_hash"] == file_hash(tmp_path / "records/documents/a.json")
    assert len(journal.read_events(tmp_path)) == events_before + 1  # новая ревизия в журнале
    v = _json(_run(runner, ["validate", "--root", str(tmp_path), "--all"]))
    assert v["ok"] is True, v["diagnostics"]


def test_undo_modified_edge_restores_previous_target(tmp_path):
    runner = CliRunner()
    _init(runner, tmp_path)
    (tmp_path / "records/documents").mkdir(parents=True, exist_ok=True)
    (tmp_path / "records/documents/b.json").write_text(_record_text("document:b", []), encoding="utf-8")
    (tmp_path / "records/documents/c.json").write_text(_record_text("document:c", []), encoding="utf-8")
    _write_with_history(tmp_path, "document:a", [
        _record_text("document:a", [{"type_id": "supports", "target": {"kind": "record", "id": "document:b"}}]),
        _record_text("document:a", [{"type_id": "supports", "target": {"kind": "record", "id": "document:c"}}]),
    ])
    _rebuild(runner, tmp_path)
    plan = _json(_run(runner, ["records", "undo-relation", "--root", str(tmp_path),
                               "--id", "document:a", "--pointer", "/relations/0"]))
    p = plan["data"]["result"]["plan"]
    assert p["mode"] == "restore" and p["previous_present"] is True
    assert p["previous"]["target"]["id"] == "document:b"
    hash_before = file_hash(tmp_path / "records/documents/a.json")
    _run(runner, ["records", "undo-relation", "--root", str(tmp_path),
                  "--id", "document:a", "--pointer", "/relations/0",
                  "--apply", "--expected-hash", hash_before])
    data = json.loads((tmp_path / "records/documents/a.json").read_text(encoding="utf-8"))
    assert data["relations"][0]["target"]["id"] == "document:b"
    v = _json(_run(runner, ["validate", "--root", str(tmp_path), "--all"]))
    assert v["ok"] is True, v["diagnostics"]


def test_undo_clean_journal_revision_missing(tmp_path):
    runner = CliRunner()
    _init(runner, tmp_path)
    path = tmp_path / "records/documents/a.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / "records/documents").mkdir(parents=True, exist_ok=True)
    (tmp_path / "records/documents/b.json").write_text(_record_text("document:b", []), encoding="utf-8")
    path.write_text(_record_text("document:a",
                                 [{"type_id": "supports", "target": {"kind": "record", "id": "document:b"}}]),
                    encoding="utf-8")
    _rebuild(runner, tmp_path)
    r = _run(runner, ["records", "undo-relation", "--root", str(tmp_path),
                      "--id", "document:a", "--pointer", "/relations/0"])
    assert r.exit_code == 1
    assert r.exception.code == "history.revision_missing"


def test_undo_pointer_out_of_range_and_malformed(tmp_path):
    runner = CliRunner()
    _init(runner, tmp_path)
    _write_with_history(tmp_path, "document:a", [
        _record_text("document:a", [{"type_id": "supports", "target": {"kind": "record", "id": "document:b"}}]),
    ])
    _rebuild(runner, tmp_path)
    r = _run(runner, ["records", "undo-relation", "--root", str(tmp_path),
                      "--id", "document:a", "--pointer", "/relations/99"])
    assert r.exit_code == 3
    assert r.exception.code == "edit.relation_missing"
    r2 = _run(runner, ["records", "undo-relation", "--root", str(tmp_path),
                       "--id", "document:a", "--pointer", "/relations/x"])
    assert r2.exit_code == 2  # usage.error


def test_undo_cas_conflict_and_success(tmp_path):
    runner = CliRunner()
    _init(runner, tmp_path)
    _write_with_history(tmp_path, "document:a", [
        _record_text("document:a", []),
        _record_text("document:a", [{"type_id": "supports", "target": {"kind": "record", "id": "document:b"}}]),
    ])
    _rebuild(runner, tmp_path)
    r = _run(runner, ["records", "undo-relation", "--root", str(tmp_path),
                      "--id", "document:a", "--pointer", "/relations/0",
                      "--apply", "--expected-hash", "deadbeef"])
    assert r.exit_code == 5  # конфликт CAS
    assert r.exception.code == "write.hash_mismatch"
    hash_before = file_hash(tmp_path / "records/documents/a.json")
    applied = _json(_run(runner, ["records", "undo-relation", "--root", str(tmp_path),
                                  "--id", "document:a", "--pointer", "/relations/0",
                                  "--apply", "--expected-hash", hash_before]))
    assert applied["ok"], applied
    data = json.loads((tmp_path / "records/documents/a.json").read_text(encoding="utf-8"))
    assert data["relations"] == []
