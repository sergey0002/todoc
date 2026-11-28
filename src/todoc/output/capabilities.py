"""Inventory of the public Click command tree."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator

import click

from todoc.errors import TodocError
from todoc.output.envelope import Envelope, emit


@dataclass(frozen=True)
class Parameter:
    name: str
    spellings: tuple[str, ...]
    type_name: str
    required: bool
    multiple: bool
    arity: int
    default: object

    @classmethod
    def from_click(cls, parameter: click.Parameter) -> Parameter:
        return cls(
            parameter.name or "",
            (*parameter.opts, *parameter.secondary_opts),
            parameter.type.name,
            parameter.required,
            parameter.multiple,
            parameter.nargs,
            parameter.default,
        )


@dataclass(frozen=True)
class CommandCapabilities:
    path: tuple[str, ...]
    parameters: tuple[Parameter, ...]
    group: bool


def command_inventory(command: click.Command, path: tuple[str, ...] = ()) -> Iterator[CommandCapabilities]:
    """Describe command spellings, including groups and nested leaves."""
    is_group = isinstance(command, click.Group)
    yield CommandCapabilities(path, tuple(Parameter.from_click(p) for p in command.params), is_group)
    if isinstance(command, click.Group):
        for name, child in sorted(command.commands.items()):
            yield from command_inventory(child, (*path, name))


def group_discovery(group: click.Group, path: str) -> dict:
    """Return a bounded command menu from Click's public command definitions."""
    return {
        "meta": {"command": path, "scope": None},
        "executed": False,
        "result": {
            "commands": [
                {"name": name, "summary": (command.short_help or command.help or "").split("\n", 1)[0]}
                for name, command in sorted(group.commands.items()) if not command.hidden
            ]
        },
    }


def command_preferences(ctx: click.Context) -> dict:
    """Return the inherited preferences visible at this point in the command tree."""
    root = ctx.find_root()
    return {**root.params, **(ctx.obj or {})}


class UnifiedCommand(click.Command):
    """Keep the command and renderer available to the application error boundary."""

    def parse_args(self, ctx: click.Context, args: list[str]) -> list[str]:
        try:
            return super().parse_args(ctx, args)
        except click.MissingParameter:
            output = ctx.params.get("output") if ctx.get_parameter_source("output") is click.core.ParameterSource.COMMANDLINE else None
            output = output or command_preferences(ctx).get("output", "json")
            fields = [Parameter.from_click(item) for item in self.params if not getattr(item, "hidden", False)]
            response = Envelope.result({"command": command_name(ctx), "scope": None}, {
                "summary": (self.short_help or self.help or "").split("\n", 1)[0],
                "parameters": [{"name": item.name, "spellings": item.spellings, "type": item.type_name,
                                "required": item.required, "multiple": item.multiple, "arity": item.arity}
                               for item in fields],
            })
            response.data["executed"] = False
            emit(response, output)
            ctx.exit()

    def invoke(self, ctx: click.Context):
        preferences = command_preferences(ctx)
        if "output" in ctx.params and ctx.get_parameter_source("output") is click.core.ParameterSource.DEFAULT:
            preference = preferences.get("output")
            if preference is not None:
                ctx.params["output"] = preference
        if "no_input" in ctx.params and preferences.get("no_input"):
            ctx.params["no_input"] = True
        try:
            return super().invoke(ctx)
        except TodocError as exc:
            exc.cli_context = ctx
            raise


def command_name(ctx: click.Context) -> str:
    names = []
    current = ctx
    while current.parent is not None:
        names.append(current.info_name or current.command.name or "")
        current = current.parent
    return " ".join(reversed(names))
