"""LombokCLIParse for Python: positional arguments, flags, typed options,
subcommands, environment fallback and generated help. The same input gives
the same result, error message and help text in the Rust, TypeScript, Go and
PHP ports (docs/SPEC_LombokCLIParse_v0.2.0.md).

Example::

    from lombokcliparse import App, ArgType

    app = (App("myapp", "My application")
           .version("1.0.0")
           .positional("input", "Input file", ArgType.STR, required=True)
           .flag("verbose", "Verbose output", short="v")
           .option("port", "Port", ArgType.INT, short="p", default="8080"))
    m = app.parse(["myapp", "data.txt", "-v", "-p", "3000"])
    m.get_int("port")  # 3000
"""

from __future__ import annotations

import os
import re
import sys
from enum import Enum
from typing import Callable, Dict, List, Mapping, NoReturn, Optional, Sequence, Tuple, Union

__version__ = "0.2.0"
__all__ = ["App", "ArgType", "Matches", "ParseError", "MAX_SAFE_INTEGER", "parse_value"]

MAX_SAFE_INTEGER = 2**53 - 1


class ArgType(Enum):
    """Type of a positional argument or option (SPEC section 3)."""

    STR = "string"
    INT = "int"
    FLOAT = "float"
    BOOL = "bool"


Value = Union[str, int, float, bool]

_MESSAGES: Dict[str, Callable[[str, Optional[str], Optional[str]], str]] = {
    "UNKNOWN_ARGUMENT": lambda a, v, r: f"unknown argument '{a}'",
    "MISSING_VALUE": lambda a, v, r: f"missing value for '{a}'",
    "INVALID_VALUE": lambda a, v, r: f"invalid value '{v}' for '{a}'",
    "MISSING_REQUIRED": lambda a, v, r: f"missing required argument '{a}'",
    "UNEXPECTED_ARGUMENT": lambda a, v, r: f"unexpected argument '{a}'",
    "UNKNOWN_SUBCOMMAND": lambda a, v, r: f"unknown subcommand '{a}'",
    "FLAG_TAKES_NO_VALUE": lambda a, v, r: f"flag '{a}' does not take a value",
    "INVALID_DEFINITION": lambda a, v, r: f"{r}: '{a}'",
}


class ParseError(Exception):
    """Raised when parsing stops. ``HELP`` and ``VERSION`` are not failures:
    ``text`` holds what to print (use :meth:`App.run` to handle them)."""

    def __init__(self, code: str, arg: str = "", value: Optional[str] = None,
                 reason: Optional[str] = None, text: Optional[str] = None) -> None:
        self.code = code
        self.arg = arg
        self.value = value
        self.reason = reason
        self.text = text
        super().__init__(text if text is not None else f"{code}: {_MESSAGES[code](arg, value, reason)}")

    @property
    def is_info(self) -> bool:
        """True for HELP and VERSION, which should exit with status 0."""
        return self.code in ("HELP", "VERSION")


_INT_RE = re.compile(r"[+-]?[0-9]+")
_FLOAT_RE = re.compile(r"[+-]?([0-9]+(\.[0-9]*)?|\.[0-9]+)([eE][+-]?[0-9]+)?")
_NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")
_SHORT_RE = re.compile(r"[A-Za-z]")
_BOOLS = {"true": True, "1": True, "yes": True, "on": True, "false": False, "0": False, "no": False, "off": False}
_PLACEHOLDER = {ArgType.STR: "<VALUE>", ArgType.INT: "<INT>", ArgType.FLOAT: "<FLOAT>", ArgType.BOOL: "<BOOL>"}


def parse_value(arg_type: ArgType, raw: str) -> Optional[Value]:
    """Parses ``raw`` as ``arg_type``; ``None`` when the text is not valid for the type.
    (Python's ``int()``/``float()`` accept more, such as ``1_000`` or spaces; the
    grammar here is the one of SPEC section 3.)"""
    if arg_type is ArgType.STR:
        return raw
    if arg_type is ArgType.INT:
        if not _INT_RE.fullmatch(raw):
            return None
        v = int(raw)
        return v if -MAX_SAFE_INTEGER <= v <= MAX_SAFE_INTEGER else None
    if arg_type is ArgType.FLOAT:
        if not _FLOAT_RE.fullmatch(raw):
            return None
        f = float(raw)
        return f if f not in (float("inf"), float("-inf")) else None
    if not raw.isascii():
        return None
    return _BOOLS.get(raw.lower())


