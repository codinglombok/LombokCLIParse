package lombokcliparse

import (
	"os"
	"strings"
	"testing"
)

func testApp() *App {
	return NewApp("testapp", "A test application").
		Version("0.1.0").
		Positional("input", "Input file", TypeStr, true).
		Positional("output", "Output file", TypeStr, false).
		Flag("verbose", "Verbose output", 'v').
		Flag("dry-run", "Dry run mode", 'n').
		Option("port", "Port number", TypeInt, 'p', "8080", "").
		Option("host", "Hostname", TypeStr, 'h', "localhost", "").
		Option("config", "Config path", TypeStr, 'c', "", "TEST_CONFIG").
		Option("rate", "Rate limit", TypeFloat, 'r', "", "")
}

func TestBasicPositional(t *testing.T) {
	m, err := testApp().Parse([]string{"app", "input.txt"})
	if err != nil {
		t.Fatal(err)
	}
	v, ok := m.GetStr("input")
	if !ok || v != "input.txt" {
		t.Fatalf("expected input.txt, got %q", v)
	}
}

func TestTwoPositionals(t *testing.T) {
	m, err := testApp().Parse([]string{"app", "in.txt", "out.txt"})
	if err != nil {
		t.Fatal(err)
	}
	v1, _ := m.GetStr("input")
	v2, _ := m.GetStr("output")
	if v1 != "in.txt" {
		t.Fatalf("expected in.txt, got %q", v1)
	}
	if v2 != "out.txt" {
		t.Fatalf("expected out.txt, got %q", v2)
	}
}

func TestMissingRequired(t *testing.T) {
	_, err := testApp().Parse([]string{"app"})
	if err == nil {
		t.Fatal("expected error for missing required")
	}
	pe := err.(*ParseError)
	if pe.Kind != "missing_required" {
		t.Fatalf("expected missing_required, got %s", pe.Kind)
	}
}

func TestFlagsLong(t *testing.T) {
	m, _ := testApp().Parse([]string{"app", "f.txt", "--verbose"})
	if !m.GetBool("verbose") {
		t.Fatal("verbose should be true")
	}
	if m.GetBool("dry-run") {
		t.Fatal("dry-run should be false")
	}
}

func TestFlagsShort(t *testing.T) {
	m, _ := testApp().Parse([]string{"app", "f.txt", "-v", "-n"})
	if !m.GetBool("verbose") {
		t.Fatal("verbose should be true")
	}
	if !m.GetBool("dry-run") {
		t.Fatal("dry-run should be true")
	}
}

func TestCombinedShortFlags(t *testing.T) {
	m, _ := testApp().Parse([]string{"app", "f.txt", "-vn"})
	if !m.GetBool("verbose") {
		t.Fatal("verbose should be true")
	}
	if !m.GetBool("dry-run") {
		t.Fatal("dry-run should be true")
	}
}

func TestOptionLong(t *testing.T) {
	m, _ := testApp().Parse([]string{"app", "f.txt", "--port", "3000"})
	v, ok := m.GetInt("port")
	if !ok || v != 3000 {
		t.Fatalf("expected 3000, got %d", v)
	}
}

func TestOptionLongEquals(t *testing.T) {
	m, _ := testApp().Parse([]string{"app", "f.txt", "--port=9090"})
	v, ok := m.GetInt("port")
	if !ok || v != 9090 {
		t.Fatalf("expected 9090, got %d", v)
	}
}

func TestOptionShort(t *testing.T) {
	m, _ := testApp().Parse([]string{"app", "f.txt", "-p", "4000"})
	v, ok := m.GetInt("port")
	if !ok || v != 4000 {
		t.Fatalf("expected 4000, got %d", v)
	}
}

func TestDefaults(t *testing.T) {
	m, _ := testApp().Parse([]string{"app", "f.txt"})
	v1, ok1 := m.GetInt("port")
	v2, ok2 := m.GetStr("host")
	if !ok1 || v1 != 8080 {
		t.Fatalf("expected port 8080, got %d", v1)
	}
	if !ok2 || v2 != "localhost" {
		t.Fatalf("expected host localhost, got %q", v2)
	}
}

func TestFloatOption(t *testing.T) {
	m, _ := testApp().Parse([]string{"app", "f.txt", "--rate", "1.5"})
	v, ok := m.GetFloat("rate")
	if !ok || v != 1.5 {
		t.Fatalf("expected 1.5, got %f", v)
	}
}

