# tests/unit/test_entity_catalog_coverage.py — покрытие ветвей З1–З5
# (план entity-catalog): query (graph/tree), validator (mentions/якоря),
# history (previous_relation_state), write (сплайс/plan/apply), cli (отказы).
import json
from pathlib import Path

from click.testing import CliRunner

from todoc.adapters.filesystem.scanner import ScannedFile, file_hash
from todoc.adapters.history import journal, objects
from todoc.application.history import previous_relation_state
from todoc.application.query import build_tree, graph_neighbors
from todoc.application.validator import _check_link_targets, build_mentions
from todoc.application.write import (_json_array_element_span, apply_undo_relation,
                                     plan_undo_relation)
from todoc.cli import cli
from todoc.errors import TodocError

REL_A_B = {"type_id": "supports", "source_id": "document:a", "target_id": "document:b"}
MENTION_A = {"source_file": "notes/b.md", "source_line": 3, "source_fragment": "",
             "target": "document:a", "target_kind": "record"}


# --- query: graph_neighbors ---------------------------------------------------

def test_graph_type_filter_skips_mentions():
    edges = graph_neighbors([REL_A_B], "document:a", type_id="supports", mentions=[MENTION_A])
    assert edges == [{"type_id": "supports", "from": "document:a", "to": "document:b"}]


def test_graph_mention_from_md_root():
    # корень — md-файл: упоминание идёт в его target
    edges = graph_neighbors([], "notes/b.md", mentions=[MENTION_A])
    assert edges == [{"type_id": "mention", "via": "mention", "from": "notes/b.md",
                      "to": "document:a", "fragment": "",
                      "provenance": {"path": "notes/b.md", "line": MENTION_A["source_line"]}}]


def test_graph_mention_limit():
    second = {"source_file": "notes/c.md", "source_line": 1, "source_fragment": "/x",
              "target": "document:a", "target_kind": "record"}
    edges = graph_neighbors([], "document:a", limit=1, mentions=[MENTION_A, second])
    assert len(edges) == 1 and edges[0]["from"] == "notes/b.md"


# --- query: build_tree --------------------------------------------------------

def test_tree_type_filter_and_in_edges():
    other = {"type_id": "blocked_by", "source_id": "document:c", "target_id": "document:a"}
    incoming = {"type_id": "supports", "source_id": "document:c", "target_id": "document:a"}
    tree = build_tree([REL_A_B, other, incoming],
                      "document:a", type_id="supports", depth=1, mentions=[MENTION_A])
    assert [g["type_id"] for g in tree["groups"]] == ["supports"]  # blocked_by и mention отфильтрованы
    edges = tree["groups"][0]["edges"]
    assert {e["direction"] for e in edges} == {"out", "in"}


def test_tree_depth_zero_returns_empty():
    assert build_tree([REL_A_B], "document:a", depth=0)["groups"] == []


def test_tree_limit_truncates_group():
    rel2 = {"type_id": "supports", "source_id": "document:a", "target_id": "document:c"}
    tree = build_tree([REL_A_B, rel2], "document:a", depth=1, limit=1)
    assert tree["truncated"] is True
    group = tree["groups"][0]
    assert len(group["edges"]) == 1 and group["truncated"] is True


def test_tree_cycle_edge():
    rel = {"type_id": "supports", "source_id": "document:b", "target_id": "document:a"}
    tree = build_tree([REL_A_B, rel], "document:a", depth=2)
    child = tree["groups"][0]["edges"][0]
    assert child["id"] == "document:b"
    nested = child["children"][0]["edges"]
    assert any(e["id"] == "document:a" and e.get("cycle") for e in nested), nested


def test_tree_mention_fragment():
    m = dict(MENTION_A, source_fragment="/title")
    tree = build_tree([], "document:a", depth=1, mentions=[m])
    edge = tree["groups"][0]["edges"][0]
    assert edge["via"] == "mention" and edge["fragment"] == "/title"


# --- validator: build_mentions / _check_link_targets ---------------------------

def _scanned(tmp_path, rel, fmt="markdown"):
    return ScannedFile(rel, tmp_path / rel, fmt, (tmp_path / rel).stat().st_size,
                       "h" * 8)


