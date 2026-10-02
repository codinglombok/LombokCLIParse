import pytest

from lombokcliparse import App, ArgType, ParseError, __version__, parse_value


def app():
    return (App("tool", "A tool").version("1.0")
            .positional("input", "Input", ArgType.STR, True)
            .flag("verbose", "Verbose", "v")
            .option("level", "Level", ArgType.INT, "l", "3", "TOOL_LEVEL")
            .option("ratio", "Ratio", ArgType.FLOAT)
            .option("color", "Colour", ArgType.BOOL))


def test_getters():
    m = app().parse_with_env(["in", "-v", "--ratio", "0.5", "--color", "on"])
    assert m.get_str("input") == "in"
    assert m.get_int("level") == 3
    assert m.get_float("ratio") == 0.5
    assert m.get_float("level") is None and m.get_int("ratio") is None and m.get_str("level") is None
    assert m.get_bool("verbose") and m.get_bool("color") and not m.get_bool("missing")
    assert m.get("level") == 3 and m.get("missing") is None
    assert m.type_of("missing") is None
    assert m.subcommand() is None and m.rest() == []


def test_env_sources(monkeypatch):
    assert app().parse_with_env(["x"], lambda k: "9" if k == "TOOL_LEVEL" else None).get_int("level") == 9
    assert app().parse_with_env(["x"], {"TOOL_LEVEL": "8"}).get_int("level") == 8
    monkeypatch.setenv("LOMBOKCLIPARSE_TEST", "5")
    a = App("t").option("n", "", ArgType.INT, env_var="LOMBOKCLIPARSE_TEST")
    assert a.parse(["t"]).get_int("n") == 5
    monkeypatch.setattr("sys.argv", ["t"])
    assert a.parse_env().get_int("n") == 5


def test_help_version_errors():
    with pytest.raises(ParseError) as ei:
        app().parse_with_env(["--help"])
    assert ei.value.is_info and ei.value.code == "HELP" and ei.value.text == app().help() == str(ei.value)
    with pytest.raises(ParseError) as ei:
        app().parse_with_env(["x", "-l", "z"])
    assert not ei.value.is_info and ei.value.value == "z" and str(ei.value) == "INVALID_VALUE: invalid value 'z' for '-l'"
    with pytest.raises(ParseError, match="INVALID_DEFINITION: invalid name: 'bad name'"):
        App("d").sub(App("bad name")).validate()


def test_run(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["tool", "--version"])
    with pytest.raises(SystemExit) as ei:
        app().run()
    assert ei.value.code == 0 and capsys.readouterr().out == "tool 1.0\n"
    monkeypatch.setattr("sys.argv", ["tool"])
    with pytest.raises(SystemExit) as ei:
        app().run()
    assert ei.value.code == 2 and capsys.readouterr().err == "error: MISSING_REQUIRED: missing required argument 'input'\n"
    monkeypatch.setattr("sys.argv", ["tool", "f"])
    assert app().run().get_str("input") == "f"


def test_parse_value():
    assert parse_value(ArgType.INT, "1_000") is None
    assert parse_value(ArgType.INT, " 5") is None
    assert parse_value(ArgType.FLOAT, "inf") is None
    assert parse_value(ArgType.BOOL, "ÿes") is None
    assert __version__ == "0.2.0"
