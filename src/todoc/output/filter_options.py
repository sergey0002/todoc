"""Map dynamic source-attribute flags to a declared, repeatable Click option."""

import re

import click

from todoc.output.capabilities import UnifiedCommand


class AttributeFilterCommand(UnifiedCommand):
    def parse_args(self, ctx: click.Context, args: list[str]) -> list[str]:
        expanded = []
        index = 0
        while index < len(args):
            arg = args[index]
            if arg == "--":
                expanded.extend(args[index:])
                break
            if not arg.startswith("--attr-"):
                # An ordinary option may take a value beginning with --attr-.
                # Preserve attached values and skip the operand of known options.
                expanded.append(arg)
                for parameter in self.params:
                    if arg in parameter.opts and isinstance(parameter, click.Option) and not parameter.is_flag:
                        expanded.extend(args[index + 1:index + 1 + parameter.nargs])
                        index += parameter.nargs
                        break
                index += 1
                continue
            name, equals, value = arg.removeprefix("--attr-").partition("=")
            if not re.fullmatch(r"[\w][\w.-]*", name):
                raise click.BadOptionUsage(arg, f"Invalid attribute name: {name!r}.", ctx=ctx)
            if not equals:
                index += 1
                if index >= len(args) or args[index].startswith("--"):
                    raise click.BadOptionUsage(arg, f"{arg} needs a value.", ctx=ctx)
                value = args[index]
            expanded.extend(("--attribute", name, value))
            index += 1
        return super().parse_args(ctx, expanded)