def test_validator_scanned_miss_skipped(tmp_path):
    doc = type("D", (), {"links": []})()
    diags = _check_link_targets("d", [], {"notes/ghost.md": doc}, [], set())
    assert diags == []  # путь разбора не из скана — пропускается


def test_build_mentions_unreadable_file_skipped(tmp_path):
    bad = tmp_path / "notes/bad.md"
    bad.parent.mkdir(parents=True)
    bad.write_bytes(b"\xff\xfe not utf-8")
    scanned = [_scanned(tmp_path, "notes/bad.md")]
    assert build_mentions(tmp_path, scanned, [], {"notes/bad.md"}) == []


def test_check_targets_ambiguous_wikilink_skipped(tmp_path):
    (tmp_path / "notes").mkdir()
    (tmp_path / "notes/a.md").write_text("---\ntitle: A\n---\n\n# A\n\nтекст.\n", encoding="utf-8")
    (tmp_path / "notes/a.json").write_text('{"x": 1}', encoding="utf-8")
    src = tmp_path / "notes/b.md"
    src.write_text("---\ntitle: B\n---\n\n# B\n\nдвойное [[a#нет]]\n", encoding="utf-8")
    scanned = [_scanned(tmp_path, "notes/a.md"), _scanned(tmp_path, "notes/a.json", "json"),
               _scanned(tmp_path, "notes/b.md")]
    diags = _check_link_targets("d", scanned, {"notes/b.md": _md_doc(src)}, [],
                                {x.rel_path for x in scanned})
    assert diags == []  # неоднозначная цель не флагается ложным якорем


def test_check_targets_anchor_on_non_markdown(tmp_path):
    csv_doc = tmp_path / "notes/a.csv"
    csv_doc.parent.mkdir(parents=True)
    csv_doc.write_text("x\n1\n", encoding="utf-8")
    src = tmp_path / "notes/b.md"
    src.write_text("---\ntitle: B\n---\n\n# B\n\n[таблица](a.csv#строка)\n", encoding="utf-8")
    scanned = [_scanned(tmp_path, "notes/a.csv", "csv"), _scanned(tmp_path, "notes/b.md")]
    diags = _check_link_targets("d", scanned, {"notes/b.md": _md_doc(src)}, [], {x.rel_path for x in scanned})
    codes = [x.code for x in diags]
    assert "markdown.anchor_not_found" in codes, diags


def _md_doc(path: Path):
    from todoc.adapters.formats.markdown import parse_markdown
    return parse_markdown(path.read_text(encoding="utf-8"))


def test_check_targets_unreadable_target_skipped_real(tmp_path):
    (tmp_path / "notes").mkdir()
    (tmp_path / "notes/a.md").write_bytes(b"\xff\xfe not utf-8")
    src = tmp_path / "notes/b.md"
    src.write_text("---\ntitle: B\n---\n\n# B\n\nдвойное [[a#нет]]\n", encoding="utf-8")
    scanned = [_scanned(tmp_path, "notes/a.md"), _scanned(tmp_path, "notes/b.md")]
    diags = _check_link_targets("d", scanned, {"notes/b.md": _md_doc(src)}, [],
                                {"notes/a.md", "notes/b.md"})
    assert all(x.code != "markdown.anchor_not_found" for x in diags), diags


def test_inline_record_like_target_not_found(tmp_path):
    """inline-цель с ":" вне записей и файлов — markdown.record_not_found."""
    runner = CliRunner()
    assert runner.invoke(cli, ["init", "--apply", "--root", str(tmp_path), "--no-input"]).exit_code == 0
    md = tmp_path / "notes/b.md"
    md.parent.mkdir(parents=True)
    md.write_text("---\ntitle: B\n---\n\n# B\n\n[ссылка](document:missing)\n", encoding="utf-8")
    r = runner.invoke(cli, ["validate", "--root", str(tmp_path), "--all"])
    assert "markdown.record_not_found" in r.output


# --- history: previous_relation_state -----------------------------------------

def _event(root, path, before_digest, rev=None):
    return journal.append_event(root, {"schema_version": 1, "at": "2026-01-01T00:00:00Z",
                                       "kind": "record.write", "actor": "test", "rev": rev,
                                       "paths": [{"path": path, "before": before_digest,
                                                  "after": "sha256:" + "1" * 64, "git_head": None,
                                                  "ranges": []}]})


EDGE = {"type_id": "supports", "target": {"kind": "record", "id": "document:b"}}


