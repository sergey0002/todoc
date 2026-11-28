"""Acceptance tests for directed edges and the graph and tree CLIs."""

import json

from click.testing import CliRunner

from todoc.cli import cli
from todoc.output.views import mermaid_graph


def test_graph_retains_edge_direction_multiplicity_and_pagination(root):
    files = {
        "a.json": ("note:a", [("supports", "note:b"), ("supports", "note:b"), ("self", "note:a")]),
        "b.json": ("note:b", [("blocked_by", "note:a"), ("supports", "note:c")]),
    }
    for path, (identity, relations) in files.items():
        record = {"record_id": identity, "entity_type": "note", "title": path,
                  "relations": [{"type_id": kind, "target": {"id": target, "kind": "record"}}
                                for kind, target in relations]}
        (root / path).write_text(json.dumps(record), encoding="utf-8")
    runner = CliRunner()
    command = ["relations", "graph", "--root", str(root), "--from", "note:a"]

    def collection(*args):
        result = runner.invoke(cli, [*command, *args])
        assert result.exit_code == 0, result.exception
        return json.loads(result.output)["data"]

    zero = collection("--depth", "0")
    assert zero["meta"]["total"] == 0 and zero["result"]["nodes"] == ["note:a"]
    first = collection("--depth", "1", "--limit", "2")
    assert first["meta"]["total"] == 4
    second = collection("--depth", "1", "--cursor", first["meta"]["next_cursor"], "--view", "flat")
    result = first["result"]["edges"] + second["result"]["items"]
    assert [(item["from"], item["to"]) for item in result] == [
        ("note:a", "note:b"), ("note:a", "note:b"), ("note:a", "note:a"), ("note:b", "note:a"),
    ]
    assert [result[index]["provenance"]["pointer"] for index in (0, 1)] == ["/relations/0", "/relations/1"]
    assert collection("--depth", "2", "--type", "supports")["meta"]["total"] == 3
    stale = runner.invoke(cli, [*command, "--depth", "2", "--cursor", first["meta"]["next_cursor"]])
    assert stale.exit_code == 2
    md = runner.invoke(cli, [*command, "--output", "markdown"])
    assert md.exit_code == 0 and "flowchart LR" in md.output and "-->" in md.output

    tree_cmd = ["relations", "tree", "--root", str(root), "--from", "note:a", "--depth", "2", "--limit", "1"]
    tree_first = json.loads(runner.invoke(cli, tree_cmd).output)["data"]
    tree_second = runner.invoke(cli, [*tree_cmd, "--cursor", tree_first["meta"]["next_cursor"]])
    assert tree_second.exit_code == 0
    assert json.loads(tree_second.output)["data"]["meta"]["returned"] == 1


def test_mermaid_encodes_directive_and_quote_characters():
    first = 'doc:"abc"\nclick n0 "other"'
    diagram = mermaid_graph([first, "b"], [{"from": first, "to": "b", "type_id": 'a"|\'\n'}])
    lines = diagram.splitlines()
    assert len(lines) == 4
    assert "#34;" in lines[1] and "#10;" in lines[1] and "#124;" in lines[3]