func TestInvalidType(t *testing.T) {
	_, err := testApp().Parse([]string{"app", "f.txt", "--port", "abc"})
	if err == nil {
		t.Fatal("expected error for invalid type")
	}
	pe := err.(*ParseError)
	if pe.Kind != "invalid_type" {
		t.Fatalf("expected invalid_type, got %s", pe.Kind)
	}
}

func TestUnknownFlag(t *testing.T) {
	_, err := testApp().Parse([]string{"app", "f.txt", "--unknown"})
	if err == nil {
		t.Fatal("expected error for unknown flag")
	}
	pe := err.(*ParseError)
	if pe.Kind != "unknown_arg" {
		t.Fatalf("expected unknown_arg, got %s", pe.Kind)
	}
}

func TestDoubleDash(t *testing.T) {
	m, _ := testApp().Parse([]string{"app", "f.txt", "--", "--not-a-flag", "extra"})
	rest := m.Rest()
	if len(rest) != 2 {
		t.Fatalf("expected 2 rest args, got %d", len(rest))
	}
	if rest[0] != "--not-a-flag" || rest[1] != "extra" {
		t.Fatalf("unexpected rest: %v", rest)
	}
}

func TestSubcommand(t *testing.T) {
	app := NewApp("cli", "CLI tool").
		Flag("verbose", "Verbose", 'v').
		Sub(NewApp("ingest", "Ingest data").
			Positional("path", "Data path", TypeStr, true).
			Flag("force", "Force overwrite", 'f')).
		Sub(NewApp("query", "Query data").
			Positional("text", "Query text", TypeStr, true).
			Option("limit", "Result limit", TypeInt, 'l', "10", ""))

	m, err := app.Parse([]string{"cli", "ingest", "data/", "--force"})
	if err != nil {
		t.Fatal(err)
	}
	name, sub, ok := m.Subcommand()
	if !ok || name != "ingest" {
		t.Fatalf("expected ingest, got %q", name)
	}
	path, _ := sub.GetStr("path")
	if path != "data/" {
		t.Fatalf("expected data/, got %q", path)
	}
	if !sub.GetBool("force") {
		t.Fatal("force should be true")
	}
}

func TestSubcommandQuery(t *testing.T) {
	app := NewApp("cli", "CLI tool").
		Sub(NewApp("query", "Query data").
			Positional("text", "Query text", TypeStr, true).
			Option("limit", "Result limit", TypeInt, 'l', "10", ""))

	m, _ := app.Parse([]string{"cli", "query", "hello world", "-l", "5"})
	name, sub, _ := m.Subcommand()
	if name != "query" {
		t.Fatalf("expected query, got %q", name)
	}
	text, _ := sub.GetStr("text")
	if text != "hello world" {
		t.Fatalf("expected 'hello world', got %q", text)
	}
	limit, _ := sub.GetInt("limit")
	if limit != 5 {
		t.Fatalf("expected 5, got %d", limit)
	}
}

func TestHelpText(t *testing.T) {
	h := testApp().Help()
	checks := []string{"testapp", "A test application", "--verbose", "-v", "[default: 8080]", "[env: TEST_CONFIG]", "<INPUT>"}
	for _, c := range checks {
		if !strings.Contains(h, c) {
			t.Fatalf("help missing %q", c)
		}
	}
}

func TestEnvVarFallback(t *testing.T) {
	os.Setenv("TEST_CONFIG", "/etc/test.toml")
	defer os.Unsetenv("TEST_CONFIG")

	m, _ := testApp().Parse([]string{"app", "f.txt"})
	v, ok := m.GetStr("config")
	if !ok || v != "/etc/test.toml" {
		t.Fatalf("expected /etc/test.toml, got %q", v)
	}
}

func TestMixedFlagsAndPositionals(t *testing.T) {
	m, _ := testApp().Parse([]string{"app", "-v", "input.txt", "--port", "3000", "output.txt", "-n"})
	if !m.GetBool("verbose") {
		t.Fatal("verbose")
	}
	if !m.GetBool("dry-run") {
		t.Fatal("dry-run")
	}
	inp, _ := m.GetStr("input")
	if inp != "input.txt" {
		t.Fatalf("input: %q", inp)
	}
	out, _ := m.GetStr("output")
	if out != "output.txt" {
		t.Fatalf("output: %q", out)
	}
	port, _ := m.GetInt("port")
	if port != 3000 {
		t.Fatalf("port: %d", port)
	}
}
