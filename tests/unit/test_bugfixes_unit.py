# tests/unit/test_bugfixes.py — регресс-тесты исправлений BUG-009/BUG-010 (unit-уровень)
import pytest

from todoc.application.folder_config import load_folder_configs, score_folder_configs
from todoc.application.folder_config import _key_line
from todoc.application.validator import _key_location
from todoc.application.write import apply_edit_ops
from todoc.errors import ValidationError


# --- BUG-009: score_raw в выдаче score_folder_configs --------------------------------

def test_score_raw_exposes_pre_normalization_value(tmp_path):
    """Слабый сигнал при единственном кандидате: score нормирован (1.0), score_raw честен (0.3)."""
    d = tmp_path / "design/bath"
    d.mkdir(parents=True)
    (d / ".config.json").write_text(
        '{"schema_version": 1, "title": "Проекты", "aliases": "дизайн ванны"}', encoding="utf-8")
    cfgs, _ = load_folder_configs(tmp_path)
    cands, _disc = score_folder_configs(cfgs, "ванны")
    assert len(cands) == 1
    assert cands[0]["score"] == 1.0  # нормировка к max (текущая семантика сохранена)
    assert cands[0]["score_raw"] == 0.3  # raw: слово alias без точного совпадения


def test_score_raw_on_exact_alias_and_discarded(tmp_path):
    d = tmp_path / "ideas/repair"
    d.mkdir(parents=True)
    (d / ".config.json").write_text(
        '{"schema_version": 1, "title": "Ремонт", "aliases": "ремонт|ванна"}', encoding="utf-8")
    d2 = tmp_path / "misc"
    d2.mkdir()
    (d2 / ".config.json").write_text('{"schema_version": 1, "title": "Разное"}', encoding="utf-8")
    cfgs, _ = load_folder_configs(tmp_path)
    cands, discarded = score_folder_configs(cfgs, "нужно сохранить идею про ремонт ванной")
    assert cands[0]["score_raw"] == 1.5  # exact «ремонт» 1.0 + его слово 0.3 + title-токен 0.2
    assert discarded and all("score_raw" in x for x in discarded)


# --- BUG-010: локация ключа, записанного unicode-escape ------------------------------

def test_key_line_finds_unicode_escaped_key():
    assert _key_line('{"\\u006frder": true}', "order") == 1


def test_key_line_missing_key_still_none():
    assert _key_line('{"a": 1}', "order") is None


def test_validator_key_location_finds_unicode_escaped_key():
    assert _key_location('{"\\u006frder": true}', "order") == {"line": 1, "column": 2}


def test_validator_key_location_missing_key_empty():
    assert _key_location('{"a": 1}', "order") == {}


def test_folder_config_bad_order_escaped_key_has_location(tmp_path):
    """Диагностика bad_order по ключу "\\u006frder" несёт строку, а не пустую локацию."""
    d = tmp_path / "a"
    d.mkdir()
    (d / ".config.json").write_text(
        '{"schema_version": 1, "title": "Папка", "\\u006frder": true}', encoding="utf-8")
    _cfgs, diags = load_folder_configs(tmp_path)
    assert [x["code"] for x in diags] == ["folder.config.bad_order"]
    assert diags[0]["location"] == {"line": 1}


# --- BUG-004: apply_edit_ops — вставка/удаление строк --------------------------------

def _w(tmp_path, body="a\nb\nc\n"):
    (tmp_path / "doc.md").write_text(body, encoding="utf-8")
    return tmp_path / "doc.md"


def test_edit_ops_insert_after_string_and_list(tmp_path):
    f = _w(tmp_path)
    apply_edit_ops(tmp_path, "doc.md", [
        {"op": "insert_after", "line": 1, "text": "x"},
        {"op": "insert_after", "line": 0, "text": ["верх1", "верх2"]},
        {"op": "insert_after", "line": 6, "text": "конец"},  # line == len(lines) — в конец
    ])
    assert f.read_text(encoding="utf-8") == "верх1\nверх2\na\nx\nb\nc\nконец\n"


def test_edit_ops_delete_single_and_range(tmp_path):
    f = _w(tmp_path, "a\nb\nc\nd\ne\n")
    apply_edit_ops(tmp_path, "doc.md", [
        {"op": "delete", "line": 2},            # a,b,c,d,e → a,c,d,e
        {"op": "delete", "line": 1, "to": 2},   # 1–2 = a,c → остаются d,e
    ])
    assert f.read_text(encoding="utf-8") == "d\ne\n"


def test_edit_ops_replace_backward_compatible(tmp_path):
    f = _w(tmp_path)
    apply_edit_ops(tmp_path, "doc.md", [{"line": 2, "text": "B"}])
    assert f.read_text(encoding="utf-8") == "a\nB\nc\n"


def test_edit_ops_unknown_op_rejected(tmp_path):
    _w(tmp_path)
    with pytest.raises(ValidationError) as e:
        apply_edit_ops(tmp_path, "doc.md", [{"op": "append_magic", "line": 1, "text": "x"}])
    assert e.value.code == "edit.op_unknown"


def test_edit_ops_insert_out_of_range_rejected(tmp_path):
    _w(tmp_path)
    with pytest.raises(ValidationError) as e:
        apply_edit_ops(tmp_path, "doc.md", [{"op": "insert_after", "line": 99, "text": "x"}])
    assert e.value.code == "edit.line_out_of_range"
