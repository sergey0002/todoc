"""CLI Фазы 3: `timeline`, `records query --as-of`, коды `temporal.*`."""

from __future__ import annotations

import json

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


def _write_record(root, rel_path, payload):
    path = root / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


@pytest.fixture()
def kb(root):
    """Датасет с засеянными интервалами: работодатель менялся в 2024-06."""
    _write_record(root, "records/persons/a.json", {
        "schema_version": 1, "record_id": "person:a", "entity_type": "person", "name": "A",
        "valid_from": "2020-01-01", "valid_to": "2024-06-01",
        "relations": [{"type_id": "performed_by", "target": {"kind": "record", "id": "person:b"},
                       "valid_from": "2020-01-01", "valid_to": "2024-06-01",
                       "observed_at": "2020-01-05T10:00:00Z", "superseded_at": "2024-06-01T09:00:00Z"}],
    })
    _write_record(root, "records/persons/b.json", {
        "schema_version": 1, "record_id": "person:b", "entity_type": "person", "name": "B",
    })
    _write_record(root, "records/persons/c.json", {
        "schema_version": 1, "record_id": "person:c", "entity_type": "person", "name": "C",
        "valid_from": "2024-06-01",
    })
    return root


def _query(root, spec):
    path = root / "queries" / "temporal.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
    return str(path)


def test_records_query_as_of_cuts_by_valid_time(kb):
    runner = CliRunner()
    assert _run(runner, ["--root", str(kb), "index", "rebuild", "--apply"]).exit_code == 0
    query_file = _query(kb, {"entity_type": "person"})

    before = _json(_run(runner, ["--root", str(kb), "records", "query",
                                 "--query-file", query_file, "--as-of", "2023-01-01"]))["data"]
    after = _json(_run(runner, ["--root", str(kb), "records", "query",
                                "--query-file", query_file, "--as-of", "2025-01-01"]))["data"]
    assert before["meta"]["as_of"] == "2023-01-01"
    assert sorted(r["record_id"] for r in before["result"]["items"]) == ["person:a", "person:b"]
    assert sorted(r["record_id"] for r in after["result"]["items"]) == ["person:b", "person:c"]
    assert before["meta"]["total"] == 2 and after["meta"]["total"] == 2


def test_records_query_without_as_of_hides_closed_records(kb):
    """Без точки во времени закрытый факт не показывается как правда о настоящем."""
    runner = CliRunner()
    assert _run(runner, ["--root", str(kb), "index", "rebuild", "--apply"]).exit_code == 0
    result = _json(_run(runner, ["--root", str(kb), "records", "query",
                                 "--query-file", _query(kb, {"entity_type": "person"})]))["data"]
    ids = sorted(r["record_id"] for r in result["result"]["items"])
    assert ids == ["person:a", "person:b", "person:c"]
    assert result["meta"]["as_of"] is None


def test_records_query_rejects_unparseable_as_of(kb):
    runner = CliRunner()
    assert _run(runner, ["--root", str(kb), "index", "rebuild", "--apply"]).exit_code == 0
    result = _run(runner, ["--root", str(kb), "--output", "json", "records", "query",
                           "--query-file", _query(kb, {"entity_type": "person"}),
                           "--as-of", "примерно май"])
    assert result.exit_code == 3
    assert result.exception.code == "temporal.invalid_instant"


def test_timeline_lists_facts_and_events(kb):
    runner = CliRunner()
    assert _run(runner, ["--root", str(kb), "index", "rebuild", "--apply"]).exit_code == 0
    data = _json(_run(runner, ["--root", str(kb), "timeline"]))["data"]["result"]
    facts = [e for e in data["items"] if e["entry"] == "fact"]
    assert len(data["items"]) >= 1
    assert facts, "отношение с интервалом обязано попасть в ленту"
    assert facts[0]["type_id"] == "performed_by"
    assert facts[0]["valid_from"] == "2020-01-01"


def test_timeline_as_of_hides_closed_fact(kb):
    runner = CliRunner()
    assert _run(runner, ["--root", str(kb), "index", "rebuild", "--apply"]).exit_code == 0
    before = _json(_run(runner, ["--root", str(kb), "timeline", "--as-of", "2023-01-01"]))["data"]
    after = _json(_run(runner, ["--root", str(kb), "timeline", "--as-of", "2025-01-01"]))["data"]["result"]
    assert [e["valid_to"] for e in before["result"]["items"] if e["entry"] == "fact"] == ["2024-06-01"]
    assert after["items"] == []
    # Дата без времени остаётся датой: это полночь того дня.
    assert before["meta"]["scope"]["as_of"] == "2023-01-01"


def test_timeline_path_filter(kb):
    runner = CliRunner()
    assert _run(runner, ["--root", str(kb), "index", "rebuild", "--apply"]).exit_code == 0
    data = _json(_run(runner, ["--root", str(kb), "timeline", "--path", "records/persons/b.json"]))["data"]["result"]
    assert data["items"] == []


def test_timeline_rejects_unparseable_as_of(kb):
    runner = CliRunner()
    result = _run(runner, ["--root", str(kb), "--output", "json", "timeline", "--as-of", "вчера"])
    assert result.exit_code == 3
    assert result.exception.code == "temporal.invalid_instant"


def test_timeline_limit_reports_truncation(kb):
    runner = CliRunner()
    assert _run(runner, ["--root", str(kb), "index", "rebuild", "--apply"]).exit_code == 0
    data = _json(_run(runner, ["--root", str(kb), "timeline", "--limit", "0"]))["data"]
    assert data["meta"]["truncated"] is True and data["result"]["items"] == []
    assert data["meta"]["total"] >= 1 and data["meta"]["next_cursor"] is None


def test_validate_reports_inverted_interval(kb):
    _write_record(kb, "records/persons/bad.json", {
        "schema_version": 1, "record_id": "person:bad", "entity_type": "person",
        "valid_from": "2024-06-01", "valid_to": "2024-01-01",
    })
    runner = CliRunner()
    result = _run(runner, ["--root", str(kb), "--output", "json", "validate", "--all"])
    envelope = _json(result)
    codes = [d["code"] for d in envelope["diagnostics"]]
    assert "temporal.invalid_interval" in codes
    diag = next(d for d in envelope["diagnostics"] if d["code"] == "temporal.invalid_interval")
    assert diag["location"]["pointer"] == "/valid_to"
    assert diag["path"] == "records/persons/bad.json"


def test_validate_reports_relation_instant(kb):
    _write_record(kb, "records/persons/bad2.json", {
        "schema_version": 1, "record_id": "person:bad2", "entity_type": "person",
        "relations": [{"type_id": "performed_by", "target": {"kind": "record", "id": "person:b"},
                       "valid_from": "не дата"}],
    })
    runner = CliRunner()
    result = _json(_run(runner, ["--root", str(kb), "--output", "json", "validate", "--all"]))
    codes = [d["code"] for d in result["diagnostics"]]
    assert "temporal.invalid_instant" in codes
