import json as _jsonlib
from pathlib import Path

from todoc.application.folder_config import load_folder_configs, score_folder_configs


def _cfg(root: Path, rel: str, body: str) -> None:
    d = root / rel
    d.mkdir(parents=True, exist_ok=True)
    (d / ".config.json").write_text(body, encoding="utf-8")


def test_parse_ok_and_alias_normalization(tmp_path):
    _cfg(tmp_path, "ideas/repair", '{"schema_version": 1, "title": "Ремонт", '
         '"aliases": "стройка| ремонт |ванна||стройка", "order": 10}')
    cfgs, diags = load_folder_configs(tmp_path)
    assert cfgs["ideas/repair"].title == "Ремонт"
    assert cfgs["ideas/repair"].aliases == ["стройка", "ремонт", "ванна"]
    assert cfgs["ideas/repair"].order == 10
    # дубликат alias — warning, конфиг остаётся рабочим
    assert [d["code"] for d in diags] == ["folder.config.duplicate_alias"]
    assert diags[0]["severity"] == "warning"


def test_missing_config_is_ok(tmp_path):
    (tmp_path / "plain").mkdir()
    cfgs, diags = load_folder_configs(tmp_path)
    assert cfgs == {} and diags == []


def test_unknown_field_ignored_but_reported(tmp_path):
    """Сценарий идеи: unknown-поле игнорируется, конфиг работает; validate репортует."""
    _cfg(tmp_path, "broken", '{"schema_version": 1, "title": "X", "color": "red"}')
    cfgs, diags = load_folder_configs(tmp_path)
    assert cfgs["broken"].title == "X"  # fail-open: поле отброшено, конфиг работает
    assert {d["code"] for d in diags} == {"folder.config.unknown_field"}
    assert diags[0]["location"].get("line") == 1


def test_invalid_json_excluded_with_location(tmp_path):
    _cfg(tmp_path, "broken", '{"schema_version": 1, "title": }')
    cfgs, diags = load_folder_configs(tmp_path)
    assert cfgs == {}
    assert {d["code"] for d in diags} == {"folder.config.invalid_json"}
    assert "line" in diags[0]["location"]


def test_field_limits_and_types(tmp_path):
    _cfg(tmp_path, "a", '{"schema_version": 1, "title": ""}')                              # пустой title
    _cfg(tmp_path, "b", '{"schema_version": 1, "title": "b", "order": "высокий"}')         # order не int
    _cfg(tmp_path, "c", '{"schema_version": 1, "title": "c", "aliases": "ok|' + "x" * 90 + '"}')
    _cfg(tmp_path, "d", '{"schema_version": 1, "title": "d", "tags": ["ok", 5]}')
    cfgs, diags = load_folder_configs(tmp_path)
    assert cfgs == {}
    codes = {d["code"] for d in diags}
    assert {"folder.config.bad_type", "folder.config.bad_order", "folder.config.bad_alias"} <= codes


def test_alias_collision_across_folders(tmp_path):
    from todoc.application.folder_config import validate_folder_configs
    _cfg(tmp_path, "one", '{"schema_version": 1, "title": "Один", "aliases": "ремонт"}')
    _cfg(tmp_path, "two", '{"schema_version": 1, "title": "Два", "aliases": "Ремонт"}')
    diags = validate_folder_configs(tmp_path)
    assert [d["code"] for d in diags] == ["folder.config.alias_collision"]
    assert diags[0]["severity"] == "warning"


def test_score_exact_alias_and_threshold(tmp_path):
    _cfg(tmp_path, "ideas/repair", '{"schema_version": 1, "title": "Ремонт", "aliases": "ремонт|ванна"}')
    _cfg(tmp_path, "misc", '{"schema_version": 1, "title": "Разное"}')
    cfgs, _ = load_folder_configs(tmp_path)
    cands, discarded = score_folder_configs(cfgs, "нужно сохранить идею про ремонт ванной")
    assert cands[0]["path"] == "ideas/repair" and cands[0]["score"] >= 0.8
    assert "exact alias «ремонт»" in cands[0]["reason"]
    assert any(d["path"] == "misc" for d in discarded)
    assert all(d["score"] < 0.25 for d in discarded)


def test_score_tie_break_order_then_path(tmp_path):
    _cfg(tmp_path, "b/x", '{"schema_version": 1, "title": "Одинаково", "order": 2}')
    _cfg(tmp_path, "a/y", '{"schema_version": 1, "title": "Одинаково 2", "order": 1}')
    cfgs, _ = load_folder_configs(tmp_path)
    cands, _ = score_folder_configs(cfgs, "одинаково")
    assert [c["path"] for c in cands] == ["a/y", "b/x"]  # меньший order выше при равном score


