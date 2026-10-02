"""Runs the shared vectors (vectors/lombokcliparse-vectors-v1.json)."""

import json
import pathlib
import struct

import pytest

from lombokcliparse import App, ArgType, ParseError

DOC = json.loads((pathlib.Path(__file__).resolve().parents[2] / "vectors" / "lombokcliparse-vectors-v1.json").read_text(encoding="utf-8"))


def build(d):
    app = App(d["name"], d["description"])
    if d["version"] is not None:
        app.version(d["version"])
    for p in d["positionals"]:
        app.positional(p["name"], p["help"], ArgType(p["type"]), p["required"])
    for a in d["args"]:
        if a["kind"] == "flag":
            app.flag(a["name"], a["help"], a["short"])
        else:
            app.option(a["name"], a["help"], ArgType(a["type"]), a["short"], a["default"], a["env"])
    for s in d["subcommands"]:
        app.subcommand(build(s))
    return app


def encode(m):
    values = {}
    for k, v in m.values():
        t = m.type_of(k)
        if t is ArgType.INT:
            values[k] = {"int": str(v)}
        elif t is ArgType.FLOAT:
            values[k] = {"float": "0x%016x" % struct.unpack("<Q", struct.pack("<d", v))[0]}
        elif t is ArgType.BOOL:
            values[k] = {"bool": v}
        else:
            values[k] = {"str": v}
    sub = m.subcommand()
    return {"values": values, "flags": m.flags(), "rest": m.rest(),
            "subcommand": None if sub is None else {"name": sub[0], "matches": encode(sub[1])}}


def run(c):
    try:
        return {"matches": encode(build(c["app"]).parse_with_env(c["argv"], c["env"]))}
    except ParseError as e:
        if e.code == "HELP":
            return {"help": e.text}
        if e.code == "VERSION":
            return {"version": e.text}
        err = {"code": e.code, "arg": e.arg, "message": str(e)}
        if e.value is not None:
            err["value"] = e.value
        return {"error": err}


def test_at_least_100_cases():
    assert len(DOC["cases"]) >= 100


@pytest.mark.parametrize("case", DOC["cases"], ids=[c["id"] for c in DOC["cases"]])
def test_vector(case):
    assert run(case) == case["expected"]