def test_previous_state_snapshot_object_missing(tmp_path):
    _event(tmp_path, "records/documents/a.json", "sha256:" + "0" * 64, "rev1")
    out = previous_relation_state(tmp_path, "records/documents/a.json", 0, EDGE, [EDGE])
    assert out is None  # объект «до» отсутствует — ревизия пропущена


def test_previous_state_other_path_skipped(tmp_path):
    snap = objects.write_snapshot(tmp_path, json.dumps({"relations": [EDGE]}).encode())
    _event(tmp_path, "records/documents/other.json", snap, "rev1")
    out = previous_relation_state(tmp_path, "records/documents/a.json", 0, EDGE, [EDGE])
    assert out is None  # событие чужого файла не участвует


def test_previous_state_undecodable_snapshot(tmp_path):
    snap = objects.write_snapshot(tmp_path, b"\xff\xfe not json")
    _event(tmp_path, "records/documents/a.json", snap, "rev1")
    out = previous_relation_state(tmp_path, "records/documents/a.json", 0, EDGE, [EDGE])
    assert out is None


def test_previous_state_relations_not_a_list(tmp_path):
    snap = objects.write_snapshot(tmp_path, json.dumps({"relations": "x"}).encode())
    rev = _event(tmp_path, "records/documents/a.json", snap, "rev1")
    out = previous_relation_state(tmp_path, "records/documents/a.json", 0, EDGE, [EDGE])
    assert out == {"state": "absent", "value": None, "rev": rev,
                   "at": "2026-01-01T00:00:00Z"}  # ребро на позиции 0 не существовало


def test_previous_state_same_identity_new_value(tmp_path):
    # та же идентичность (type_id + target.id), другой payload ребра
    old_edge = {"type_id": "supports", "target": {"kind": "record", "id": "document:b"},
                "note": "старая формулировка"}
    snap = objects.write_snapshot(tmp_path, json.dumps({"relations": [old_edge]}).encode())
    rev = _event(tmp_path, "records/documents/a.json", snap, "rev1")
    out = previous_relation_state(tmp_path, "records/documents/a.json", 0, EDGE, [EDGE])
    assert out == {"state": "value", "value": old_edge, "rev": rev,
                   "at": "2026-01-01T00:00:00Z"}


def test_previous_state_identity_unchanged_goes_older(tmp_path):
    # идентичное ребро в старой версии — «не менялось», версия пропускается
    snap = objects.write_snapshot(tmp_path, json.dumps({"relations": [EDGE]}).encode())
    _event(tmp_path, "records/documents/a.json", snap, "rev1")
    out = previous_relation_state(tmp_path, "records/documents/a.json", 0, EDGE, [EDGE])
    assert out is None


# --- write: сплайс JSON -------------------------------------------------------

def test_span_rejects_non_object_and_garbage():
    assert _json_array_element_span("[1, 2]", "relations", 0) is None
    assert _json_array_element_span("{", "relations", 0) is None
    assert _json_array_element_span("{}", "relations", 0) is None
    assert _json_array_element_span('{"a": 1,', "relations", 0) is None
    assert _json_array_element_span("{a: 1}", "relations", 0) is None
    assert _json_array_element_span('{"a" 1}', "relations", 0) is None
    assert _json_array_element_span('{"x": bad, "relations": []}', "relations", 0) is None
    assert _json_array_element_span('{"relations": 5}', "relations", 0) is None
    assert _json_array_element_span('{"relations": [1', "relations", 0) is None
    assert _json_array_element_span('{"relations": [bad]}', "relations", 0) is None
    assert _json_array_element_span('{"relations": [1]}', "relations", 5) is None


def test_span_two_element_array_both_indices():
    text = '{"relations": [{"i": 1}, {"i": 2}]}'
    s0 = _json_array_element_span(text, "relations", 0)
    s1 = _json_array_element_span(text, "relations", 1)
    assert json.loads(text[s0[0]:s0[1]]) == {"i": 1}
    assert json.loads(text[s1[0]:s1[1]]) == {"i": 2}


def test_splice_remove_first_and_last_of_two():
    from todoc.application.write import _splice_element
    text = '{"relations": [{"i": 1}, {"i": 2}]}'
    s0 = _json_array_element_span(text, "relations", 0)
    out = json.loads(_splice_element(text, s0, None))
    assert out["relations"] == [{"i": 2}]
    s1 = _json_array_element_span(text, "relations", 1)
    out2 = json.loads(_splice_element(text, s1, None))
    assert out2["relations"] == [{"i": 1}]


