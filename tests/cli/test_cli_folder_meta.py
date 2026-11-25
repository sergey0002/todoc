# tests/cli/test_cli_folder_meta.py — house-паттерн (Задача 2)
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


def _init(tmp_path):
    _run(CliRunner(), ["init", "--root", str(tmp_path)])


def test_tree_flat_fields_and_absence(tmp_path):
    runner = CliRunner()
    _init(tmp_path)
    (tmp_path / "notes").mkdir()
    (tmp_path / "notes/.config.json").write_text(
        '{"schema_version": 1, "title": "Заметки", "description": "Рабочие записи", "order": 5}',
        encoding="utf-8")
    (tmp_path / "misc").mkdir()  # без конфига
    folders = {f["path"]: f
               for f in _json(_run(runner, ["docs", "tree", "--root", str(tmp_path)]))["data"]["folders"]}
    assert folders["notes"]["title"] == "Заметки" and folders["notes"]["order"] == 5
    assert folders["notes"]["description"] == "Рабочие записи"
    assert folders["misc"]["title"] is None and folders["misc"]["dir_type"]  # прежние поля целы


def test_tree_match_filters_by_score(tmp_path):
    runner = CliRunner()
    _init(tmp_path)
    (tmp_path / "ideas/repair").mkdir(parents=True)
    (tmp_path / "ideas/repair/.config.json").write_text(
        '{"schema_version": 1, "title": "Ремонт", "aliases": "ремонт|ванна"}', encoding="utf-8")
    (tmp_path / "misc").mkdir()
    d = _json(_run(runner, ["docs", "tree", "--root", str(tmp_path), "--match", "ремонт ванной"]))["data"]
    paths = [f["path"] for f in d["folders"]]
    assert "ideas/repair" in paths and "misc" not in paths


def test_explain_path_for_folder_and_document(tmp_path):
    runner = CliRunner()
    _init(tmp_path)
    (tmp_path / "notes").mkdir()
    (tmp_path / "notes/.config.json").write_text(
        '{"schema_version": 1, "title": "Заметки", "order": 5}', encoding="utf-8")
    (tmp_path / "notes/n1.md").write_text("---\ntitle: \"Первая\"\n---\n\n# n1\n", encoding="utf-8")
    _run(runner, ["index", "rebuild", "--root", str(tmp_path)])
    d = _json(_run(runner, ["explain-path", "notes", "--root", str(tmp_path)]))["data"]
    assert d["folder"] is True and d["title"] == "Заметки" and "dir_type" in d
    d2 = _json(_run(runner, ["explain-path", "notes/n1.md", "--root", str(tmp_path)]))["data"]
    assert d2["title"] == "Заметки" and d2["doc_type"]  # документ + поля предка
    bad = _run(runner, ["explain-path", "nope", "--root", str(tmp_path)])
    assert bad.exit_code != 0  # прежняя семантика для несуществующих
