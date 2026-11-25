"""Сквозной контракт CLI: K47 и K48 по всему перечню команд.

План (docs/plan/history-and-changes.md, §20) требует: «K47 и K48 должны быть
параметризованы по перечню команд, а не написаны на одну: иначе команда, добавленная
позже, пройдёт мимо проверки». Поэтому список команд здесь не зашит literально, а
вычитывается из самого CLI — новая команда попадает в проверку автоматически.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import click
import pytest

from todoc.cli import cli

SRC = str(Path(__file__).resolve().parents[2] / "src")


def _leaf_commands() -> list[tuple[str, ...]]:
    """Все листовые команды CLI: («docs», «edit»), («change», «apply»), («status»,)…"""
    out: list[tuple[str, ...]] = []
    for name in sorted(cli.commands):
        cmd = cli.commands[name]
        if isinstance(cmd, click.Group):
            for sub in sorted(cmd.commands):
                out.append((name, sub))
        else:
            out.append((name,))
    return out


LEAVES = _leaf_commands()


def _run_no_input(root: Path, argv: tuple[str, ...]) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["PYTHONPATH"] = SRC
    return subprocess.run(
        [sys.executable, "-m", "todoc", "--root", str(root), "--output", "json",
         "--no-input", *argv],
        capture_output=True, text=True, env=env, timeout=120,
        stdin=subprocess.DEVNULL,  # K47: TTY нет вовсе
    )


def test_every_leaf_command_is_covered():
    """Страховка от молчаливого сужения списка: команд не меньше, чем в CLI."""
    expected = sum(len(c.commands) if isinstance(c, click.Group) else 1
                   for c in cli.commands.values())
    assert len(LEAVES) == expected
    assert len(LEAVES) >= 45, f"слишком мало команд: {len(LEAVES)}"


@pytest.mark.parametrize("argv", LEAVES)
def test_k47_no_command_needs_a_tty(root, argv):
    """K47: при --no-input и закрытом stdin команда завершается, а не ждёт ввода."""
    result = _run_no_input(root, argv)
    # Главное — процесс вернулся (timeout убил бы его) и не оставил трейсбек ожидания.
    assert result.returncode is not None
    assert "Traceback (most recent call last)" not in result.stderr, result.stderr[-800:]


@pytest.mark.parametrize("argv", LEAVES)
def test_k48_failure_is_an_envelope(root, argv):
    """K48: неуспех — это конверт ok:false в stdout и ненулевой exit code."""
    result = _run_no_input(root, argv)
    if result.returncode == 0:
        pytest.skip("команда завершилась успешно — проверять отказ не на чем")
    assert result.stdout.strip(), f"при ошибке stdout пуст: stderr={result.stderr[-400:]}"
    envelope = json.loads(result.stdout)
    assert envelope["ok"] is False
    # Контракт конверта: код и сообщение живут в диагностике, а не на верхнем уровне.
    diags = envelope["diagnostics"]
    assert diags, "ok:false без диагностики необъясним для агента"
    assert diags[0]["code"] and diags[0]["message"]
    assert diags[0]["severity"] == "error"
    assert "Traceback (most recent call last)" not in result.stderr, result.stderr[-800:]