# --- write: plan/apply отказы --------------------------------------------------

def test_plan_undo_file_missing(tmp_path):
    try:
        plan_undo_relation(tmp_path, "records/nope.json", "/relations/0")
        assert False
    except TodocError as exc:
        assert exc.code == "edit.file_missing"


def test_apply_undo_file_missing_and_no_spans(tmp_path):
    try:
        apply_undo_relation(tmp_path, "records/nope.json", "/relations/0", None)
        assert False
    except TodocError as exc:
        assert exc.code == "edit.file_missing"
    target = tmp_path / "records/documents/a.json"
    target.parent.mkdir(parents=True)
    target.write_text('{"record_id": "document:a", "title": "T"}', encoding="utf-8")
    try:
        apply_undo_relation(tmp_path, "records/documents/a.json", "/relations/0", None)
        assert False
    except TodocError as exc:
        assert exc.code == "edit.relation_missing"


def test_apply_undo_without_history_still_writes(tmp_path):
    target = tmp_path / "records/documents/a.json"
    target.parent.mkdir(parents=True)
    target.write_text('{"record_id": "document:a", "relations": [{"i": 1}], "title": "T"}',
                      encoding="utf-8")
    new_hash = apply_undo_relation(tmp_path, "records/documents/a.json", "/relations/0", None)
    data = json.loads(target.read_text(encoding="utf-8"))
    assert data["relations"] == [] and new_hash == file_hash(target)


# --- cli: отказы и текст-рендер -------------------------------------------------

def test_cli_undo_unknown_record(tmp_path):
    runner = CliRunner()
    runner.invoke(cli, ["init", "--apply", "--root", str(tmp_path), "--no-input"])
    r = runner.invoke(cli, ["records", "undo-relation", "--root", str(tmp_path),
                            "--id", "document:ghost", "--pointer", "/relations/0"])
    assert isinstance(r.exception, TodocError) and r.exception.code == "records.not_found"


def test_cli_tree_text_truncation(tmp_path):
    runner = CliRunner()
    runner.invoke(cli, ["init", "--apply", "--root", str(tmp_path), "--no-input"])
    rec = {"record_id": "document:a", "entity_type": "document", "title": "A",
           "relations": [{"type_id": "supports", "target": {"kind": "record", "id": "document:b"}},
                          {"type_id": "supports", "target": {"kind": "record", "id": "document:c"}}]}
    for rid in ("a", "b", "c"):
        data = dict(rec, record_id=f"document:{rid}", title=rid.upper(),
                    relations=rec["relations"] if rid == "a" else [])
        p = tmp_path / f"records/documents/{rid}.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    runner.invoke(cli, ["index", "rebuild", "--apply", "--root", str(tmp_path)])
    out = runner.invoke(cli, ["relations", "tree", "--root", str(tmp_path),
                              "--from", "document:a", "--depth", "1", "--limit", "1",
                              "--output", "markdown"]).output
    assert "обрезано" in out and "лимит рёбер" in out


def test_graph_keeps_parallel_mentions():
    second = dict(MENTION_A)  # тот же md-корень, та же цель
    edges = graph_neighbors([], "notes/b.md", mentions=[MENTION_A, second])
    assert len(edges) == 2  # Two source occurrences survive one visited target.


def test_check_targets_anchor_reread_success(tmp_path):
    # цель валидна, но в parsed_docs её нет — перечитывается и якорь находится
    (tmp_path / "notes").mkdir()
    (tmp_path / "notes/a.md").write_text("---\ntitle: A\n---\n\n# A\n\n## Ок\n\nтекст.\n",
                                        encoding="utf-8")
    src = tmp_path / "notes/b.md"
    src.write_text("---\ntitle: B\n---\n\n# B\n\nдвойное [[a#ок]]\n", encoding="utf-8")
    scanned = [_scanned(tmp_path, "notes/a.md"), _scanned(tmp_path, "notes/b.md")]
    diags = _check_link_targets("d", scanned, {"notes/b.md": _md_doc(src)}, [],
                                {x.rel_path for x in scanned})
    assert diags == []
