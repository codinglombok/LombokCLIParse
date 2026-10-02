#!/usr/bin/env python3
"""Builds vectors/lombokcliparse-vectors-v1.json (GP-11).

Expected outputs come from a reference implementation of SPEC_LombokCLIParse
sections 2-6 written in this file from the SPEC, plus hand-written cases whose
expected output is typed out and checked against the reference. Every port
must reproduce every case exactly: parse results, error code/argument/message,
and help and version text byte for byte.

After editing, run:

    python3 vectors/build_vectors.py
    sha256sum vectors/lombokcliparse-vectors-v1.json > vectors/SHA256SUMS

and update the hash in docs/SPEC_LombokCLIParse_v<version>.md.
"""
import json
import pathlib
import re
import struct

NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")
SHORT_RE = re.compile(r"[A-Za-z]")
INT_RE = re.compile(r"[+-]?[0-9]+")
FLOAT_RE = re.compile(r"[+-]?([0-9]+(\.[0-9]*)?|\.[0-9]+)([eE][+-]?[0-9]+)?")
MAX_SAFE = 2**53 - 1
BOOLS = {"true": True, "1": True, "yes": True, "on": True, "false": False, "0": False, "no": False, "off": False}
PLACEHOLDER = {"string": "<VALUE>", "int": "<INT>", "float": "<FLOAT>", "bool": "<BOOL>"}


class Err(Exception):
    def __init__(self, code, arg, value=None, reason=None):
        super().__init__(code)
        self.code, self.arg, self.value, self.reason = code, arg, value, reason

    def message(self):
        m = {
            "UNKNOWN_ARGUMENT": f"unknown argument '{self.arg}'",
            "MISSING_VALUE": f"missing value for '{self.arg}'",
            "INVALID_VALUE": f"invalid value '{self.value}' for '{self.arg}'",
            "MISSING_REQUIRED": f"missing required argument '{self.arg}'",
            "UNEXPECTED_ARGUMENT": f"unexpected argument '{self.arg}'",
            "UNKNOWN_SUBCOMMAND": f"unknown subcommand '{self.arg}'",
            "FLAG_TAKES_NO_VALUE": f"flag '{self.arg}' does not take a value",
            "INVALID_DEFINITION": f"{self.reason}: '{self.arg}'",
        }[self.code]
        return f"{self.code}: {m}"

    def to_json(self):
        out = {"code": self.code, "arg": self.arg, "message": self.message()}
        if self.value is not None:
            out["value"] = self.value
        return out


class Outcome(Exception):
    def __init__(self, kind, text):
        super().__init__(kind)
        self.kind, self.text = kind, text


# ---------------------------------------------------------------------------
# SPEC section 3: values
# ---------------------------------------------------------------------------


def parse_value(ty, raw):
    """Returns the typed value or None when the raw text is invalid."""
    if ty == "string":
        return ("str", raw)
    if ty == "int":
        if not INT_RE.fullmatch(raw):
            return None
        v = int(raw)
        return ("int", v) if -MAX_SAFE <= v <= MAX_SAFE else None
    if ty == "float":
        if not FLOAT_RE.fullmatch(raw):
            return None
        v = float(raw)
        return ("float", v) if v not in (float("inf"), float("-inf")) else None
    if ty == "bool":
        b = BOOLS.get(raw.lower()) if raw.isascii() else None
        return None if b is None else ("bool", b)
    raise ValueError(ty)


def encode_value(v):
    kind, x = v
    if kind == "int":
        return {"int": str(x)}
    if kind == "float":
        return {"float": "0x%016x" % struct.unpack("<Q", struct.pack("<d", x))[0]}
    return {kind: x}


# ---------------------------------------------------------------------------
# SPEC section 2: definitions
# ---------------------------------------------------------------------------


