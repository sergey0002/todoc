#!/usr/bin/env python3
"""Render the public CLI reference from Click's registered commands."""

import argparse
from pathlib import Path

import click

from todoc.cli import cli
from todoc.output.capabilities import command_inventory


REFERENCE = Path(__file__).resolve().parents[1] / "docs/state/cli.md"


def render() -> str:
    inventory = list(command_inventory(cli))
    leaves = sum(not entry.group for entry in inventory)
    sections = [
        "# Полный справочник CLI",
        "",
        f"Справочник сгенерирован из дерева Click. Листовых команд: {leaves}.",
        "",
        "Порядок опций, форматы ответа и примеры описаны в [контракте CLI](03-cli-reference.md).",
        "",
        "## Указатель",
        "",
    ]
    for entry in inventory:
        name = " ".join(entry.path) or "todoc"
        anchor = "-".join(entry.path) or "todoc"
        sections.append(f"- [`{name}`](#{anchor})")
    sections.extend(["", "## Команды", ""])
    for entry in inventory:
        command = cli
        context = click.Context(cli, info_name="todoc", terminal_width=100)
        for part in entry.path:
            command = command.commands[part]
            context = click.Context(command, parent=context, info_name=part)
        name = " ".join(entry.path) or "todoc"
        sections.extend([f"### {name}", "", "```text", command.get_help(context), "```", ""])
    return "\n".join(sections)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Fail if the checked-in reference is stale.")
    args = parser.parse_args()
    reference = render()
    if args.check:
        if REFERENCE.read_text(encoding="utf-8") == reference:
            return 0
        print(f"Outdated CLI reference: {REFERENCE}")
        return 1
    REFERENCE.write_text(reference, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
