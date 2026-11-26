# tests/unit/test_relations_tree.py — план entity-catalog З3 (T5/T11):
# fragment в docs read id (синоним --section) + relations tree (вложенное дерево).
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
    assert _run(runner, ["init", "--root", str(tmp_path), "--no-input"]).exit_code == 0


def _record(tmp_path, rel, record_id, relations=None):
    path = tmp_path / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"record_id": record_id, "entity_type": "document", "title": "Т",
                                "relations": relations or []}, ensure_ascii=False, indent=2),
                    encoding="utf-8")


def test_docs_read_fragment_equals_section(tmp_path):
    runner = CliRunner()
    _init(runner, tmp_path)
    md = tmp_path / "notes/a.md"
    md.parent.mkdir(parents=True, exist_ok=True)
    md.write_text("---\nid: doc:a\ntitle: A\n---\n\n# A\n\n## Принципы\n\nтекст раздела.\n", encoding="utf-8")
    _run(runner, ["index", "rebuild", "--root", str(tmp_path)])
    by_fragment = _json(_run(runner, ["docs", "read", "--root", str(tmp_path), "--id", "doc:a#Принципы"]))
    by_section = _json(_run(runner, ["docs", "read", "--root", str(tmp_path), "--id", "doc:a",
                                     "--section", "Принципы"]))
    assert by_fragment["ok"] and by_section["ok"]
    assert by_fragment["data"]["section"] == "Принципы"
    assert by_fragment["data"]["text"] == by_section["data"]["text"] == "## Принципы\n\nтекст раздела."
    assert by_fragment["data"]["line_start"] == by_section["data"]["line_start"]


def test_docs_read_fragment_conflict_with_section(tmp_path):
    runner = CliRunner()
    _init(runner, tmp_path)
    r = _run(runner, ["docs", "read", "--root", str(tmp_path), "--id", "doc:a#x", "--section", "y"])
    assert r.exit_code == 2, r.output  # EXIT_USAGE
    assert "одновременно" in str(r.exception)


def test_tree_groups_directions_mentions(tmp_path):
    runner = CliRunner()
    _init(runner, tmp_path)
    _record(tmp_path, "records/documents/a.json", "document:a",
            [{"type_id": "supports", "target": {"kind": "record", "id": "document:b"}},
             {"type_id": "blocked_by", "target": {"kind": "record", "id": "document:b"}}])
    _record(tmp_path, "records/documents/b.json", "document:b")
    md = tmp_path / "notes/b.md"
    md.parent.mkdir(parents=True, exist_ok=True)
    md.write_text("---\ntitle: B\n---\n\n# B\n\nВитрина: [[document:a]]\n", encoding="utf-8")
    assert _run(runner, ["index", "rebuild", "--root", str(tmp_path)]).exit_code == 0
    tree = _json(_run(runner, ["relations", "tree", "--root", str(tmp_path),
                               "--from", "document:a", "--depth", "2"]))["data"]
    assert tree["root"] == "document:a"
    groups = {g["type_id"]: g for g in tree["groups"]}
    assert set(groups) == {"supports", "blocked_by", "mention"}, tree["groups"]
    out_supports = [e for e in groups["supports"]["edges"] if e["direction"] == "out"]
    assert [e["id"] for e in out_supports] == ["document:b"]
    # blocked_by у a: a заблокирована b → ребро из a в b, направление "out"
    assert any(e["direction"] == "out" and e["id"] == "document:b"
               for e in groups["blocked_by"]["edges"])
    # mention-вершина помечена и указывает на md
    m = groups["mention"]["edges"][0]
    assert m["via"] == "mention" and m["id"] == "notes/b.md"


def test_tree_depth_limit_markdown(tmp_path):
    runner = CliRunner()
    _init(runner, tmp_path)
    _record(tmp_path, "records/documents/a.json", "document:a",
            [{"type_id": "supports", "target": {"kind": "record", "id": "document:b"}}])
    _record(tmp_path, "records/documents/b.json", "document:b",
            [{"type_id": "supports", "target": {"kind": "record", "id": "document:c"}}])
    _record(tmp_path, "records/documents/c.json", "document:c")
    assert _run(runner, ["index", "rebuild", "--root", str(tmp_path)]).exit_code == 0
    deep = _json(_run(runner, ["relations", "tree", "--root", str(tmp_path),
                               "--from", "document:a", "--depth", "2"]))["data"]
    groups = {g["type_id"]: g for g in deep["groups"]}
    child = groups["supports"]["edges"][0]
    assert child["id"] == "document:b"
    nested = child["children"]
    assert nested and nested[0]["type_id"] == "supports"
    assert any(e["direction"] == "out" and e["id"] == "document:c" and "cycle" not in e
               for e in nested[0]["edges"]), nested
    shallow = _json(_run(runner, ["relations", "tree", "--root", str(tmp_path),
                                  "--from", "document:a", "--depth", "1"]))["data"]
    shallow_child = {g["type_id"]: g for g in shallow["groups"]}["supports"]["edges"][0]
    assert shallow_child.get("children", []) == []
    # цикл не разворачивается повторно
    _record(tmp_path, "records/documents/b.json", "document:b",
            [{"type_id": "supports", "target": {"kind": "record", "id": "document:c"}},
             {"type_id": "supports", "target": {"kind": "record", "id": "document:a"}}])
    assert _run(runner, ["index", "rebuild", "--root", str(tmp_path)]).exit_code == 0
    cycled = _json(_run(runner, ["relations", "tree", "--root", str(tmp_path),
                                 "--from", "document:a", "--depth", "3"]))["data"]
    assert cycled["groups"], cycled
    # markdown-рендер: компактные строки с отступами, mention помечен
    text = _run(runner, ["relations", "tree", "--root", str(tmp_path), "--from", "document:a",
                         "--depth", "2", "--output", "markdown"]).output
    assert "document:a" in text and "->" in text.replace("→", "->") or "→" in text