def validate(app):
    reserved = {"help"} | ({"version"} if app.get("version") is not None else set())
    names, shorts = set(), set()
    items = [("positional", p) for p in app.get("positionals", [])] + [
        (a["kind"], a) for a in app.get("args", [])]
    for kind, a in items:
        n = a["name"]
        if not NAME_RE.fullmatch(n):
            raise Err("INVALID_DEFINITION", n, reason="invalid name")
        if n in reserved:
            raise Err("INVALID_DEFINITION", n, reason="reserved name")
        if n in names:
            raise Err("INVALID_DEFINITION", n, reason="duplicate name")
        names.add(n)
        s = a.get("short")
        if s is not None:
            if not (len(s) == 1 and SHORT_RE.fullmatch(s)):
                raise Err("INVALID_DEFINITION", s, reason="invalid short")
            if s in shorts:
                raise Err("INVALID_DEFINITION", s, reason="duplicate short")
            shorts.add(s)
        if kind == "option" and a.get("default") is not None and parse_value(a["type"], a["default"]) is None:
            raise Err("INVALID_DEFINITION", n, reason="invalid default")
    seen_optional = False
    for p in app.get("positionals", []):
        if p.get("required"):
            if seen_optional:
                raise Err("INVALID_DEFINITION", p["name"], reason="required after optional")
        else:
            seen_optional = True
    subs = app.get("subcommands", [])
    if subs and app.get("positionals"):
        raise Err("INVALID_DEFINITION", subs[0]["name"], reason="positionals with subcommands")
    sub_names = set()
    for s in subs:
        if not NAME_RE.fullmatch(s["name"]):
            raise Err("INVALID_DEFINITION", s["name"], reason="invalid name")
        if s["name"] in sub_names:
            raise Err("INVALID_DEFINITION", s["name"], reason="duplicate name")
        sub_names.add(s["name"])
        validate(s)


# ---------------------------------------------------------------------------
# SPEC section 5: help and version text
# ---------------------------------------------------------------------------


def join_parts(parts):
    return " ".join(p for p in parts if p)


def section(title, rows):
    width = max(len(left) for left, _ in rows)
    lines = [title + ":"]
    for left, help_ in rows:
        lines.append("    " + left.ljust(width) + "  " + help_ if help_ else "    " + left)
    return lines


def help_text(app, path):
    lines = [app["name"] + (" " + app["version"] if app.get("version") is not None else "")]
    if app.get("description"):
        lines.append(app["description"])
    usage = "    " + path + " [OPTIONS]"
    if app.get("subcommands"):
        usage += " <COMMAND>"
    for p in app.get("positionals", []):
        usage += (" <%s>" if p.get("required") else " [%s]") % p["name"].upper()
    lines += ["", "USAGE:", usage]
    if app.get("positionals"):
        rows = [("<%s>" % p["name"].upper(), join_parts([p.get("help", ""), "(required)" if p.get("required") else ""]))
                for p in app["positionals"]]
        lines += [""] + section("ARGS", rows)
    if app.get("subcommands"):
        lines += [""] + section("COMMANDS", [(s["name"], s.get("description", "")) for s in app["subcommands"]])
    rows = []
    for a in app.get("args", []):
        left = ("-%s, " % a["short"] if a.get("short") else "    ") + "--" + a["name"]
        parts = [a.get("help", "")]
        if a["kind"] == "option":
            left += " " + PLACEHOLDER[a["type"]]
            if a.get("default") is not None:
                parts.append("[default: %s]" % a["default"])
            if a.get("env") is not None:
                parts.append("[env: %s]" % a["env"])
        rows.append((left, join_parts(parts)))
    rows.append(("    --help", "Print help"))
    if app.get("version") is not None:
        rows.append(("    --version", "Print version"))
    lines += [""] + section("OPTIONS", rows)
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# SPEC section 4: parsing
# ---------------------------------------------------------------------------


