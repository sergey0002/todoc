# tests/cli/test_cli_status.py — план «скилы-взаимодействия» З2:
# CLI docs status / records status — сет одного поля с валидацией набора типа.
import json

from click.testing import CliRunner

from todoc.cli import cli
from todoc.errors import TodocError

IDEA_STATUSES = ["captured", "planned", "in_progress", "done", "rejected", "superseded"]
TASK_STATUSES = ["open", "in_progress", "done", "cancelled"]

IDEA_MD = ('---\nid: doc:idea-x\ntitle: "Идея"\ndoc_type: idea\nlang: ru\n'
           "created: 2026-01-01\nupdated: 2026-01-01\nstatus: captured\n---\n\n"
           "# Идея\n\nТело идеи, которое не должно измениться.\n")

TASK_REC = {"schema_version": 1, "record_id": "task:demo-1", "entity_type": "task",
            "title": "Дело", "status": "open", "source": "user"}


def _run(runner, args):
    result = runner.invoke(cli, args)
    if isinstance(result.exception, TodocError):
        result.exit_code = result.exception.exit_code
    return result


def _json(result):
    return json.loads(result.output)


def _init_with_types(runner, tmp_path):
    assert _run(runner, ["init", "--apply", "--root", str(tmp_path), "--no-input"]).exit_code == 0
    idea = tmp_path / ".todoc" / "doc_types" / "idea"
    idea.mkdir(parents=True)
    (idea / "type.json").write_text(json.dumps(
        {"schema_version": 1, "type_id": "idea", "version": "0.1", "kind": "doc_type",
         "description": "Идея.", "format": "markdown", "allowed_statuses": IDEA_STATUSES},
        ensure_ascii=False) + "\n", encoding="utf-8")
    task = tmp_path / ".todoc" / "entity_types" / "task"
    task.mkdir(parents=True)
    (task / "type.json").write_text(json.dumps(
        {"schema_version": 1, "type_id": "task", "version": "0.1", "kind": "entity_type",
         "description": "Задача.", "format": "json", "schema": "schema.json",
         "path_template": "tasks/{slug}.json",
         "required_fields": ["record_id", "entity_type", "title"]}, ensure_ascii=False) + "\n",
        encoding="utf-8")
    (task / "schema.json").write_text(json.dumps(
        {"type": "object",
         "required": ["schema_version", "record_id", "entity_type", "title"],
         "properties": {"schema_version": {"const": 1},
                        "record_id": {"type": "string", "pattern": "^task:[a-z0-9][a-z0-9-]*$"},
                        "entity_type": {"const": "task"}, "title": {"type": "string"},
                        "source": {"type": "string"},
                        "status": {"enum": TASK_STATUSES}}}, ensure_ascii=False) + "\n",
        encoding="utf-8")
    ideas = tmp_path / "ideas"
    ideas.mkdir()
    (ideas / "x.md").write_text(IDEA_MD, encoding="utf-8")
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    (tasks / "demo-1.json").write_text(
        json.dumps(TASK_REC, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    assert _run(runner, ["index", "rebuild", "--apply", "--root", str(tmp_path)]).exit_code == 0


def test_docs_status_get(tmp_path):
    runner = CliRunner()
    _init_with_types(runner, tmp_path)
    r = _run(runner, ["docs", "status", "--root", str(tmp_path), "--id", "doc:idea-x"])
    assert r.exit_code == 0, r.output
    data = _json(r)["data"]["result"]
    assert data["id"] == "doc:idea-x" and data["status"] == "captured"


def test_docs_status_get_without_status(tmp_path):
    runner = CliRunner()
    _init_with_types(runner, tmp_path)
    (tmp_path / "ideas" / "x.md").write_text(
        '---\nid: doc:idea-x\ntitle: "Идея"\ndoc_type: idea\nlang: ru\n---\n\n# Идея\n\nТело.\n',
        encoding="utf-8")
    _run(runner, ["index", "rebuild", "--apply", "--root", str(tmp_path)])
    r = _run(runner, ["docs", "status", "--root", str(tmp_path), "--id", "doc:idea-x"])
    assert r.exit_code == 0
    assert _json(r)["data"]["result"]["status"] is None


def test_docs_status_set_ok_preserves_body_and_bumps_updated(tmp_path):
    runner = CliRunner()
    _init_with_types(runner, tmp_path)
    before = (tmp_path / "ideas" / "x.md").read_text(encoding="utf-8")
    r = _run(runner, ["docs", "status", "--apply", "--root", str(tmp_path),
                      "--id", "doc:idea-x", "--set", "planned"])
    assert r.exit_code == 0, r.output
    data = _json(r)["data"]["result"]
    assert data["status"] == "planned" and data["new_hash"].startswith("sha256:")
    after = (tmp_path / "ideas" / "x.md").read_text(encoding="utf-8")
    # тело байт-в-байт, fm: только status и updated
    assert after.split("---", 2)[2] == before.split("---", 2)[2]
    assert "status: planned" in after and "status: captured" not in after
    assert "updated: 2026-01-01" not in after  # бампнуто на «сегодня»
    v = _json(_run(runner, ["validate", "--root", str(tmp_path), "--all"]))
    assert v["ok"] is True, v["diagnostics"]
    # history: запись о ревизии
    journal = (tmp_path / ".todoc" / "history" / "journal.jsonl")
    assert journal.is_file() and journal.read_text(encoding="utf-8").strip()


def test_docs_status_set_outside_set(tmp_path):
    runner = CliRunner()
    _init_with_types(runner, tmp_path)
    before = (tmp_path / "ideas" / "x.md").read_text(encoding="utf-8")
    r = _run(runner, ["docs", "status", "--apply", "--root", str(tmp_path),
                      "--id", "doc:idea-x", "--set", "blah"])
    assert r.exit_code != 0
    assert "docs.status_not_allowed" in getattr(r.exception, "code", str(r.exception))  # код в исключении (envelope — в main())
    assert (tmp_path / "ideas" / "x.md").read_text(encoding="utf-8") == before


def test_docs_status_set_without_status_field(tmp_path):
    runner = CliRunner()
    _init_with_types(runner, tmp_path)
    (tmp_path / "ideas" / "x.md").write_text(
        '---\nid: doc:idea-x\ntitle: "Идея"\ndoc_type: idea\nlang: ru\n---\n\n# Идея\n\nТело.\n',
        encoding="utf-8")
    _run(runner, ["index", "rebuild", "--apply", "--root", str(tmp_path)])
    r = _run(runner, ["docs", "status", "--apply", "--root", str(tmp_path),
                      "--id", "doc:idea-x", "--set", "planned"])
    assert r.exit_code != 0
    assert "docs.no_status_field" in getattr(r.exception, "code", str(r.exception))


def test_docs_status_not_found(tmp_path):
    runner = CliRunner()
    assert _run(runner, ["init", "--apply", "--root", str(tmp_path), "--no-input"]).exit_code == 0
    r = _run(runner, ["docs", "status", "--root", str(tmp_path), "--id", "doc:ghost"])
    assert r.exit_code != 0
    assert "docs.not_found" in getattr(r.exception, "code", str(r.exception))


def test_records_status_get_and_set_only_status_changes(tmp_path):
    runner = CliRunner()
    _init_with_types(runner, tmp_path)
    g = _run(runner, ["records", "status", "--root", str(tmp_path), "--id", "task:demo-1"])
    assert g.exit_code == 0 and _json(g)["data"]["result"]["status"] == "open"
    before = json.loads((tmp_path / "tasks" / "demo-1.json").read_text(encoding="utf-8"))
    r = _run(runner, ["records", "status", "--apply", "--root", str(tmp_path),
                      "--id", "task:demo-1", "--set", "in_progress"])
    assert r.exit_code == 0, r.output
    data = _json(r)["data"]["result"]
    assert data["status"] == "in_progress" and data["new_hash"].startswith("sha256:")
    after = json.loads((tmp_path / "tasks" / "demo-1.json").read_text(encoding="utf-8"))
    assert after.pop("status") == "in_progress" and before.pop("status") == "open"
    assert after == before  # остальные поля байт-в-байт по значению
    v = _json(_run(runner, ["validate", "--root", str(tmp_path), "--all"]))
    assert v["ok"] is True, v["diagnostics"]


def test_records_status_set_outside_enum(tmp_path):
    runner = CliRunner()
    _init_with_types(runner, tmp_path)
    before = (tmp_path / "tasks" / "demo-1.json").read_text(encoding="utf-8")
    r = _run(runner, ["records", "status", "--apply", "--root", str(tmp_path),
                      "--id", "task:demo-1", "--set", "blah"])
    assert r.exit_code != 0
    assert "records.status_not_allowed" in getattr(r.exception, "code", str(r.exception))
    assert (tmp_path / "tasks" / "demo-1.json").read_text(encoding="utf-8") == before


def test_records_status_not_found(tmp_path):
    runner = CliRunner()
    assert _run(runner, ["init", "--apply", "--root", str(tmp_path), "--no-input"]).exit_code == 0
    r = _run(runner, ["records", "status", "--root", str(tmp_path), "--id", "task:ghost"])
    assert r.exit_code != 0
    assert "records.not_found" in getattr(r.exception, "code", str(r.exception))


def test_docs_status_set_rejects_padded_value(tmp_path):
    # docs status: значение с обрамляющими пробелами/переводом строки → usage.error
    runner = CliRunner()
    _init_with_types(runner, tmp_path)
    r = _run(runner, ["docs", "status", "--apply", "--root", str(tmp_path),
                      "--id", "doc:idea-x", "--set", " planned "])
    assert r.exit_code != 0
    assert getattr(r.exception, "code", "") == "usage.error"


def test_records_status_with_schemaless_type_sets_openly(tmp_path):
    # запись типа без схемы/enum: сет любого статуса легален (набор не объявлен)
    runner = CliRunner()
    _init_with_types(runner, tmp_path)
    (tmp_path / ".todoc" / "entity_types" / "task" / "schema.json").unlink()
    _run(runner, ["index", "rebuild", "--apply", "--root", str(tmp_path)])
    r = _run(runner, ["records", "status", "--apply", "--root", str(tmp_path),
                      "--id", "task:demo-1", "--set", "paused"])
    assert r.exit_code == 0, r.output
    assert _json(r)["data"]["result"]["status"] == "paused"


def test_records_status_set_rejects_padded_value(tmp_path):
    # records status: значение с обрамляющими пробелами → usage.error, файл не тронут
    runner = CliRunner()
    _init_with_types(runner, tmp_path)
    before = (tmp_path / "tasks" / "demo-1.json").read_text(encoding="utf-8")
    r = _run(runner, ["records", "status", "--apply", "--root", str(tmp_path),
                      "--id", "task:demo-1", "--set", " open "])
    assert r.exit_code != 0
    assert getattr(r.exception, "code", "") == "usage.error"
    assert (tmp_path / "tasks" / "demo-1.json").read_text(encoding="utf-8") == before
