from pathlib import Path

from todoc.adapters.filesystem.scanner import scan_dataset
from todoc.application.validator import validate_dataset, validate_relations
from todoc.config import load_dataset, load_rules


def _validate(root: Path):
    dataset = load_dataset(root)
    dir_rules, doc_rules = load_rules(root, dataset)
    _folders, files = scan_dataset(root)
    return validate_dataset(root, dataset, files, dir_rules, doc_rules)


def test_validate_clean(root, sample_md, sample_csv, sample_record):
    diags, info = _validate(root)
    codes = [d.code for d in diags]
    assert "markdown.link.target_missing" not in codes
    assert info["notes/design.md"]["doc_type"] == "unknown"
    assert info["notes/design.md"]["title"] == "Design"


def test_validate_broken_link(root, tmp_path):
    path = root / "notes" / "broken.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# Broken\n\nSee [missing](../ops/missing.md).\n", encoding="utf-8")
    diags, _info = _validate(root)
    broken = [d for d in diags if d.code == "markdown.link.target_missing"]
    assert len(broken) == 1
    assert broken[0].location["line"] == 3


def test_validate_broken_link_with_candidate_fix(root):
    (root / "ops").mkdir(parents=True, exist_ok=True)
    (root / "ops" / "runbook.md").write_text("# Runbook\n", encoding="utf-8")
    path = root / "notes" / "broken.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# Broken\n\nSee [runbook](../ops/runbok.md).\n", encoding="utf-8")
    diags, _info = _validate(root)
    broken = [d for d in diags if d.code == "markdown.link.target_missing"]
    # Relative to notes/, not to the dataset root: the parser resolves the link
    # against the file that contains it.
    assert broken[0].suggested_fixes[0].replacement == "../ops/runbook.md"


def test_validate_csv_errors(root):
    path = root / "data" / "bad.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("a,a\n1\n", encoding="utf-8")
    diags, _info = _validate(root)
    codes = [d.code for d in diags]
    assert "csv.duplicate_header" in codes
    assert "csv.wrong_width" in codes


def test_validate_json_errors(root):
    path = root / "data" / "bad.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{"a": 1, "a": 2}', encoding="utf-8")
    diags, _info = _validate(root)
    assert any(d.code == "json.duplicate_key" for d in diags)


def test_validate_duplicate_record_id(root, sample_record):
    dup = root / "records" / "workouts" / "w2.json"
    dup.write_text('{"record_id": "workout:2026-11-24-sergei-01", "entity_type": "workout"}', encoding="utf-8")
    diags, _info = _validate(root)
    assert any(d.code == "record.duplicate_id" for d in diags)


def test_validate_missing_entity_type(root):
    path = root / "records" / "x.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{"record_id": "x:1"}', encoding="utf-8")
    diags, _info = _validate(root)
    assert any(d.code == "record.missing_entity_type" for d in diags)


def test_validate_relations_dangling():
    records = [{"record_id": "w:1", "path": "w.json", "data": {"relations": [{"type_id": "performed_by", "target": {"id": "person:ghost"}}]}}]
    diags = validate_relations("ds", records, {"performed_by"})
    assert len(diags) == 1
    assert diags[0].code == "relation.dangling_target"


def test_validate_relations_ok():
    records = [
        {"record_id": "w:1", "path": "w.json", "data": {"relations": [{"type_id": "performed_by", "target": {"id": "p:1"}}]}},
        {"record_id": "p:1", "path": "p.json", "data": {}},
    ]
    assert validate_relations("ds", records, {"performed_by"}) == []


def test_validate_glossary_front_matter(root):
    path = root / "docs" / "glossary.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("---\ndoc_type: glossary-entry\n---\n\n# Term\n", encoding="utf-8")
    _diags, info = _validate(root)
    assert info["docs/glossary.md"]["doc_type"] == "glossary-entry"


# --- P1-8: позиции у диагностик отношений -----------------------------------


def test_pointer_key_takes_last_named_segment():
    from todoc.application.validator import _pointer_key
    assert _pointer_key("/relations/0") == "relations"
    assert _pointer_key("/relations/0/target/id") == "id"
    assert _pointer_key("relations") == "relations"
    # Только числовые сегменты — ключа нет.
    assert _pointer_key("/0/1") == ""
    assert _pointer_key("") == ""


def test_validate_relations_reports_lines_when_texts_given():
    text = ('{\n  "record_id": "a",\n  "relations": [\n'
            '    {"type_id": "loves", "target": {"id": "ghost"}}\n  ]\n}\n')
    records = [{"record_id": "a", "entity_type": "note", "path": "records/a.json",
                "data": {"relations": [{"type_id": "loves", "target": {"id": "ghost"}}]}}]
    diags = validate_relations("ds", records, {"performed_by"}, texts={"records/a.json": text})
    by_code = {d.code: d for d in diags}
    assert set(by_code) == {"relation.unknown_type", "relation.dangling_target"}
    unknown = by_code["relation.unknown_type"]
    assert unknown.location["pointer"] == "/relations/0"
    assert unknown.location["line"] == 3          # строка ключа "relations"
    dangling = by_code["relation.dangling_target"]
    assert dangling.location["pointer"] == "/relations/0/target/id"
    assert dangling.location["line"] == 4          # строка ключа "id"


def test_validate_relations_without_texts_keeps_pointer_only():
    records = [{"record_id": "a", "entity_type": "note", "path": "records/a.json",
                "data": {"relations": [{"type_id": "loves", "target": {"id": "ghost"}}]}}]
    diags = validate_relations("ds", records, {"performed_by"})
    assert all(d.location.get("line") is None for d in diags)
    assert diags[0].location["pointer"] == "/relations/0"


def test_validate_relations_malformed_entries_are_located():
    text = '{\n  "relations": "не список"\n}\n'
    records = [{"record_id": "a", "entity_type": "note", "path": "records/a.json",
                "data": {"relations": "не список"}}]
    diags = validate_relations("ds", records, {"performed_by"}, texts={"records/a.json": text})
    assert [d.code for d in diags] == ["relation.malformed"]
    assert diags[0].location == {"pointer": "/relations", "line": 2, "column": 3}

    text2 = '{\n  "relations": [\n    "не объект"\n  ]\n}\n'
    records2 = [{"record_id": "b", "entity_type": "note", "path": "records/b.json",
                 "data": {"relations": ["не объект"]}}]
    diags2 = validate_relations("ds", records2, {"performed_by"}, texts={"records/b.json": text2})
    assert [d.code for d in diags2] == ["relation.malformed"]
    assert diags2[0].location["pointer"] == "/relations/0"
    assert diags2[0].location["line"] == 2