def parse_app(app, tokens, env, path):
    m = {"values": {}, "flags": [], "rest": [], "subcommand": None}
    args = app.get("args", [])
    by_long = {a["name"]: a for a in args}
    by_short = {a["short"]: a for a in args if a.get("short")}
    positionals = app.get("positionals", [])
    pos_idx, i, after_dd = 0, 0, False

    def set_option(a, raw, arg):
        v = parse_value(a["type"], raw)
        if v is None:
            raise Err("INVALID_VALUE", arg, value=raw)
        m["values"][a["name"]] = v

    def set_flag(a):
        if a["name"] not in m["flags"]:
            m["flags"].append(a["name"])

    while i < len(tokens):
        tok = tokens[i]
        i += 1
        if not after_dd:
            if tok == "--":
                after_dd = True
                continue
            if tok == "--help":
                raise Outcome("help", help_text(app, path))
            if tok == "--version" and app.get("version") is not None:
                raise Outcome("version", app["name"] + " " + app["version"] + "\n")
            if tok.startswith("--"):
                body = tok[2:]
                name, inline = (body.split("=", 1) + [None])[:2] if "=" in body else (body, None)
                a = by_long.get(name)
                if a is None:
                    raise Err("UNKNOWN_ARGUMENT", "--" + name)
                if a["kind"] == "flag":
                    if inline is not None:
                        raise Err("FLAG_TAKES_NO_VALUE", "--" + name)
                    set_flag(a)
                    continue
                if inline is None:
                    if i >= len(tokens):
                        raise Err("MISSING_VALUE", "--" + name)
                    inline = tokens[i]
                    i += 1
                set_option(a, inline, "--" + name)
                continue
            if tok.startswith("-") and len(tok) > 1 and not (tok[1].isdigit() and tok[1].isascii()) and tok[1] != ".":
                chars = list(tok[1:])
                k = 0
                while k < len(chars):
                    c = chars[k]
                    a = by_short.get(c)
                    if a is None:
                        raise Err("UNKNOWN_ARGUMENT", "-" + c)
                    if a["kind"] == "flag":
                        set_flag(a)
                        k += 1
                        continue
                    raw = "".join(chars[k + 1:])
                    if raw.startswith("="):
                        raw = raw[1:]
                    elif raw == "":
                        if i >= len(tokens):
                            raise Err("MISSING_VALUE", "-" + c)
                        raw = tokens[i]
                        i += 1
                    set_option(a, raw, "-" + c)
                    break
                continue
        # positional token
        if not after_dd and app.get("subcommands"):
            sub = next((s for s in app["subcommands"] if s["name"] == tok), None)
            if sub is None:
                raise Err("UNKNOWN_SUBCOMMAND", tok)
            m["subcommand"] = {"name": tok, "matches": parse_app(sub, tokens[i:], env, path + " " + tok)}
            break
        if pos_idx < len(positionals):
            p = positionals[pos_idx]
            v = parse_value(p.get("type", "string"), tok)
            if v is None:
                raise Err("INVALID_VALUE", p["name"], value=tok)
            m["values"][p["name"]] = v
            pos_idx += 1
        elif after_dd:
            m["rest"].append(tok)
        else:
            raise Err("UNEXPECTED_ARGUMENT", tok)
    for a in args:
        if a["kind"] != "option" or a["name"] in m["values"]:
            continue
        if a.get("env") is not None and a["env"] in env:
            set_option(a, env[a["env"]], "--" + a["name"])
        elif a.get("default") is not None:
            set_option(a, a["default"], "--" + a["name"])
    for p in positionals:
        if p.get("required") and p["name"] not in m["values"]:
            raise Err("MISSING_REQUIRED", p["name"])
    return m


def encode_matches(m):
    return {
        "values": {k: encode_value(v) for k, v in sorted(m["values"].items())},
        "flags": sorted(m["flags"]),
        "rest": m["rest"],
        "subcommand": None if m["subcommand"] is None else {
            "name": m["subcommand"]["name"], "matches": encode_matches(m["subcommand"]["matches"])},
    }


def run(app, argv, env):
    try:
        validate(app)
        return {"matches": encode_matches(parse_app(app, argv, env, app["name"]))}
    except Outcome as o:
        return {o.kind: o.text}
    except Err as e:
        return {"error": e.to_json()}


# ---------------------------------------------------------------------------
# Apps and cases
# ---------------------------------------------------------------------------


def pos(name, help_="", type_="string", required=False):
    return {"name": name, "help": help_, "type": type_, "required": required}


def flag(name, help_="", short=None):
    return {"kind": "flag", "name": name, "help": help_, "short": short}


def opt(name, help_="", type_="string", short=None, default=None, env=None):
    return {"kind": "option", "name": name, "help": help_, "type": type_, "short": short, "default": default, "env": env}


