from __future__ import annotations

import json
from pathlib import Path
from click.testing import CliRunner

from todoc.cli import cli
from todoc.errors import TodocError


def _run(runner: CliRunner, args: list[str]):
    result = runner.invoke(cli, args)
    if isinstance(result.exception, TodocError):
        result.exit_code = result.exception.exit_code
    return result


def test_cli_sync_direct_edit_dirty_derived_block_out_and_conflicts(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()
    kb = tmp_path / "kb"
    assert _run(runner, ["init", "--root", str(kb)]).exit_code == 0
    res_new = _run(runner, ["docs", "new", "--root", str(kb), "--type", "note",
                            "--title", "Заметка", "--path", "notes/n1.md"])
    assert res_new.exit_code == 0

    note = kb / "notes" / "n1.md"
    lines = [ln for ln in note.read_text(encoding="utf-8").splitlines() if "<!--" not in ln]
    lines.append("Содержательный абзац.")
    note.write_text("\n".join(lines) + "\n", encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    # 1. Путь относительно CWD (kb/notes/n1.md) + запись ответа в --out внутри DATA_ROOT
    res_sync = _run(runner, ["sync", "--root", "kb", "kb/notes/n1.md"])
    assert res_sync.exit_code == 0, res_sync.output
    payload = json.loads(res_sync.output)
    assert payload["ok"] is True
    assert payload["data"]["synced"][0]["path"] == "notes/n1.md"
    assert payload["guidance"] is None

    res_out = _run(runner, ["sync", "--root", "kb", "notes/n1.md", "--out", ".todoc/generated/sync.json"])
    assert res_out.exit_code == 0
    assert (kb / ".todoc" / "generated" / "sync.json").is_file()

    # 2. Режим без аргументов (автопоиск грязных файлов) + --output table
    note.write_text(note.read_text(encoding="utf-8") + "\nЕщё строка.\n", encoding="utf-8")
    res_auto = _run(runner, ["sync", "--root", "kb", "--no-history", "--output", "table"])
    assert res_auto.exit_code == 0
    assert "ok: True" in res_auto.output

    # 3. Блокировка рендера с меткой <!-- СГЕНЕРИРОВАНО: (exit 3 + guidance) и обход --allow-derived
    gen_doc = kb / "notes" / "rendered.md"
    gen_doc.write_text(
        '---\nderived_from: ["notes/n1.md@sha256:000"]\n---\n\n<!-- СГЕНЕРИРОВАНО: flow render -->\n\n# Витрина\n\n## Суть\n\nv1\n',
        encoding="utf-8",
    )
    assert _run(runner, ["index", "rebuild", "--root", "kb"]).exit_code == 0
    gen_doc.write_text(gen_doc.read_text(encoding="utf-8").replace("v1", "ручная правка"), encoding="utf-8")

    res_blocked = _run(runner, ["sync", "--root", "kb", "notes/rendered.md"])
    assert res_blocked.exit_code == 3
    blocked_json = json.loads(res_blocked.output)
    assert blocked_json["ok"] is False
    assert blocked_json["guidance"]["code"] == "sync.derived_view_blocked"

    res_allowed = _run(runner, ["sync", "--root", "kb", "notes/rendered.md", "--allow-derived"])
    assert res_allowed.exit_code == 0

    # 4. Коды ошибок: --if-hash (exit 5) и выход за пределы DATA_ROOT (exit 4)
    assert _run(runner, ["sync", "--root", "kb", "notes/n1.md", "--if-hash", "sha256:bad"]).exit_code == 5
    assert _run(runner, ["sync", "--root", "kb", "../outside.md"]).exit_code == 4