class Matches:
    """The result of a successful parse."""

    def __init__(self) -> None:
        self._values: Dict[str, Tuple[ArgType, Value]] = {}
        self._flags: set = set()
        self._sub: Optional[Tuple[str, "Matches"]] = None
        self._rest: List[str] = []

    def _typed(self, name: str, t: ArgType) -> Optional[Value]:
        e = self._values.get(name)
        return e[1] if e is not None and e[0] is t else None

    def get_str(self, name: str) -> Optional[str]:
        """A string value."""
        return self._typed(name, ArgType.STR)  # type: ignore[return-value]

    def get_int(self, name: str) -> Optional[int]:
        """An int value."""
        return self._typed(name, ArgType.INT)  # type: ignore[return-value]

    def get_float(self, name: str) -> Optional[float]:
        """A float value."""
        return self._typed(name, ArgType.FLOAT)  # type: ignore[return-value]

    def get_bool(self, name: str) -> bool:
        """True when the flag was given or a bool option is true."""
        return name in self._flags or self._typed(name, ArgType.BOOL) is True

    def get(self, name: str) -> Optional[Value]:
        """Any value by name."""
        e = self._values.get(name)
        return None if e is None else e[1]

    def type_of(self, name: str) -> Optional[ArgType]:
        """The type of a stored value."""
        e = self._values.get(name)
        return None if e is None else e[0]

    def values(self) -> List[Tuple[str, Value]]:
        """All values, sorted by name."""
        return [(k, self._values[k][1]) for k in sorted(self._values)]

    def flags(self) -> List[str]:
        """Names of the flags that were given, sorted."""
        return sorted(self._flags)

    def subcommand(self) -> Optional[Tuple[str, "Matches"]]:
        """The selected subcommand and its matches."""
        return self._sub

    def rest(self) -> List[str]:
        """Tokens after ``--`` that did not fill a positional argument."""
        return self._rest


def _join(parts: Sequence[str]) -> str:
    return " ".join(p for p in parts if p)


def _section(title: str, rows: List[Tuple[str, str]]) -> str:
    width = max(len(left) for left, _ in rows)  # len() counts code points
    out = title + ":\n"
    for left, help_ in rows:
        out += ("    " + left.ljust(width) + "  " + help_ if help_ else "    " + left) + "\n"
    return out


def _def_err(arg: str, reason: str) -> ParseError:
    return ParseError("INVALID_DEFINITION", arg, reason=reason)


EnvLookup = Union[Callable[[str], Optional[str]], Mapping[str, str]]