def app(name, description="", version=None, positionals=(), args=(), subcommands=()):
    return {"name": name, "description": description, "version": version, "positionals": list(positionals),
            "args": list(args), "subcommands": list(subcommands)}


TOOL = app("tool", "A test tool", "1.2.3",
           [pos("input", "Input file", required=True), pos("output", "Output file")],
           [flag("verbose", "Verbose output", "v"), flag("dry-run", "Do nothing", "n"),
            opt("port", "Port number", "int", "p", "8080"), opt("host", "Host name", short="H", default="localhost"),
            opt("config", "Config path", short="c", env="TOOL_CONFIG"), opt("rate", "Rate limit", "float", "r"),
            opt("color", "Use colour", "bool")])

CLI = app("cli", "Data tool", "0.9.0", args=[flag("verbose", "Verbose", "v"), opt("level", "Log level", "int", "l", "1")],
          subcommands=[
              app("ingest", "Ingest data", positionals=[pos("path", "Data path", required=True)],
                  args=[flag("force", "Overwrite", "f"), opt("batch", "Batch size", "int", "b", "100", "CLI_BATCH")]),
              app("query", "Query data", positionals=[pos("text", "Query text", required=True), pos("limit", "Max results", "int")],
                  args=[opt("format", "Output format", short="F", default="table")]),
              app("admin", "Administration", subcommands=[app("reset", "Reset state", args=[flag("yes", "Confirm", "y")])]),
          ])

NUMS = app("calc", "Numbers", positionals=[pos("a", "First", "float", True), pos("b", "Second", "int")],
           args=[opt("offset", "Offset", "int", "o"), opt("scale", "Scale", "float", "s", "1.0"), opt("on", "Switch", "bool", "b")])

MIN = app("min")

cases = []


def add(group, application, argv, env=None, expected=None, note=None):
    env = env or {}
    model = run(application, argv, env)
    if expected is not None:
        assert model == expected, f"hand-written case disagrees with SPEC model: {note}\n{json.dumps(model, indent=1)}\n{json.dumps(expected, indent=1)}"
    case = {"id": f"{group}-{sum(1 for c in cases if c['id'].startswith(group + '-')) + 1:03d}"}
    if note:
        case["note"] = note
    case.update({"app": application, "argv": argv, "env": env, "expected": model})
    cases.append(case)


def M(values=None, flags=(), rest=(), sub=None):
    return {"matches": {"values": values or {}, "flags": list(flags), "rest": list(rest), "subcommand": sub}}


def E(code, arg, message, value=None):
    e = {"code": code, "arg": arg, "message": message}
    if value is not None:
        e["value"] = value
    return {"error": e}


TOOL_DEFAULTS = {"host": {"str": "localhost"}, "port": {"int": "8080"}}

