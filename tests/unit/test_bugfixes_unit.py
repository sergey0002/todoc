# tests/unit/test_bugfixes.py — регресс-тесты исправлений BUG-009/BUG-010 (unit-уровень)
from todoc.application.folder_config import load_folder_configs, score_folder_configs
from todoc.application.folder_config import _key_line
from todoc.application.validator import _key_location


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