class App:
    """A command-line application or subcommand definition (builder)."""

    def __init__(self, name: str, description: str = "") -> None:
        self._name = name
        self._description = description
        self._version: Optional[str] = None
        self._positionals: List[dict] = []
        self._args: List[dict] = []
        self._subs: List[App] = []

    def version(self, v: str) -> "App":
        """Sets the version; enables ``--version``."""
        self._version = v
        return self

    def positional(self, name: str, help: str, arg_type: ArgType = ArgType.STR, required: bool = False) -> "App":
        """Adds a positional argument (filled in definition order)."""
        self._positionals.append({"name": name, "help": help, "type": arg_type, "required": required})
        return self

    def flag(self, name: str, help: str, short: Optional[str] = None) -> "App":
        """Adds a boolean flag, ``--name`` or ``-c``."""
        self._args.append({"kind": "flag", "name": name, "help": help, "short": short})
        return self

    def option(self, name: str, help: str, arg_type: ArgType = ArgType.STR, short: Optional[str] = None,
               default: Optional[str] = None, env_var: Optional[str] = None) -> "App":
        """Adds an option taking a value; when absent, ``env_var`` and then ``default`` are used."""
        self._args.append({"kind": "option", "name": name, "help": help, "type": arg_type, "short": short,
                           "default": default, "env": env_var})
        return self

    def subcommand(self, sub: "App") -> "App":
        """Adds a subcommand. An app with subcommands has no positional arguments."""
        self._subs.append(sub)
        return self

    sub = subcommand

    def validate(self) -> None:
        """Checks the rules of SPEC section 2; raises ``INVALID_DEFINITION``."""
        reserved = {"help"} | ({"version"} if self._version is not None else set())
        names: set = set()
        shorts: set = set()
        for a in self._positionals + self._args:
            n = a["name"]
            if not _NAME_RE.fullmatch(n):
                raise _def_err(n, "invalid name")
            if n in reserved:
                raise _def_err(n, "reserved name")
            if n in names:
                raise _def_err(n, "duplicate name")
            names.add(n)
            s = a.get("short")
            if s is not None:
                if not _SHORT_RE.fullmatch(s):
                    raise _def_err(s, "invalid short")
                if s in shorts:
                    raise _def_err(s, "duplicate short")
                shorts.add(s)
            if a.get("kind") == "option" and a["default"] is not None and parse_value(a["type"], a["default"]) is None:
                raise _def_err(n, "invalid default")
        seen_optional = False
        for p in self._positionals:
            if p["required"] and seen_optional:
                raise _def_err(p["name"], "required after optional")
            seen_optional = seen_optional or not p["required"]
        if self._subs and self._positionals:
            raise _def_err(self._subs[0]._name, "positionals with subcommands")
        sub_names: set = set()
        for s in self._subs:
            if not _NAME_RE.fullmatch(s._name):
                raise _def_err(s._name, "invalid name")
            if s._name in sub_names:
                raise _def_err(s._name, "duplicate name")
            sub_names.add(s._name)
            s.validate()

    def help(self) -> str:
        """The help text (SPEC section 5) as shown for ``--help``."""
        return self._help_at(self._name)

    def _help_at(self, path: str) -> str:
        out = self._name + (" " + self._version if self._version is not None else "") + "\n"
        if self._description:
            out += self._description + "\n"
        out += "\nUSAGE:\n    " + path + " [OPTIONS]"
        if self._subs:
            out += " <COMMAND>"
        for p in self._positionals:
            n = p["name"].upper()
            out += f" <{n}>" if p["required"] else f" [{n}]"
        out += "\n"
        if self._positionals:
            out += "\n" + _section("ARGS", [("<%s>" % p["name"].upper(), _join([p["help"], "(required)" if p["required"] else ""]))
                                            for p in self._positionals])
        if self._subs:
            out += "\n" + _section("COMMANDS", [(s._name, s._description) for s in self._subs])
        rows: List[Tuple[str, str]] = []
        for a in self._args:
            left = ("-%s, " % a["short"] if a["short"] is not None else "    ") + "--" + a["name"]
            if a["kind"] == "flag":
                rows.append((left, a["help"]))
                continue
            left += " " + _PLACEHOLDER[a["type"]]
            rows.append((left, _join([a["help"],
                                      "[default: %s]" % a["default"] if a["default"] is not None else "",
                                      "[env: %s]" % a["env"] if a["env"] is not None else ""])))
        rows.append(("    --help", "Print help"))
        if self._version is not None:
            rows.append(("    --version", "Print version"))
        return out + "\n" + _section("OPTIONS", rows)

    def parse(self, argv: Sequence[str]) -> Matches:
        """Parses a full command line (the first element is the program name),
        with ``os.environ`` for environment fallback."""
        return self.parse_with_env(list(argv)[1:], os.environ)

    def parse_with_env(self, tokens: Sequence[str], env: EnvLookup = {}) -> Matches:  # noqa: B006 - never mutated
        """Parses ``tokens`` (without the program name) with an explicit environment."""
        self.validate()
        lookup = env if callable(env) else env.get
        return self._parse(list(tokens), lookup, self._name)

    def parse_env(self) -> Matches:
        """Parses ``sys.argv``."""
        return self.parse(sys.argv)

    def run(self) -> Matches:
        """Parses ``sys.argv``; prints help or version and exits with 0, or
        prints the error and exits with 2."""
        try:
            return self.parse_env()
        except ParseError as e:
            if e.is_info:
                sys.stdout.write(e.text or "")
                _exit(0)
            sys.stderr.write(f"error: {e}\n")
            _exit(2)

    @staticmethod
    def _set(m: Matches, a: dict, raw: str, arg: str) -> None:
        v = parse_value(a["type"], raw)
        if v is None:
            raise ParseError("INVALID_VALUE", arg, value=raw)
        m._values[a["name"]] = (a["type"], v)

    def _parse(self, tokens: List[str], env: Callable[[str], Optional[str]], path: str) -> Matches:
        m = Matches()
        pos_idx = i = 0
        after_dd = False
        while i < len(tokens):
            tok = tokens[i]
            i += 1
            if not after_dd:
                if tok == "--":
                    after_dd = True
                    continue
                if tok == "--help":
                    raise ParseError("HELP", text=self._help_at(path))
                if tok == "--version" and self._version is not None:
                    raise ParseError("VERSION", text=f"{self._name} {self._version}\n")
                if tok.startswith("--"):
                    name, eq, inline = tok[2:].partition("=")
                    arg = "--" + name
                    a = next((x for x in self._args if x["name"] == name), None)
                    if a is None:
                        raise ParseError("UNKNOWN_ARGUMENT", arg)
                    if a["kind"] == "flag":
                        if eq:
                            raise ParseError("FLAG_TAKES_NO_VALUE", arg)
                        m._flags.add(a["name"])
                        continue
                    if not eq:
                        if i >= len(tokens):
                            raise ParseError("MISSING_VALUE", arg)
                        inline = tokens[i]
                        i += 1
                    self._set(m, a, inline, arg)
                    continue
                if len(tok) > 1 and tok[0] == "-" and tok[1] not in "0123456789.":
                    cluster = tok[1:]
                    for k, c in enumerate(cluster):
                        arg = "-" + c
                        a = next((x for x in self._args if x["short"] == c), None)
                        if a is None:
                            raise ParseError("UNKNOWN_ARGUMENT", arg)
                        if a["kind"] == "flag":
                            m._flags.add(a["name"])
                            continue
                        raw = cluster[k + 1:]
                        if raw.startswith("="):
                            raw = raw[1:]
                        elif raw == "":
                            if i >= len(tokens):
                                raise ParseError("MISSING_VALUE", arg)
                            raw = tokens[i]
                            i += 1
                        self._set(m, a, raw, arg)
                        break
                    continue
            if not after_dd and self._subs:
                sub = next((s for s in self._subs if s._name == tok), None)
                if sub is None:
                    raise ParseError("UNKNOWN_SUBCOMMAND", tok)
                m._sub = (tok, sub._parse(tokens[i:], env, f"{path} {tok}"))
                break
            if pos_idx < len(self._positionals):
                p = self._positionals[pos_idx]
                v = parse_value(p["type"], tok)
                if v is None:
                    raise ParseError("INVALID_VALUE", p["name"], value=tok)
                m._values[p["name"]] = (p["type"], v)
                pos_idx += 1
            elif after_dd:
                m._rest.append(tok)
            else:
                raise ParseError("UNEXPECTED_ARGUMENT", tok)
        for a in self._args:
            if a["kind"] != "option" or a["name"] in m._values:
                continue
            from_env = env(a["env"]) if a["env"] is not None else None
            if from_env is not None:
                self._set(m, a, from_env, "--" + a["name"])
            elif a["default"] is not None:
                self._set(m, a, a["default"], "--" + a["name"])
        for p in self._positionals:
            if p["required"] and p["name"] not in m._values:
                raise ParseError("MISSING_REQUIRED", p["name"])
        return m


def _exit(code: int) -> NoReturn:
    sys.exit(code)
