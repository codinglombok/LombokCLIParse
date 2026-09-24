"""LombokCLIParse — Lightweight CLI argument parser.

Positional args, flags, options, subcommands, auto-help,
env fallback, type parsing. Zero dependencies.

Example::

    from lombokcliparse import App, ArgType

    app = (App("myapp", "My application")
        .version("1.0.0")
        .positional("input", "Input file", ArgType.STR, required=True)
        .flag("verbose", "Enable verbose", short="v")
        .option("port", "Port", ArgType.INT, short="p", default="8080"))

    matches = app.parse(["myapp", "data.txt", "--verbose", "-p", "3000"])
"""

from __future__ import annotations

import os
import sys
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class ArgType(Enum):
    STR = "str"
    INT = "int"
    BOOL = "bool"
    FLOAT = "float"


class ParseError(Exception):
    def __init__(self, kind: str, message: str) -> None:
        super().__init__(message)
        self.kind = kind


class Matches:
    """Parsed argument results."""

    def __init__(self) -> None:
        self._values: Dict[str, Any] = {}
        self._flags: Dict[str, bool] = {}
        self._subcommand: Optional[Tuple[str, Matches]] = None
        self._rest: List[str] = []

    def get_str(self, name: str) -> Optional[str]:
        v = self._values.get(name)
        return v if isinstance(v, str) else None

    def get_int(self, name: str) -> Optional[int]:
        v = self._values.get(name)
        return v if isinstance(v, int) and not isinstance(v, bool) else None

    def get_float(self, name: str) -> Optional[float]:
        v = self._values.get(name)
        return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None

    def get_bool(self, name: str) -> bool:
        return self._flags.get(name, False)

    def get(self, name: str) -> Any:
        return self._values.get(name)

    def subcommand(self) -> Optional[Tuple[str, 'Matches']]:
        return self._subcommand

    def rest(self) -> List[str]:
        return self._rest


def _parse_value(name: str, raw: str, ty: ArgType) -> Any:
    if ty == ArgType.STR:
        return raw
    elif ty == ArgType.INT:
        try:
            return int(raw)
        except ValueError:
            raise ParseError("invalid_type", f"invalid value '{raw}' for {name}")
    elif ty == ArgType.FLOAT:
        try:
            return float(raw)
        except ValueError:
            raise ParseError("invalid_type", f"invalid value '{raw}' for {name}")
    elif ty == ArgType.BOOL:
        if raw in ("true", "1", "yes", "on"):
            return True
        if raw in ("false", "0", "no", "off"):
            return False
        raise ParseError("invalid_type", f"invalid value '{raw}' for {name}")


