# tests/unit/test_mentions.py — план entity-catalog З2 (T8/T4/T6):
# mention-индекс в снапшоте, mentioned_in в records read, mention-вершины графа.
import json

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


def _init(runner, tmp_path):
    assert _run(runner, ["init", "--apply", "--root", str(tmp_path), "--no-input"]).exit_code == 0


def _record(tmp_path, rel, record_id):
    path = tmp_path / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"record_id": record_id, "entity_type": "document",
                                "title": "Т", "relations": []}, ensure_ascii=False, indent=2),
                    encoding="utf-8")


def _rebuild(runner, tmp_path):
    r = _run(runner, ["index", "rebuild", "--apply", "--root", str(tmp_path)])
    assert r.exit_code == 0, r.output
    return _json(r)


def test_mentions_published_and_mentioned_in(tmp_path):
    runner = CliRunner()
    _init(runner, tmp_path)
    _record(tmp_path, "records/documents/plan.json", "document:plan")
    md = tmp_path / "notes/b.md"
    md.parent.mkdir(parents=True, exist_ok=True)
    md.write_text("---\ntitle: B\n---\n\n# B\n\n"
                  "Витрина: [[document:plan]]. Поле: [[document:plan#/title]].\n", encoding="utf-8")
    _rebuild(runner, tmp_path)
    r = _run(runner, ["records", "read", "--root", str(tmp_path), "--id", "document:plan"])
    data = _json(r)["data"]["result"]
    mentioned = data["mentioned_in"]
    assert [m["file"] for m in mentioned] == ["notes/b.md", "notes/b.md"], mentioned
    assert [m["line"] for m in mentioned] == [7, 7], mentioned
    assert [m["fragment"] for m in mentioned] == ["", "/title"], mentioned


def test_mentions_doc_kind(tmp_path):
    runner = CliRunner()
    _init(runner, tmp_path)
    (tmp_path / "notes").mkdir()
    (tmp_path / "notes/a.md").write_text("---\ntitle: A\n---\n\n# A\n\nтекст.\n", encoding="utf-8")
    (tmp_path / "notes/b.md").write_text("---\ntitle: B\n---\n\n# B\n\n[страница](a.md#заголовок)\n",
                                         encoding="utf-8")
    _rebuild(runner, tmp_path)
    # doc-kind упоминания видны через снапшот напрямую (в records read их нет):
    idx = json.loads((tmp_path / ".todoc/index/current/mentions.json").read_text(encoding="utf-8"))
    assert len(idx) == 1, idx
    assert idx[0]["source_file"] == "notes/b.md"
    assert idx[0]["target"] == "notes/a.md"
    assert idx[0]["target_kind"] == "doc"
    assert idx[0]["source_fragment"] == "заголовок"


def test_graph_includes_mention_vertices(tmp_path):
    runner = CliRunner()
    _init(runner, tmp_path)
    _record(tmp_path, "records/documents/plan.json", "document:plan")
    md = tmp_path / "notes/b.md"
    md.parent.mkdir(parents=True, exist_ok=True)
    md.write_text("---\ntitle: B\n---\n\n# B\n\nВитрина: [[document:plan]]\n", encoding="utf-8")
    _rebuild(runner, tmp_path)
    r = _run(runner, ["relations", "graph", "--root", str(tmp_path), "--from", "document:plan"])
    edges = _json(r)["data"]["result"]["edges"]
    mention_edges = [e for e in edges if e.get("via") == "mention"]
    edge, = mention_edges
    assert (edge["from"], edge["to"]) == ("notes/b.md", "document:plan")
    assert edge["provenance"]["path"] == "notes/b.md" and edge["provenance"]["line"] > 0


def test_reuse_keeps_mentions_stable(tmp_path):
    runner = CliRunner()
    _init(runner, tmp_path)
    _record(tmp_path, "records/documents/plan.json", "document:plan")
    md = tmp_path / "notes/b.md"
    md.parent.mkdir(parents=True, exist_ok=True)
    md.write_text("---\ntitle: B\n---\n\n# B\n\nВитрина: [[document:plan]]\n", encoding="utf-8")
    _rebuild(runner, tmp_path)
    first = _json(_run(runner, ["records", "read", "--root", str(tmp_path), "--id", "document:plan"]))
    r = _rebuild(runner, tmp_path)  # корпус не менялся
    assert r["data"]["result"]["datasets"][0]["reused"] is True
    second = _json(_run(runner, ["records", "read", "--root", str(tmp_path), "--id", "document:plan"]))
    assert first["data"]["result"]["mentioned_in"] == second["data"]["result"]["mentioned_in"]
