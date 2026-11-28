# tests/cli/test_cli_docs_suggest.py — house-паттерн (Задача 3)
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


def _demo_vault(tmp_path):
    runner = CliRunner()
    assert _run(runner, ["init", "--apply", "--root", str(tmp_path)]).exit_code == 0
    for rel, body in [
        ("ideas/repair", '{"schema_version": 1, "title": "Ремонт и стройка", '
                         '"aliases": "ремонт|ванна|дизайн ванны", '
                         '"description": "Идеи и скилы по ремонту.", "order": 10}'),
        ("ideas/home", '{"schema_version": 1, "title": "Дом и быт", "order": 20}'),
        ("work", '{"schema_version": 1, "title": "Рабочие заметки", "order": 1}'),
    ]:
        d = tmp_path / rel
        d.mkdir(parents=True)
        (d / ".config.json").write_text(body, encoding="utf-8")


def test_suggest_exact_alias_top_with_reason(tmp_path):
    runner = CliRunner()
    _demo_vault(tmp_path)
    d = _json(_run(runner, ["docs", "suggest", "--root", str(tmp_path),
                            "--query", "нужно сохранить идею про дизайн ванны"]))["data"]
    assert d["result"]["items"][0]["path"] == "ideas/repair"
    assert d["result"]["items"][0]["score"] >= 0.8
    assert "exact alias «дизайн ванны»" in d["result"]["items"][0]["reason"]
    assert d["meta"]["threshold"] == 0.25
    assert any(x["path"] == "ideas/home" for x in d["result"]["discarded"])
    assert d["result"]["items"][0]["order"] == 10


def test_suggest_miss_returns_all_discarded(tmp_path):
    runner = CliRunner()
    _demo_vault(tmp_path)
    d = _json(_run(runner, ["docs", "suggest", "--root", str(tmp_path),
                            "--query", "космический лифт"]))["data"]
    assert d["result"]["items"] == []
    assert len(d["result"]["discarded"]) == 3


def test_suggest_deterministic_byte_for_byte(tmp_path):
    runner = CliRunner()
    _demo_vault(tmp_path)
    args = ["docs", "suggest", "--root", str(tmp_path), "--query", "ремонт"]
    a = _run(runner, args).output
    b = _run(runner, args).output
    assert a == b


def test_suggest_empty_query_usage_error(tmp_path):
    runner = CliRunner()
    _demo_vault(tmp_path)
    r = _run(runner, ["docs", "suggest", "--root", str(tmp_path), "--query", "  "])
    assert r.exit_code != 0
    assert r.exception.code == "usage.error"