# --- basic parsing (hand-written) ---------------------------------------------------
add("parse", TOOL, ["in.txt"], expected=M({"input": {"str": "in.txt"}, **TOOL_DEFAULTS}), note="defaults applied")
add("parse", TOOL, ["in.txt", "out.txt", "-v"], expected=M({"input": {"str": "in.txt"}, "output": {"str": "out.txt"}, **TOOL_DEFAULTS}, ["verbose"]))
add("parse", TOOL, ["-vn", "a"], expected=M({"input": {"str": "a"}, **TOOL_DEFAULTS}, ["dry-run", "verbose"]), note="combined short flags")
add("parse", TOOL, ["a", "--port", "3000"], expected=M({"input": {"str": "a"}, "host": {"str": "localhost"}, "port": {"int": "3000"}}))
add("parse", TOOL, ["a", "--port=3000"], expected=M({"input": {"str": "a"}, "host": {"str": "localhost"}, "port": {"int": "3000"}}))
add("parse", TOOL, ["a", "-p", "3000"], expected=M({"input": {"str": "a"}, "host": {"str": "localhost"}, "port": {"int": "3000"}}))
add("parse", TOOL, ["a", "-p3000"], expected=M({"input": {"str": "a"}, "host": {"str": "localhost"}, "port": {"int": "3000"}}), note="attached short value")
add("parse", TOOL, ["a", "-p=3000"], expected=M({"input": {"str": "a"}, "host": {"str": "localhost"}, "port": {"int": "3000"}}), note="= after short is dropped")
add("parse", TOOL, ["a", "-vp", "3000"], expected=M({"input": {"str": "a"}, "host": {"str": "localhost"}, "port": {"int": "3000"}}, ["verbose"]), note="flag then option in a cluster")
add("parse", TOOL, ["a", "-p", "1", "-p", "2"], expected=M({"input": {"str": "a"}, "host": {"str": "localhost"}, "port": {"int": "2"}}), note="last value wins")
add("parse", TOOL, ["a", "-v", "-v"], expected=M({"input": {"str": "a"}, **TOOL_DEFAULTS}, ["verbose"]), note="repeated flag")
add("parse", TOOL, ["--host", "--port", "a"], expected=M({"input": {"str": "a"}, "host": {"str": "--port"}, "port": {"int": "8080"}}), note="option value taken verbatim")
add("parse", TOOL, ["a", "--host="], expected=M({"input": {"str": "a"}, "host": {"str": ""}, "port": {"int": "8080"}}), note="empty inline value")
add("parse", TOOL, ["a", "--host", "x=y"], expected=M({"input": {"str": "a"}, "host": {"str": "x=y"}, "port": {"int": "8080"}}))
add("parse", TOOL, ["a", "--host=x=y"], expected=M({"input": {"str": "a"}, "host": {"str": "x=y"}, "port": {"int": "8080"}}), note="split at the first =")
add("parse", TOOL, ["-", "-"], expected=M({"input": {"str": "-"}, "output": {"str": "-"}, **TOOL_DEFAULTS}), note="a single dash is positional")
add("parse", TOOL, ["a", "--", "-v", "--port"], expected=M({"input": {"str": "a"}, "output": {"str": "-v"}, **TOOL_DEFAULTS}, rest=["--port"]), note="after -- everything is positional")
add("parse", TOOL, ["--", "--help"], expected=M({"input": {"str": "--help"}, **TOOL_DEFAULTS}), note="--help after -- is a value")
add("parse", TOOL, ["a", "b", "--", "c", "d"], expected=M({"input": {"str": "a"}, "output": {"str": "b"}, **TOOL_DEFAULTS}, rest=["c", "d"]))
add("parse", TOOL, ["a", "--", "--"], expected=M({"input": {"str": "a"}, "output": {"str": "--"}, **TOOL_DEFAULTS}), note="second -- is a value")
add("parse", TOOL, ["中文.txt", "--host", "éxample"], expected=M({"input": {"str": "中文.txt"}, "host": {"str": "éxample"}, "port": {"int": "8080"}}), note="non-ASCII values")
add("parse", TOOL, ["a", "--color", "YES"], expected=M({"input": {"str": "a"}, "color": {"bool": True}, **TOOL_DEFAULTS}), note="bool is case-insensitive")
add("parse", TOOL, ["a", "--color=off"], expected=M({"input": {"str": "a"}, "color": {"bool": False}, **TOOL_DEFAULTS}))
add("parse", TOOL, ["a", "-r", "0.5"], expected=M({"input": {"str": "a"}, "rate": {"float": "0x3fe0000000000000"}, **TOOL_DEFAULTS}))

# --- environment ------------------------------------------------------------------
add("env", TOOL, ["a"], {"TOOL_CONFIG": "/etc/tool.conf"}, M({"config": {"str": "/etc/tool.conf"}, "input": {"str": "a"}, **TOOL_DEFAULTS}))
add("env", TOOL, ["a", "-c", "cli.conf"], {"TOOL_CONFIG": "/etc/tool.conf"}, M({"config": {"str": "cli.conf"}, "input": {"str": "a"}, **TOOL_DEFAULTS}), note="command line beats env")
add("env", TOOL, ["a"], {"TOOL_CONFIG": ""}, M({"config": {"str": ""}, "input": {"str": "a"}, **TOOL_DEFAULTS}), note="empty env value counts as set")
add("env", TOOL, ["a"], {"OTHER": "x"}, M({"input": {"str": "a"}, **TOOL_DEFAULTS}), note="unrelated env ignored")
add("env", CLI, ["ingest", "p"], {"CLI_BATCH": "50"}, M({"level": {"int": "1"}}, sub={"name": "ingest", "matches": {"values": {"batch": {"int": "50"}, "path": {"str": "p"}}, "flags": [], "rest": [], "subcommand": None}}), note="env beats default")
add("env", CLI, ["ingest", "p"], {"CLI_BATCH": "lots"}, E("INVALID_VALUE", "--batch", "INVALID_VALUE: invalid value 'lots' for '--batch'", "lots"), note="invalid env value is an error")

