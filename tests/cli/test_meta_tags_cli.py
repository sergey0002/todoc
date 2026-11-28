# tests/cli/test_meta_tags_cli.py — план doc-tags: Задача 2 (CLI --tag и meta-поля docs read)
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


def _doc(runner, tmp_path, rel, body):
    path = tmp_path / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    r = _run(runner, ["index", "rebuild", "--apply", "--root", str(tmp_path)])
    assert r.exit_code == 0, r.output


def _setup_two_docs(runner, tmp_path):
    """Оба документа совпадают по телу («search»); разница — тег: буст решает порядок."""
    _doc(runner, tmp_path, "notes/tagged.md",
         "---\ntitle: Заметка о креденшалах\ntags: [search]\n---\n\n# Заметка о креденшалах\n\n"
         "текст про search и refresh token.\n")
    _doc(runner, tmp_path, "notes/plain.md",
         "---\ntitle: Заметка о креденшалах\n---\n\n# Заметка о креденшалах\n\n"
         "текст про search и refresh token.\n")


def test_tag_filter_cli(tmp_path):
    runner = CliRunner()
    _init(runner, tmp_path)
    _setup_two_docs(runner, tmp_path)
    r = _run(runner, ["docs", "search", "--root", str(tmp_path), "--query", "refresh", "--tag", "search"])
    hits = _json(r)["data"]["result"]["items"]
    assert [h["path"] for h in hits] == ["notes/tagged.md"]


def test_tag_filter_empty_when_no_match(tmp_path):
    runner = CliRunner()
    _init(runner, tmp_path)
    _setup_two_docs(runner, tmp_path)
    r = _run(runner, ["docs", "search", "--root", str(tmp_path), "--query", "refresh", "--tag", "нет-такого"])
    assert _json(r)["data"]["result"]["items"] == []


def test_read_output_carries_meta_fields(tmp_path):
    runner = CliRunner()
    _init(runner, tmp_path)
    _doc(runner, tmp_path, "notes/meta.md",
         "---\nid: doc:notes/meta.md\ntitle: T\ncreated: 2026-11-25\nupdated: 2026-11-26\n"
         "tags: [a1, b2]\nrelated: [\"[[x]]\"]\n---\n\n# T\n\nтело.\n")
    r = _run(runner, ["docs", "read", "--root", str(tmp_path), "--id", "doc:notes/meta.md"])
    d = _json(r)["data"]["result"]
    assert d["tags"] == ["a1", "b2"]
    assert d["updated"] == "2026-11-26"
    assert d["related"] == ["[[x]]"]
    r2 = _run(runner, ["docs", "read", "--root", str(tmp_path), "--id", "doc:notes/plain-x.md"])
    assert r2.exit_code != 0  # не существует — docs.not_found
