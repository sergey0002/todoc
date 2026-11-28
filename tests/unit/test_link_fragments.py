# tests/unit/test_link_fragments.py — план entity-catalog З1 (T7):
# фрагменты wikilink/inline-ссылок, record-цели, JSON Pointer.
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


def _write(runner, tmp_path, rel, body):
    path = tmp_path / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    assert _run(runner, ["index", "rebuild", "--apply", "--root", str(tmp_path)]).exit_code == 0, \
        f"rebuild failed for {rel}"


def _record(tmp_path, rel, record_id):
    path = tmp_path / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "record_id": record_id, "entity_type": "document", "title": "Т",
        "relations": [],
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _diags(runner, tmp_path):
    # диагностики легальны: конверт приходит при любом коде выхода (3 = валидация)
    return _json(_run(runner, ["validate", "--root", str(tmp_path), "--all"]))["diagnostics"]


def _codes(diags):
    return [d["code"] for d in diags]


# --- якоря md-целей -------------------------------------------------------------------

def test_inline_anchor_valid_passes(tmp_path):
    runner = CliRunner()
    _init(runner, tmp_path)
    _write(runner, tmp_path, "notes/a.md",
           "---\ntitle: A\n---\n\n# A\n\n## Целевой раздел\n\nтекст.\n")
    _write(runner, tmp_path, "notes/b.md",
           "---\ntitle: B\n---\n\n# B\n\n[раздел](a.md#целевой-раздел) и [вики](a.md).\n")
    assert _codes(_diags(runner, tmp_path)) == []


def test_inline_anchor_missing(tmp_path):
    runner = CliRunner()
    _init(runner, tmp_path)
    _write(runner, tmp_path, "notes/a.md", "---\ntitle: A\n---\n\n# A\n\n## Раздел\n\nтекст.\n")
    _write(runner, tmp_path, "notes/b.md",
           "---\ntitle: B\n---\n\n# B\n\n[раздел](a.md#нет-такого)\n")
    assert _codes(_diags(runner, tmp_path)) == ["markdown.anchor_not_found"]


def test_wikilink_anchor_cyrillic_valid_and_missing(tmp_path):
    runner = CliRunner()
    _init(runner, tmp_path)
    _write(runner, tmp_path, "notes/a.md", "---\ntitle: A\n---\n\n# A\n\n## Принципы\n\nтекст.\n")
    _write(runner, tmp_path, "notes/b.md",
           "---\ntitle: B\n---\n\n# B\n\nОк: [[a#Принципы]]. Битый: [[a#Секция]]\n")
    diags = _diags(runner, tmp_path)
    assert _codes(diags) == ["markdown.anchor_not_found"]
    assert diags[0]["path"] == "notes/b.md"


def test_anchor_target_not_md_or_missing_file_unchanged(tmp_path):
    runner = CliRunner()
    _init(runner, tmp_path)
    # цель-файл не существует — прежний код markdown.link.target_missing, не новый
    _write(runner, tmp_path, "notes/b.md", "---\ntitle: B\n---\n\n# B\n\n[x](missing.md#сек)\n")
    assert _codes(_diags(runner, tmp_path)) == ["markdown.link.target_missing"]


# --- record-цели ----------------------------------------------------------------------

def test_wikilink_to_record_target_passes(tmp_path):
    runner = CliRunner()
    _init(runner, tmp_path)
    _record(tmp_path, "records/documents/constitution.json", "document:constitution")
    _write(runner, tmp_path, "notes/b.md",
           "---\ntitle: B\n---\n\n# B\n\nСм. [[document:constitution]].\n")
    assert _codes(_diags(runner, tmp_path)) == []


def test_wikilink_to_unknown_record(tmp_path):
    runner = CliRunner()
    _init(runner, tmp_path)
    _write(runner, tmp_path, "notes/b.md", "---\ntitle: B\n---\n\n# B\n\nСм. [[document:no-such]].\n")
    assert _codes(_diags(runner, tmp_path)) == ["markdown.record_not_found"]


def test_record_target_pointer_valid_and_invalid(tmp_path):
    runner = CliRunner()
    _init(runner, tmp_path)
    _record(tmp_path, "records/documents/plan.json", "document:plan")
    _write(runner, tmp_path, "notes/b.md",
           "---\ntitle: B\n---\n\n# B\n\n"
           "Ок: [[document:plan#/title]]. Битый pointer: [[document:plan#/no/such]].\n"
           "Не pointer: [[document:plan#раздел]]\n")
    codes = _codes(_diags(runner, tmp_path))
    assert codes == ["markdown.pointer_invalid", "markdown.pointer_invalid"], codes


def test_inline_link_to_record_target_with_pointer(tmp_path):
    runner = CliRunner()
    _init(runner, tmp_path)
    _record(tmp_path, "records/documents/plan.json", "document:plan")
    _write(runner, tmp_path, "notes/b.md",
           "---\ntitle: B\n---\n\n# B\n\n[поле](document:plan#/title)\n")
    assert _codes(_diags(runner, tmp_path)) == []


def test_fragment_ignores_code_spans(tmp_path):
    runner = CliRunner()
    _init(runner, tmp_path)
    _write(runner, tmp_path, "notes/b.md",
           "---\ntitle: B\n---\n\n# B\n\nСинтаксис в коде: `[[document:no-such]]` и\n"
           "\n    [[document:no-such]]\n")
    assert _codes(_diags(runner, tmp_path)) == []