# --- subcommands --------------------------------------------------------------------
add("sub", CLI, [], expected=M({"level": {"int": "1"}}), note="subcommand is optional")
add("sub", CLI, ["-v", "query", "hello"], expected=M({"level": {"int": "1"}}, ["verbose"], sub={"name": "query", "matches": {"values": {"format": {"str": "table"}, "text": {"str": "hello"}}, "flags": [], "rest": [], "subcommand": None}}))
add("sub", CLI, ["query", "hello", "-v"], expected=E("UNKNOWN_ARGUMENT", "-v", "UNKNOWN_ARGUMENT: unknown argument '-v'"), note="parent flags must come before the subcommand")
add("sub", CLI, ["fetch"], expected=E("UNKNOWN_SUBCOMMAND", "fetch", "UNKNOWN_SUBCOMMAND: unknown subcommand 'fetch'"))
add("sub", CLI, ["query"], expected=E("MISSING_REQUIRED", "text", "MISSING_REQUIRED: missing required argument 'text'"))
add("sub", CLI, ["admin", "reset", "-y"], expected=M({"level": {"int": "1"}}, sub={"name": "admin", "matches": {"values": {}, "flags": [], "rest": [], "subcommand": {"name": "reset", "matches": {"values": {}, "flags": ["yes"], "rest": [], "subcommand": None}}}}), note="nested subcommands")
add("sub", CLI, ["--", "query"], expected=M({"level": {"int": "1"}}, rest=["query"]), note="no subcommand after --; extra tokens after -- go to rest")
add("sub", CLI, ["query", "q", "5", "extra"], expected=E("UNEXPECTED_ARGUMENT", "extra", "UNEXPECTED_ARGUMENT: unexpected argument 'extra'"))

# --- numbers --------------------------------------------------------------------------
add("num", NUMS, ["-1.5", "-2"], expected=M({"a": {"float": "0xbff8000000000000"}, "b": {"int": "-2"}, "scale": {"float": "0x3ff0000000000000"}}), note="negative numbers are positional")
add("num", NUMS, ["1", "--offset", "-5"], expected=M({"a": {"float": "0x3ff0000000000000"}, "offset": {"int": "-5"}, "scale": {"float": "0x3ff0000000000000"}}))
add("num", NUMS, ["1", "-o-5"], expected=M({"a": {"float": "0x3ff0000000000000"}, "offset": {"int": "-5"}, "scale": {"float": "0x3ff0000000000000"}}))
add("num", NUMS, ["-.5"], expected=M({"a": {"float": "0xbfe0000000000000"}, "scale": {"float": "0x3ff0000000000000"}}))
add("num", NUMS, ["1", "x"], expected=E("INVALID_VALUE", "b", "INVALID_VALUE: invalid value 'x' for 'b'", "x"))
add("num", NUMS, ["1", "--offset", "9007199254740991"], expected=M({"a": {"float": "0x3ff0000000000000"}, "offset": {"int": "9007199254740991"}, "scale": {"float": "0x3ff0000000000000"}}), note="largest safe integer")
add("num", NUMS, ["1", "--offset", "9007199254740992"], expected=E("INVALID_VALUE", "--offset", "INVALID_VALUE: invalid value '9007199254740992' for '--offset'", "9007199254740992"), note="beyond the safe integer range")
add("num", NUMS, ["1e309"], expected=E("INVALID_VALUE", "a", "INVALID_VALUE: invalid value '1e309' for 'a'", "1e309"), note="float overflow")
for raw in ["0", "+7", "007", "-0", "1_000", " 5", "5 ", "0x10", "1.0", "", "５", "12345678901234567890"]:
    add("int", NUMS, ["1", "--offset", raw])
