package lombokcliparse

import (
	"errors"
	"os"
	"strings"
	"testing"
)

func tool() *App {
	return NewApp("tool", "A tool").Version("1.0").
		Positional("input", "Input", TypeStr, true).
		Flag("verbose", "Verbose", 'v').
		Option("level", "Level", TypeInt, 'l', "3", "TOOL_LEVEL").
		Option("ratio", "Ratio", TypeFloat, 0, "", "").
		Option("color", "Colour", TypeBool, 0, "", "")
}

func TestGetters(t *testing.T) {
	m, err := tool().ParseWithEnv([]string{"in", "-v", "--ratio", "0.5", "--color", "on"}, nil)
	if err != nil {
		t.Fatal(err)
	}
	if s, ok := m.GetStr("input"); !ok || s != "in" {
		t.Fatal(s)
	}
	if n, ok := m.GetInt("level"); !ok || n != 3 {
		t.Fatal(n)
	}
	if f, ok := m.GetFloat("ratio"); !ok || f != 0.5 {
		t.Fatal(f)
	}
	if _, ok := m.GetInt("ratio"); ok {
		t.Fatal("ratio is not an int")
	}
	if !m.GetBool("verbose") || !m.GetBool("color") || m.GetBool("missing") {
		t.Fatal("bools")
	}
	if _, _, ok := m.Subcommand(); ok || len(m.Rest()) != 0 {
		t.Fatal("sub/rest")
	}
}

func TestEnvAndParse(t *testing.T) {
	t.Setenv("TOOL_LEVEL", "9")
	m, err := tool().Parse([]string{"tool", "x"})
	if err != nil {
		t.Fatal(err)
	}
	if n, _ := m.GetInt("level"); n != 9 {
		t.Fatal(n)
	}
	if _, err := NewApp("t", "").Parse(nil); err != nil {
		t.Fatal(err)
	}
	old := os.Args
	defer func() { os.Args = old }()
	os.Args = []string{"tool", "f"}
	if m := tool().Run(); m == nil {
		t.Fatal("Run")
	}
	if _, err := tool().ParseEnv(); err != nil {
		t.Fatal(err)
	}
}

func TestHelpVersionErrors(t *testing.T) {
	_, err := tool().ParseWithEnv([]string{"--help"}, nil)
	var pe *ParseError
	if !errors.As(err, &pe) || !pe.IsInfo() || pe.Error() != tool().Help() {
		t.Fatal(err)
	}
	_, err = tool().ParseWithEnv([]string{"x", "-l", "z"}, nil)
	if !errors.As(err, &pe) || pe.IsInfo() || pe.Error() != "INVALID_VALUE: invalid value 'z' for '-l'" {
		t.Fatal(err)
	}
	err = NewApp("d", "").Subcommand(NewApp("bad name", "")).Validate()
	if err == nil || err.Error() != "INVALID_DEFINITION: invalid name: 'bad name'" {
		t.Fatal(err)
	}
	err = NewApp("d", "").Flag("a", "", 'é').Validate()
	if err == nil || !strings.Contains(err.Error(), "invalid short") {
		t.Fatal(err)
	}
	_, err = NewApp("d", "").Positional("p", "", TypeStr, false).Positional("q", "", TypeStr, true).ParseWithEnv(nil, nil)
	if err == nil || !strings.Contains(err.Error(), "required after optional") {
		t.Fatal(err)
	}
}

func TestParseValue(t *testing.T) {
	for _, c := range []struct {
		t   ArgType
		raw string
		ok  bool
	}{
		{TypeInt, "-9007199254740991", true}, {TypeInt, "99999999999999999", false},
		{TypeInt, "9007199254740992", false}, {TypeFloat, "1e+", false}, {TypeFloat, "1e309", false},
		{TypeBool, "ÿes", false}, {ArgType("other"), "x", false},
	} {
		if _, ok := ParseValue(c.t, c.raw); ok != c.ok {
			t.Errorf("%s %q: %v", c.t, c.raw, ok)
		}
	}
}
