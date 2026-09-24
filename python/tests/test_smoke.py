"""Smoke tests for lombokcliparse."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from lombokcliparse import App, ArgType, ParseError

passed = 0
failed = 0


def assert_eq(a, b, name):
    global passed, failed
    if a == b:
        passed += 1
    else:
        failed += 1
        print(f"FAIL: {name} — expected {b!r}, got {a!r}")


def assert_true(cond, name):
    global passed, failed
    if cond:
        passed += 1
    else:
        failed += 1
        print(f"FAIL: {name}")


def test_app():
    return (
        App("testapp", "A test application")
        .version("0.1.0")
        .positional("input", "Input file", ArgType.STR, required=True)
        .positional("output", "Output file", ArgType.STR, required=False)
        .flag("verbose", "Verbose output", short="v")
        .flag("dry-run", "Dry run mode", short="n")
        .option("port", "Port number", ArgType.INT, short="p", default="8080")
        .option("host", "Hostname", ArgType.STR, short="h", default="localhost")
        .option("config", "Config path", ArgType.STR, short="c", env_var="TEST_CONFIG")
        .option("rate", "Rate limit", ArgType.FLOAT, short="r")
    )


# Basic positional
m = test_app().parse(["app", "input.txt"])
assert_eq(m.get_str("input"), "input.txt", "basic positional")

# Two positionals
m = test_app().parse(["app", "in.txt", "out.txt"])
assert_eq(m.get_str("input"), "in.txt", "two positionals input")
assert_eq(m.get_str("output"), "out.txt", "two positionals output")

# Missing required
try:
    test_app().parse(["app"])
    assert_true(False, "missing required should raise")
except ParseError as e:
    assert_eq(e.kind, "missing_required", "missing required kind")

# Flags long
m = test_app().parse(["app", "f.txt", "--verbose"])
assert_true(m.get_bool("verbose"), "flag long verbose")
assert_true(not m.get_bool("dry-run"), "flag long dry-run off")

# Flags short
m = test_app().parse(["app", "f.txt", "-v", "-n"])
assert_true(m.get_bool("verbose"), "flag short -v")
assert_true(m.get_bool("dry-run"), "flag short -n")

# Combined short flags
m = test_app().parse(["app", "f.txt", "-vn"])
assert_true(m.get_bool("verbose"), "combined -vn verbose")
assert_true(m.get_bool("dry-run"), "combined -vn dry-run")

# Option long
m = test_app().parse(["app", "f.txt", "--port", "3000"])
assert_eq(m.get_int("port"), 3000, "option long port")

# Option long equals
m = test_app().parse(["app", "f.txt", "--port=9090"])
assert_eq(m.get_int("port"), 9090, "option long equals")

# Option short
m = test_app().parse(["app", "f.txt", "-p", "4000"])
assert_eq(m.get_int("port"), 4000, "option short")

# Defaults
m = test_app().parse(["app", "f.txt"])
assert_eq(m.get_int("port"), 8080, "default port")
assert_eq(m.get_str("host"), "localhost", "default host")

# Float option
m = test_app().parse(["app", "f.txt", "--rate", "1.5"])
assert_eq(m.get_float("rate"), 1.5, "float option")

# Invalid type
try:
    test_app().parse(["app", "f.txt", "--port", "abc"])
    assert_true(False, "invalid type should raise")
except ParseError as e:
    assert_eq(e.kind, "invalid_type", "invalid type kind")

# Unknown flag
try:
    test_app().parse(["app", "f.txt", "--unknown"])
    assert_true(False, "unknown flag should raise")
except ParseError as e:
    assert_eq(e.kind, "unknown_arg", "unknown flag kind")

# Double dash
m = test_app().parse(["app", "f.txt", "--", "--not-a-flag", "extra"])
assert_eq(len(m.rest()), 2, "double dash rest count")
assert_eq(m.rest()[0], "--not-a-flag", "double dash rest 0")
assert_eq(m.rest()[1], "extra", "double dash rest 1")

# Subcommand
app = (
    App("cli", "CLI tool")
    .flag("verbose", "Verbose", short="v")
    .sub(
        App("ingest", "Ingest data")
        .positional("path", "Data path", ArgType.STR, required=True)
        .flag("force", "Force overwrite", short="f")
    )
    .sub(
        App("query", "Query data")
        .positional("text", "Query text", ArgType.STR, required=True)
        .option("limit", "Result limit", ArgType.INT, short="l", default="10")
    )
)

m = app.parse(["cli", "ingest", "data/", "--force"])
sub = m.subcommand()
assert_eq(sub[0], "ingest", "subcommand name")
assert_eq(sub[1].get_str("path"), "data/", "subcommand path")
assert_true(sub[1].get_bool("force"), "subcommand flag")

# Subcommand query
app2 = App("cli", "CLI tool").sub(
    App("query", "Query data")
    .positional("text", "Query text", ArgType.STR, required=True)
    .option("limit", "Result limit", ArgType.INT, short="l", default="10")
)
m = app2.parse(["cli", "query", "hello world", "-l", "5"])
sub = m.subcommand()
assert_eq(sub[0], "query", "subcommand query name")
assert_eq(sub[1].get_str("text"), "hello world", "subcommand query text")
assert_eq(sub[1].get_int("limit"), 5, "subcommand query limit")

# Help text
h = test_app().help()
assert_true("testapp" in h, "help has name")
assert_true("A test application" in h, "help has desc")
assert_true("--verbose" in h, "help has verbose")
assert_true("-v" in h, "help has -v")
assert_true("[default: 8080]" in h, "help has default")
assert_true("[env: TEST_CONFIG]" in h, "help has env")
assert_true("<INPUT>" in h, "help has INPUT")

# Env var fallback
os.environ["TEST_CONFIG"] = "/etc/test.toml"
m = test_app().parse(["app", "f.txt"])
assert_eq(m.get_str("config"), "/etc/test.toml", "env var fallback")
del os.environ["TEST_CONFIG"]

# Mixed flags and positionals
m = test_app().parse(["app", "-v", "input.txt", "--port", "3000", "output.txt", "-n"])
assert_true(m.get_bool("verbose"), "mixed verbose")
assert_true(m.get_bool("dry-run"), "mixed dry-run")
assert_eq(m.get_str("input"), "input.txt", "mixed input")
assert_eq(m.get_str("output"), "output.txt", "mixed output")
assert_eq(m.get_int("port"), 3000, "mixed port")

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed > 0 else 0)