for raw in ["1", "1.", ".5", "+2.5e3", "1E-3", "-0.0", "1e-400", "inf", "nan", "1,5", "0x1p3", "1e", ".", "e5", "1.5.2", "2.2250738585072011e-308", "0.1", "179769313486231570000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"]:
    add("float", NUMS, [raw])
for raw in ["true", "FALSE", "Yes", "no", "On", "off", "1", "0", "y", "", "truе"]:
    add("bool", NUMS, ["1", "--on", raw])

# --- errors -------------------------------------------------------------------------
add("error", TOOL, [], expected=E("MISSING_REQUIRED", "input", "MISSING_REQUIRED: missing required argument 'input'"))
add("error", TOOL, ["a", "--bogus"], expected=E("UNKNOWN_ARGUMENT", "--bogus", "UNKNOWN_ARGUMENT: unknown argument '--bogus'"))
add("error", TOOL, ["a", "--bogus=1"], expected=E("UNKNOWN_ARGUMENT", "--bogus", "UNKNOWN_ARGUMENT: unknown argument '--bogus'"), note="inline value not shown")
add("error", TOOL, ["a", "-x"], expected=E("UNKNOWN_ARGUMENT", "-x", "UNKNOWN_ARGUMENT: unknown argument '-x'"))
add("error", TOOL, ["a", "-vx"], expected=E("UNKNOWN_ARGUMENT", "-x", "UNKNOWN_ARGUMENT: unknown argument '-x'"))
add("error", TOOL, ["a", "--port"], expected=E("MISSING_VALUE", "--port", "MISSING_VALUE: missing value for '--port'"))
add("error", TOOL, ["a", "-p"], expected=E("MISSING_VALUE", "-p", "MISSING_VALUE: missing value for '-p'"))
add("error", TOOL, ["a", "--port", "abc"], expected=E("INVALID_VALUE", "--port", "INVALID_VALUE: invalid value 'abc' for '--port'", "abc"))
add("error", TOOL, ["a", "-pabc"], expected=E("INVALID_VALUE", "-p", "INVALID_VALUE: invalid value 'abc' for '-p'", "abc"))
add("error", TOOL, ["a", "--verbose=yes"], expected=E("FLAG_TAKES_NO_VALUE", "--verbose", "FLAG_TAKES_NO_VALUE: flag '--verbose' does not take a value"))
add("error", TOOL, ["a", "b", "c"], expected=E("UNEXPECTED_ARGUMENT", "c", "UNEXPECTED_ARGUMENT: unexpected argument 'c'"))
add("error", TOOL, ["a", "--bogus", "--help"], expected=E("UNKNOWN_ARGUMENT", "--bogus", "UNKNOWN_ARGUMENT: unknown argument '--bogus'"), note="first problem in token order wins")
add("error", TOOL, ["a", "-é"], expected=E("UNKNOWN_ARGUMENT", "-é", "UNKNOWN_ARGUMENT: unknown argument '-é'"), note="shorts are code points")
add("error", TOOL, ["a", "-v\U0001F600"], expected=E("UNKNOWN_ARGUMENT", "-\U0001F600", "UNKNOWN_ARGUMENT: unknown argument '-\U0001F600'"), note="astral code point")
add("error", MIN, ["x"], expected=E("UNEXPECTED_ARGUMENT", "x", "UNEXPECTED_ARGUMENT: unexpected argument 'x'"))
add("error", MIN, ["--version"], expected=E("UNKNOWN_ARGUMENT", "--version", "UNKNOWN_ARGUMENT: unknown argument '--version'"), note="--version only when a version is set")