def test_config_excluded_from_index_and_search(tmp_path):
    """Служебный файл: .config.json не попадает в индекс документов и поиск."""
    from click.testing import CliRunner

    from todoc.cli import cli
    from todoc.errors import TodocError

    def _run(runner, args):
        result = runner.invoke(cli, args)
        if isinstance(result.exception, TodocError):
            result.exit_code = result.exception.exit_code
        return result

    runner = CliRunner()
    assert _run(runner, ["init", "--apply", "--root", str(tmp_path)]).exit_code == 0
    (tmp_path / "notes").mkdir()
    (tmp_path / "notes/.config.json").write_text(
        '{"schema_version": 1, "title": "Уникальный-маркер-конфига"}', encoding="utf-8")
    (tmp_path / "notes/readme.md").write_text("---\ntitle: \"Заметки\"\n---\n\n# Заметки\n", encoding="utf-8")
    assert _run(runner, ["index", "rebuild", "--apply", "--root", str(tmp_path)]).exit_code == 0
    r = _run(runner, ["docs", "search", "--root", str(tmp_path), "--query", "Уникальный-маркер-конфига"])
    assert r.exit_code == 0, r.output
    assert _jsonlib.loads(r.output)["data"]["result"]["items"] == []


def test_non_utf8_and_non_object_configs(tmp_path):
    """Битые носители: не-UTF-8 и JSON не-объект — invalid_json, конфиг исключён."""
    d = tmp_path / "a"
    d.mkdir(parents=True)
    (d / ".config.json").write_bytes(b"\xff\xfe\x00\xff")
    d2 = tmp_path / "b"
    d2.mkdir()
    (d2 / ".config.json").write_text("[1, 2]", encoding="utf-8")
    cfgs, diags = load_folder_configs(tmp_path)
    assert cfgs == {}
    codes = [x["code"] for x in diags]
    assert codes.count("folder.config.invalid_json") == 2
    assert "не читается как UTF-8" in diags[0]["message"] or "не читается как UTF-8" in diags[1]["message"]


def test_schema_version_and_field_types_pretty_printed(tmp_path):
    """Многострочный конфиг: schema_version != 1, aliases не строка, длинные description/icon/lang."""
    body = """{
  "schema_version": 2,
  "title": "Папка",
  "aliases": ["не", "строка"],
  "description": "д" * 1,
  "order": 1
}
"""
    d = tmp_path / "a"
    d.mkdir(parents=True)
    (d / ".config.json").write_text(
        '{\n  "schema_version": 2,\n  "title": "Папка",\n  "aliases": ["не", "строка"],\n'
        + '  "description": "' + "д" * 501 + '",\n  "icon": "' + "и" * 51 + '",\n'
        + '  "lang": "' + "л" * 11 + '",\n  "order": 1\n}\n', encoding="utf-8")
    cfgs, diags = load_folder_configs(tmp_path)
    assert cfgs == {}
    codes = [x["code"] for x in diags]
    assert codes.count("folder.config.bad_type") == 5  # schema_version, aliases, description, icon, lang
    assert any("schema_version" in x["message"] for x in diags)
    # многострочный текст: локация ключа на своей строке (loop continue в _key_line)
    lang_diag = [x for x in diags if "lang" in x["message"]][0]
    assert lang_diag["location"]["line"] == 7


def test_bad_order_key_line_missing(tmp_path):
    """Ключ, записанный unicode-escape: ошибка order ловится, литерал «order» в тексте нет → location без line."""
    d = tmp_path / "a"
    d.mkdir(parents=True)
    (d / ".config.json").write_text(
        '{"schema_version": 1, "title": "Папка", "\\u006frder": true}', encoding="utf-8")
    cfgs, diags = load_folder_configs(tmp_path)
    assert cfgs == {}
    assert [x["code"] for x in diags] == ["folder.config.bad_order"]
    # BUG-010: escape-ключ "\\u006frder" теперь находится fallback-поиском
    assert diags[0]["location"] == {"line": 1}


def test_score_alias_words_reason(tmp_path):
    """Многословный alias без точного совпадения: слово запроса даёт 0.3 и reason «words: … (aliases)»."""
    _cfg(tmp_path, "design/bath",
         '{"schema_version": 1, "title": "Проекты", "aliases": "дизайн ванны", "order": 5}')
    _cfg(tmp_path, "misc/other",
         '{"schema_version": 1, "title": "Сантехника", "aliases": "ванны"}')
    cfgs, _ = load_folder_configs(tmp_path)
    cands, _disc = score_folder_configs(cfgs, "ванны дизайн")
    assert [c["path"] for c in cands] == ["misc/other", "design/bath"]
    assert cands[0]["score"] == 1.0  # точный alias «ванны» (1.0 + слово 0.3 → max=1.3, нормировка к 1.0)
    assert cands[1]["score"] == round(0.6 / 1.3, 4)  # два слова alias-а (0.3+0.3) без точного совпадения
    assert "words: дизайн, ванны (aliases)" in cands[1]["reason"]  # порядок — по токенам alias


def test_folders_under_edge_cases(tmp_path, monkeypatch):
    """Не-каталог → пусто; OSError при обходе — ветка пропускается, остальное читается."""
    import os as _os

    from todoc.application import folder_config as fc

    assert fc.load_folder_configs(tmp_path / "нет-такой") == ({}, [])

    locked = tmp_path / "locked"
    locked.mkdir()
    good = tmp_path / "good"
    good.mkdir()
    (good / ".config.json").write_text('{"schema_version": 1, "title": "Гуд"}', encoding="utf-8")
    real = _os.scandir

    def flaky(path, *args, **kwargs):
        if str(path).endswith("locked"):
            raise OSError("заперто")
        return real(path, *args, **kwargs)

    monkeypatch.setattr(fc.os, "scandir", flaky)
    cfgs, diags = fc.load_folder_configs(tmp_path)
    assert list(cfgs) == ["good"] and diags == []
