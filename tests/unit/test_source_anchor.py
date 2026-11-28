# tests/unit/test_source_anchor.py — план entity-catalog З9 (T9):
# source_anchor у записи-с ключом source_path — якорь обязан существовать в витрине.
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


def _codes(runner, tmp_path):
    r = _run(runner, ["validate", "--root", str(tmp_path), "--all"])
    return [_d["code"] for _d in _json(r)["diagnostics"]], r


def test_source_anchor_valid_and_missing(tmp_path):
    runner = CliRunner()
    assert _run(runner, ["init", "--apply", "--root", str(tmp_path), "--no-input"]).exit_code == 0
    vitrine = tmp_path / "glossary/envelope.md"
    vitrine.parent.mkdir(parents=True)
    vitrine.write_text("---\ntitle: Конверт\n---\n\n# Конверт\n\n## Связи\n\nтекст.\n",
                       encoding="utf-8")
    rec = tmp_path / "records/documents/a.json"
    rec.parent.mkdir(parents=True)
    rec.write_text(json.dumps({
        "record_id": "document:a", "entity_type": "document", "title": "Т",
        "source_path": "glossary/envelope.md", "source_anchor": "связи", "relations": [],
    }, ensure_ascii=False), encoding="utf-8")
    codes, _ = _codes(runner, tmp_path)
    assert "markdown.anchor_not_found" not in codes, codes

    bad = tmp_path / "records/documents/b.json"
    bad.write_text(json.dumps({
        "record_id": "document:b", "entity_type": "document", "title": "Т2",
        "source_path": "glossary/envelope.md", "source_anchor": "нет-такого", "relations": [],
    }, ensure_ascii=False), encoding="utf-8")
    codes, _ = _codes(runner, tmp_path)
    assert "markdown.anchor_not_found" in codes, codes


def test_source_anchor_without_vitrine_is_defect(tmp_path):
    runner = CliRunner()
    assert _run(runner, ["init", "--apply", "--root", str(tmp_path), "--no-input"]).exit_code == 0
    rec = tmp_path / "records/documents/a.json"
    rec.parent.mkdir(parents=True)
    rec.write_text(json.dumps({
        "record_id": "document:a", "entity_type": "document", "title": "Т",
        "source_path": "glossary/ghost.md", "source_anchor": "х", "relations": [],
    }, ensure_ascii=False), encoding="utf-8")
    codes, _ = _codes(runner, tmp_path)
    assert "markdown.anchor_not_found" in codes, codes


def test_source_anchor_null_or_absent_untouched(tmp_path):
    runner = CliRunner()
    assert _run(runner, ["init", "--apply", "--root", str(tmp_path), "--no-input"]).exit_code == 0
    rec = tmp_path / "records/documents/a.json"
    rec.parent.mkdir(parents=True)
    rec.write_text(json.dumps({
        "record_id": "document:a", "entity_type": "document", "title": "Т",
        "source_path": "glossary/ghost.md", "source_anchor": None, "relations": [],
    }, ensure_ascii=False), encoding="utf-8")
    codes, _ = _codes(runner, tmp_path)
    assert "markdown.anchor_not_found" not in codes, codes


def test_source_anchor_unreadable_vitrine_skipped(tmp_path):
    runner = CliRunner()
    assert _run(runner, ["init", "--apply", "--root", str(tmp_path), "--no-input"]).exit_code == 0
    vitrine = tmp_path / "glossary/envelope.md"
    vitrine.parent.mkdir(parents=True)
    vitrine.write_bytes(b"\xff\xfe not utf-8")
    rec = tmp_path / "records/documents/a.json"
    rec.parent.mkdir(parents=True)
    rec.write_text(json.dumps({
        "record_id": "document:a", "entity_type": "document", "title": "Т",
        "source_path": "glossary/envelope.md", "source_anchor": "связи", "relations": [],
    }, ensure_ascii=False), encoding="utf-8")
    codes, _ = _codes(runner, tmp_path)
    assert "markdown.anchor_not_found" not in codes, codes


def test_source_anchor_non_string_skipped(tmp_path):
    runner = CliRunner()
    assert _run(runner, ["init", "--apply", "--root", str(tmp_path), "--no-input"]).exit_code == 0
    rec = tmp_path / "records/documents/a.json"
    rec.parent.mkdir(parents=True)
    rec.write_text(json.dumps({
        "record_id": "document:a", "entity_type": "document", "title": "Т",
        "source_path": "glossary/envelope.md", "source_anchor": 42, "relations": [],
    }, ensure_ascii=False), encoding="utf-8")
    codes, _ = _codes(runner, tmp_path)
    assert "markdown.anchor_not_found" not in codes, codes