# --- help and version ------------------------------------------------------------------
add("help", TOOL, ["--help"])
add("help", TOOL, ["a", "--help", "--bogus"], note="--help stops parsing")
add("help", CLI, ["--help"])
add("help", CLI, ["query", "--help"], note="subcommand help shows the full path")
add("help", CLI, ["admin", "reset", "--help"])
add("help", NUMS, ["--help"])
add("help", MIN, ["--help"], note="minimal app")
add("help", app("x", "", None, args=[opt("a-very-long-option-name", "Long", short="a"), flag("b")]), ["--help"], note="column width follows the longest entry; empty help has no trailing spaces")
add("help", app("u", "Unicode été", None, [pos("fé", "x")]), ["--help"])
add("help", app("u", "Unicode", None, args=[opt("name", "Naïve 中文", default="é")]), ["--help"], note="padding counts code points")
add("help", app("e", "", None, [pos("req", required=True)], [opt("o", default="1", env="E")]), ["--help"], note="empty help: suffixes joined by single spaces")
add("help", TOOL, ["-p", "1", "--help"])
add("version", TOOL, ["--version"])
add("version", CLI, ["--version"])
add("version", CLI, ["query", "--version"], note="subcommand without version: unknown argument")
add("version", TOOL, ["--version", "--help"], note="first wins")

# --- definition errors -------------------------------------------------------------------
D = "INVALID_DEFINITION"
add("def", app("d", args=[flag("ok"), flag("ok")]), [], expected=E(D, "ok", "INVALID_DEFINITION: duplicate name: 'ok'"))
add("def", app("d", args=[flag("a", short="x"), opt("b", short="x")]), [], expected=E(D, "x", "INVALID_DEFINITION: duplicate short: 'x'"))
add("def", app("d", args=[flag("bad name")]), [], expected=E(D, "bad name", "INVALID_DEFINITION: invalid name: 'bad name'"))
add("def", app("d", args=[flag("-x")]), [], expected=E(D, "-x", "INVALID_DEFINITION: invalid name: '-x'"))
add("def", app("d", args=[flag("help")]), [], expected=E(D, "help", "INVALID_DEFINITION: reserved name: 'help'"))
add("def", app("d", "", "1", args=[flag("version")]), [], expected=E(D, "version", "INVALID_DEFINITION: reserved name: 'version'"))
add("def", app("d", args=[flag("version")]), ["--version"], expected=M(flags=["version"]), note="version is free when no version is set")
add("def", app("d", args=[flag("a", short="1")]), [], expected=E(D, "1", "INVALID_DEFINITION: invalid short: '1'"), note="digit shorts would clash with negative numbers")
add("def", app("d", args=[flag("a", short="ab")]), [], expected=E(D, "ab", "INVALID_DEFINITION: invalid short: 'ab'"))
add("def", app("d", args=[opt("n", type_="int", default="x")]), [], expected=E(D, "n", "INVALID_DEFINITION: invalid default: 'n'"))
add("def", app("d", positionals=[pos("a"), pos("b", required=True)]), [], expected=E(D, "b", "INVALID_DEFINITION: required after optional: 'b'"))
add("def", app("d", positionals=[pos("a")], subcommands=[app("s")]), [], expected=E(D, "s", "INVALID_DEFINITION: positionals with subcommands: 's'"))
add("def", app("d", subcommands=[app("s"), app("s")]), [], expected=E(D, "s", "INVALID_DEFINITION: duplicate name: 's'"))
add("def", app("d", subcommands=[app("s", args=[flag("x"), flag("x")])]), [], expected=E(D, "x", "INVALID_DEFINITION: duplicate name: 'x'"), note="nested definitions are checked before parsing")
add("def", app("d", positionals=[pos("p")], args=[flag("p")]), [], expected=E(D, "p", "INVALID_DEFINITION: duplicate name: 'p'"), note="one namespace per app")

doc = {
    "name": "lombokcliparse-vectors",
    "version": 1,
    "spec": "docs/SPEC_LombokCLIParse (sections 2-6)",
    "app_format": "app: {name, description, version|null, positionals: [{name, help, type, required}], "
                  "args: [{kind: flag|option, name, help, short|null, type?, default?, env?}], subcommands: [app]}",
    "expected": "{matches: {values: {name: {str|int|float|bool}}, flags: [sorted], rest, subcommand}} | {help: text} | "
                "{version: text} | {error: {code, arg, message, value?}}; int as decimal string, float as binary64 bits",
    "cases": cases,
}
out = pathlib.Path(__file__).with_name("lombokcliparse-vectors-v1.json")
out.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print(f"{len(cases)} cases -> {out}")
