package lombokcliparse

// Runs the shared vectors (vectors/lombokcliparse-vectors-v1.json).

import (
	"encoding/json"
	"errors"
	"fmt"
	"math"
	"os"
	"reflect"
	"testing"
	"unicode/utf8"
)

type argDef struct {
	Kind     string  `json:"kind"`
	Name     string  `json:"name"`
	Help     string  `json:"help"`
	Type     string  `json:"type"`
	Required bool    `json:"required"`
	Short    *string `json:"short"`
	Default  *string `json:"default"`
	Env      *string `json:"env"`
}

type appDef struct {
	Name        string   `json:"name"`
	Description string   `json:"description"`
	Version     *string  `json:"version"`
	Positionals []argDef `json:"positionals"`
	Args        []argDef `json:"args"`
	Subcommands []appDef `json:"subcommands"`
}

type vcase struct {
	ID       string            `json:"id"`
	App      appDef            `json:"app"`
	Argv     []string          `json:"argv"`
	Env      map[string]string `json:"env"`
	Expected any               `json:"expected"`
}

// shortRune maps a vector short to a rune; ok is false for strings that are
// not a single code point (the Go API takes a rune, so they cannot be expressed).
func shortRune(s *string) (rune, bool) {
	if s == nil {
		return 0, true
	}
	if utf8.RuneCountInString(*s) != 1 {
		return 0, false
	}
	r, _ := utf8.DecodeRuneInString(*s)
	return r, true
}

func build(d appDef) (*App, bool) {
	app := NewApp(d.Name, d.Description)
	if d.Version != nil {
		app.Version(*d.Version)
	}
	for _, p := range d.Positionals {
		app.Positional(p.Name, p.Help, ArgType(p.Type), p.Required)
	}
	for _, a := range d.Args {
		r, ok := shortRune(a.Short)
		if !ok {
			return nil, false
		}
		if a.Kind == "flag" {
			app.Flag(a.Name, a.Help, r)
			continue
		}
		def, env := "", ""
		if a.Default != nil {
			def = *a.Default
		}
		if a.Env != nil {
			env = *a.Env
		}
		app.OptionFull(a.Name, a.Help, ArgType(a.Type), r, def, a.Default != nil, env, a.Env != nil)
	}
	for _, s := range d.Subcommands {
		sub, ok := build(s)
		if !ok {
			return nil, false
		}
		app.Sub(sub)
	}
	return app, true
}

func encode(m *Matches) map[string]any {
	values := map[string]any{}
	for _, k := range m.Names() {
		v, _ := m.Get(k)
		switch v.Type {
		case TypeInt:
			values[k] = map[string]any{"int": fmt.Sprint(v.Int)}
		case TypeFloat:
			values[k] = map[string]any{"float": fmt.Sprintf("0x%016x", math.Float64bits(v.Float))}
		case TypeBool:
			values[k] = map[string]any{"bool": v.Bool}
		default:
			values[k] = map[string]any{"str": v.Str}
		}
	}
	flags := []any{}
	for _, f := range m.Flags() {
		flags = append(flags, f)
	}
	rest := []any{}
	for _, r := range m.Rest() {
		rest = append(rest, r)
	}
	var sub any
	if name, sm, ok := m.Subcommand(); ok {
		sub = map[string]any{"name": name, "matches": encode(sm)}
	}
	return map[string]any{"values": values, "flags": flags, "rest": rest, "subcommand": sub}
}

func TestVectors(t *testing.T) {
	raw, err := os.ReadFile("../vectors/lombokcliparse-vectors-v1.json")
	if err != nil {
		t.Fatal(err)
	}
	var doc struct{ Cases []vcase }
	if err := json.Unmarshal(raw, &doc); err != nil {
		t.Fatal(err)
	}
	if len(doc.Cases) < 100 {
		t.Fatalf("only %d cases", len(doc.Cases))
	}
	skipped := 0
	for _, c := range doc.Cases {
		app, ok := build(c.App)
		if !ok {
			skipped++
			continue
		}
		env := func(k string) (string, bool) { v, ok := c.Env[k]; return v, ok }
		m, err := app.ParseWithEnv(c.Argv, env)
		var got any
		var pe *ParseError
		switch {
		case err == nil:
			got = map[string]any{"matches": encode(m)}
		case errors.As(err, &pe) && pe.Code == "HELP":
			got = map[string]any{"help": pe.Text}
		case errors.As(err, &pe) && pe.Code == "VERSION":
			got = map[string]any{"version": pe.Text}
		case errors.As(err, &pe):
			e := map[string]any{"code": pe.Code, "arg": pe.Arg, "message": pe.Error()}
			if pe.Code == "INVALID_VALUE" {
				e["value"] = pe.Value
			}
			got = map[string]any{"error": e}
		default:
			t.Fatalf("%s: unexpected error %v", c.ID, err)
		}
		// round-trip through JSON so types match the decoded expectation
		b, _ := json.Marshal(got)
		var norm any
		_ = json.Unmarshal(b, &norm)
		if !reflect.DeepEqual(norm, c.Expected) {
			w, _ := json.Marshal(c.Expected)
			t.Errorf("%s:\n got %s\nwant %s", c.ID, b, w)
		}
	}
	if skipped > 1 {
		t.Fatalf("%d cases could not be expressed in Go", skipped)
	}
}