class App:
    """CLI application builder."""

    def __init__(self, name: str, description: str) -> None:
        self._name = name
        self._description = description
        self._version: Optional[str] = None
        self._positionals: List[dict] = []
        self._flags: List[dict] = []
        self._options: List[dict] = []
        self._subcommands: Dict[str, App] = {}

    def version(self, v: str) -> 'App':
        self._version = v
        return self

    def positional(self, name: str, help: str, arg_type: ArgType, required: bool = False) -> 'App':
        self._positionals.append({
            "name": name, "help": help, "arg_type": arg_type, "required": required
        })
        return self

    def flag(self, name: str, help: str, short: Optional[str] = None) -> 'App':
        self._flags.append({"name": name, "help": help, "short": short})
        return self

    def option(
        self, name: str, help: str, arg_type: ArgType,
        short: Optional[str] = None, default: Optional[str] = None,
        env_var: Optional[str] = None,
    ) -> 'App':
        self._options.append({
            "name": name, "help": help, "arg_type": arg_type,
            "short": short, "default": default, "env_var": env_var,
        })
        return self

    def sub(self, sub: 'App') -> 'App':
        self._subcommands[sub._name] = sub
        return self

    def help(self) -> str:
        out = self._name
        if self._version:
            out += f" {self._version}"
        out += f"\n{self._description}\n\n"

        out += f"USAGE:\n    {self._name}"
        if self._subcommands:
            out += " <COMMAND>"
        if self._options or self._flags:
            out += " [OPTIONS]"
        for p in self._positionals:
            n = p["name"].upper()
            out += f" <{n}>" if p["required"] else f" [{n}]"
        out += "\n\n"

        if self._positionals:
            out += "ARGS:\n"
            for p in self._positionals:
                req = " (required)" if p["required"] else ""
                out += f"    <{p['name'].upper()}>    {p['help']}{req}\n"
            out += "\n"

        if self._subcommands:
            out += "COMMANDS:\n"
            for name in sorted(self._subcommands.keys()):
                sub = self._subcommands[name]
                out += f"    {name:<16}{sub._description}\n"
            out += "\n"

        if self._flags or self._options:
            out += "OPTIONS:\n"
            for f in self._flags:
                s = f"-{f['short']}, " if f["short"] else "    "
                out += f"    {s}--{f['name']:<16}{f['help']}\n"
            for o in self._options:
                s = f"-{o['short']}, " if o["short"] else "    "
                d = f" [default: {o['default']}]" if o["default"] else ""
                e = f" [env: {o['env_var']}]" if o["env_var"] else ""
                out += f"    {s}--{o['name']:<16}{o['help']}{d}{e}\n"
            out += "        --help            Show this help message\n"

        return out

    def parse(self, args: List[str]) -> Matches:
        """Parse args list (first element = program name, skipped)."""
        return self._parse_slice(args[1:] if args else [])

    def parse_env(self) -> Matches:
        """Parse from sys.argv."""
        return self.parse(sys.argv)

    def _parse_slice(self, args: List[str]) -> Matches:
        matches = Matches()
        pos_idx = 0
        i = 0
        after_dd = False

        while i < len(args):
            arg = args[i]

            if after_dd:
                matches._rest.append(arg)
                i += 1
                continue

            if arg == "--":
                after_dd = True
                i += 1
                continue

            # --name=value or --name value
            if arg.startswith("--"):
                rest = arg[2:]
                if rest == "help":
                    print(self.help())
                    sys.exit(0)

                eq = rest.find("=")
                if eq != -1:
                    name = rest[:eq]
                    inline_val = rest[eq + 1:]
                else:
                    name = rest
                    inline_val = None

                # Flag?
                flag_def = next((f for f in self._flags if f["name"] == name), None)
                if flag_def:
                    matches._flags[name] = True
                    i += 1
                    continue

                # Option?
                opt_def = next((o for o in self._options if o["name"] == name), None)
                if opt_def:
                    if inline_val is not None:
                        val_str = inline_val
                    else:
                        i += 1
                        if i >= len(args):
                            raise ParseError("missing_value", f"missing value for: --{name}")
                        val_str = args[i]
                    matches._values[opt_def["name"]] = _parse_value(
                        opt_def["name"], val_str, opt_def["arg_type"]
                    )
                    i += 1
                    continue

                raise ParseError("unknown_arg", f"unknown argument: --{name}")

            # Short: -v, -p value, -vn
            if arg.startswith("-") and len(arg) > 1 and not arg.startswith("--"):
                chars = list(arg[1:])
                ci = 0
                while ci < len(chars):
                    ch = chars[ci]

                    flag_def = next((f for f in self._flags if f["short"] == ch), None)
                    if flag_def:
                        matches._flags[flag_def["name"]] = True
                        ci += 1
                        continue

                    opt_def = next((o for o in self._options if o["short"] == ch), None)
                    if opt_def:
                        if ci + 1 < len(chars):
                            val_str = "".join(chars[ci + 1:])
                        else:
                            i += 1
                            if i >= len(args):
                                raise ParseError("missing_value", f"missing value for: {opt_def['name']}")
                            val_str = args[i]
                        matches._values[opt_def["name"]] = _parse_value(
                            opt_def["name"], val_str, opt_def["arg_type"]
                        )
                        break

                    raise ParseError("unknown_arg", f"unknown argument: -{ch}")
                i += 1
                continue

            # Subcommand?
            if pos_idx == 0 and arg in self._subcommands:
                sub = self._subcommands[arg]
                sub_matches = sub._parse_slice(args[i + 1:])
                matches._subcommand = (arg, sub_matches)
                return matches

            # Positional
            if pos_idx < len(self._positionals):
                p = self._positionals[pos_idx]
                matches._values[p["name"]] = _parse_value(p["name"], arg, p["arg_type"])
                pos_idx += 1
            else:
                matches._rest.append(arg)

            i += 1

        # Defaults and env vars
        for o in self._options:
            if o["name"] not in matches._values:
                if o["env_var"]:
                    env_val = os.environ.get(o["env_var"])
                    if env_val is not None:
                        try:
                            matches._values[o["name"]] = _parse_value(
                                o["name"], env_val, o["arg_type"]
                            )
                            continue
                        except ParseError:
                            pass
                if o["default"] is not None:
                    try:
                        matches._values[o["name"]] = _parse_value(
                            o["name"], o["default"], o["arg_type"]
                        )
                    except ParseError:
                        pass

        # Required check
        for p in self._positionals:
            if p["required"] and p["name"] not in matches._values:
                raise ParseError("missing_required", f"missing required argument: {p['name']}")

        return matches
