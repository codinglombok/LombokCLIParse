// Package lombokcliparse parses command lines: positional arguments, flags,
// typed options, subcommands, environment fallback, and generated help. The
// same input gives the same result, error message and help text in the Rust,
// TypeScript, Python and PHP ports (docs/SPEC_LombokCLIParse_v0.2.0.md).
package lombokcliparse

import (
	"fmt"
	"math"
	"os"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"unicode/utf8"
)

// ArgType is the type of a positional argument or option (SPEC section 3).
type ArgType string

// Argument types.
const (
	TypeStr   ArgType = "string"
	TypeInt   ArgType = "int"
	TypeFloat ArgType = "float"
	TypeBool  ArgType = "bool"
)

// MaxSafeInteger is the largest value accepted by TypeInt (2^53 - 1).
const MaxSafeInteger = 1<<53 - 1

// Value is a parsed value; Type tells which field is set.
type Value struct {
	Type  ArgType
	Str   string
	Int   int64
	Float float64
	Bool  bool
}

// ParseError reports why parsing stopped. HELP and VERSION are not failures:
// Text holds what to print (use App.Run to handle them).
type ParseError struct {
	Code   string // e.g. "UNKNOWN_ARGUMENT", "HELP"
	Arg    string // the argument concerned; "" for HELP and VERSION
	Value  string // the rejected text for INVALID_VALUE
	Reason string // the broken rule for INVALID_DEFINITION
	Text   string // help or version text
}

// Error returns "CODE: message" (SPEC section 6), or the help/version text.
func (e *ParseError) Error() string {
	var m string
	switch e.Code {
	case "HELP", "VERSION":
		return e.Text
	case "UNKNOWN_ARGUMENT":
		m = "unknown argument '" + e.Arg + "'"
	case "MISSING_VALUE":
		m = "missing value for '" + e.Arg + "'"
	case "INVALID_VALUE":
		m = "invalid value '" + e.Value + "' for '" + e.Arg + "'"
	case "MISSING_REQUIRED":
		m = "missing required argument '" + e.Arg + "'"
	case "UNEXPECTED_ARGUMENT":
		m = "unexpected argument '" + e.Arg + "'"
	case "UNKNOWN_SUBCOMMAND":
		m = "unknown subcommand '" + e.Arg + "'"
	case "FLAG_TAKES_NO_VALUE":
		m = "flag '" + e.Arg + "' does not take a value"
	case "INVALID_DEFINITION":
		m = e.Reason + ": '" + e.Arg + "'"
	}
	return e.Code + ": " + m
}

// IsInfo reports HELP and VERSION, which should exit with status 0.
func (e *ParseError) IsInfo() bool { return e.Code == "HELP" || e.Code == "VERSION" }

var (
	intRE   = regexp.MustCompile(`^[+-]?[0-9]+$`)
	floatRE = regexp.MustCompile(`^[+-]?([0-9]+(\.[0-9]*)?|\.[0-9]+)([eE][+-]?[0-9]+)?$`)
	nameRE  = regexp.MustCompile(`^[A-Za-z0-9][A-Za-z0-9_-]*$`)
	bools   = map[string]bool{"true": true, "1": true, "yes": true, "on": true, "false": false, "0": false, "no": false, "off": false}
)

func isASCII(s string) bool {
	for i := 0; i < len(s); i++ {
		if s[i] >= 0x80 {
			return false
		}
	}
	return true
}

// ParseValue parses raw as t; ok is false when the text is not valid for the type.
func ParseValue(t ArgType, raw string) (v Value, ok bool) {
	v.Type = t
	switch t {
	case TypeStr:
		v.Str = raw
		return v, true
	case TypeInt:
		if !intRE.MatchString(raw) || len(strings.TrimLeft(strings.TrimLeft(raw, "+-"), "0")) > 16 {
			return v, false
		}
		n, err := strconv.ParseInt(strings.TrimPrefix(raw, "+"), 10, 64)
		if err != nil || n > MaxSafeInteger || n < -MaxSafeInteger {
			return v, false
		}
		v.Int = n
		return v, true
	case TypeFloat:
		if !floatRE.MatchString(raw) {
			return v, false
		}
		f, _ := strconv.ParseFloat(raw, 64) // ErrRange on overflow gives ±Inf, rejected below
		if math.IsInf(f, 0) {
			return v, false
		}
		v.Float = f
		return v, true
	case TypeBool:
		if !isASCII(raw) {
			return v, false
		}
		b, found := bools[strings.ToLower(raw)]
		v.Bool = b
		return v, found
	}
	return v, false
}

// Matches is the result of a successful parse.
type Matches struct {
	values  map[string]Value
	flags   map[string]bool
	subName string
	sub     *Matches
	rest    []string
}

func newMatches() *Matches {
	return &Matches{values: map[string]Value{}, flags: map[string]bool{}, rest: []string{}}
}

// GetStr returns a string value.
func (m *Matches) GetStr(name string) (string, bool) {
	v, ok := m.values[name]
	return v.Str, ok && v.Type == TypeStr
}

// GetInt returns an int value.
func (m *Matches) GetInt(name string) (int64, bool) {
	v, ok := m.values[name]
	return v.Int, ok && v.Type == TypeInt
}

// GetFloat returns a float value.
func (m *Matches) GetFloat(name string) (float64, bool) {
	v, ok := m.values[name]
	return v.Float, ok && v.Type == TypeFloat
}

// GetBool reports whether the flag was given or a bool option is true.
func (m *Matches) GetBool(name string) bool {
	v, ok := m.values[name]
	return m.flags[name] || (ok && v.Type == TypeBool && v.Bool)
}

// Get returns any value by name.
func (m *Matches) Get(name string) (Value, bool) {
	v, ok := m.values[name]
	return v, ok
}

// Names returns the names of all values, sorted.
func (m *Matches) Names() []string {
	out := make([]string, 0, len(m.values))
	for k := range m.values {
		out = append(out, k)
	}
	sort.Strings(out)
	return out
}

// Flags returns the names of the flags that were given, sorted.
func (m *Matches) Flags() []string {
	out := make([]string, 0, len(m.flags))
	for k := range m.flags {
		out = append(out, k)
	}
	sort.Strings(out)
	return out
}

// Subcommand returns the selected subcommand and its matches.
func (m *Matches) Subcommand() (string, *Matches, bool) {
	return m.subName, m.sub, m.sub != nil
}

// Rest returns tokens after "--" that did not fill a positional argument.
func (m *Matches) Rest() []string { return m.rest }

type positional struct {
	name, help string
	t          ArgType
	required   bool
}

type named struct {
	isFlag             bool
	name, help         string
	short              rune // 0 = none
	t                  ArgType
	def, env           string
	hasDefault, hasEnv bool
}

// App is a command-line application or subcommand definition (builder).
type App struct {
	name, description string
	version           string
	hasVersion        bool
	positionals       []positional
	args              []named
	subs              []*App
}

// NewApp creates an app; description may be empty.
func NewApp(name, description string) *App { return &App{name: name, description: description} }

// Version sets the version and enables --version.
func (a *App) Version(v string) *App {
	a.version, a.hasVersion = v, true
	return a
}

// Positional adds a positional argument (filled in definition order).
func (a *App) Positional(name, help string, t ArgType, required bool) *App {
	a.positionals = append(a.positionals, positional{name, help, t, required})
	return a
}

// Flag adds a boolean flag; short 0 means none.
func (a *App) Flag(name, help string, short rune) *App {
	a.args = append(a.args, named{isFlag: true, name: name, help: help, short: short})
	return a
}

// Option adds an option taking a value; short 0 means none, and an empty
// defaultVal or envVar means none (use OptionFull for an empty default).
func (a *App) Option(name, help string, t ArgType, short rune, defaultVal, envVar string) *App {
	return a.OptionFull(name, help, t, short, defaultVal, defaultVal != "", envVar, envVar != "")
}

// OptionFull is Option with explicit presence of the default and env variable.
func (a *App) OptionFull(name, help string, t ArgType, short rune, def string, hasDefault bool, env string, hasEnv bool) *App {
	a.args = append(a.args, named{name: name, help: help, short: short, t: t, def: def, hasDefault: hasDefault, env: env, hasEnv: hasEnv})
	return a
}

// Sub adds a subcommand. An app with subcommands has no positional arguments.
func (a *App) Sub(sub *App) *App {
	a.subs = append(a.subs, sub)
	return a
}

// Subcommand is the same as Sub.
func (a *App) Subcommand(sub *App) *App { return a.Sub(sub) }

func defErr(arg, reason string) *ParseError {
	return &ParseError{Code: "INVALID_DEFINITION", Arg: arg, Reason: reason}
}

// Validate checks the rules of SPEC section 2.
func (a *App) Validate() error {
	names := map[string]bool{}
	shorts := map[rune]bool{}
	check := func(n string) error {
		switch {
		case !nameRE.MatchString(n):
			return defErr(n, "invalid name")
		case n == "help" || (n == "version" && a.hasVersion):
			return defErr(n, "reserved name")
		case names[n]:
			return defErr(n, "duplicate name")
		}
		names[n] = true
		return nil
	}
	for _, p := range a.positionals {
		if err := check(p.name); err != nil {
			return err
		}
	}
	for _, x := range a.args {
		if err := check(x.name); err != nil {
			return err
		}
		if x.short != 0 {
			if !(x.short >= 'a' && x.short <= 'z' || x.short >= 'A' && x.short <= 'Z') {
				return defErr(string(x.short), "invalid short")
			}
			if shorts[x.short] {
				return defErr(string(x.short), "duplicate short")
			}
			shorts[x.short] = true
		}
		if !x.isFlag && x.hasDefault {
			if _, ok := ParseValue(x.t, x.def); !ok {
				return defErr(x.name, "invalid default")
			}
		}
	}
	seenOptional := false
	for _, p := range a.positionals {
		if p.required && seenOptional {
			return defErr(p.name, "required after optional")
		}
		seenOptional = seenOptional || !p.required
	}
	if len(a.subs) > 0 && len(a.positionals) > 0 {
		return defErr(a.subs[0].name, "positionals with subcommands")
	}
	subNames := map[string]bool{}
	for _, s := range a.subs {
		if !nameRE.MatchString(s.name) {
			return defErr(s.name, "invalid name")
		}
		if subNames[s.name] {
			return defErr(s.name, "duplicate name")
		}
		subNames[s.name] = true
		if err := s.Validate(); err != nil {
			return err
		}
	}
	return nil
}

func joinParts(parts ...string) string {
	out := make([]string, 0, len(parts))
	for _, p := range parts {
		if p != "" {
			out = append(out, p)
		}
	}
	return strings.Join(out, " ")
}

func section(b *strings.Builder, title string, rows [][2]string) {
	width := 0
	for _, r := range rows {
		if n := utf8.RuneCountInString(r[0]); n > width {
			width = n
		}
	}
	b.WriteString(title + ":\n")
	for _, r := range rows {
		b.WriteString("    " + r[0])
		if r[1] != "" {
			b.WriteString(strings.Repeat(" ", width-utf8.RuneCountInString(r[0])+2) + r[1])
		}
		b.WriteString("\n")
	}
}

var placeholder = map[ArgType]string{TypeStr: "<VALUE>", TypeInt: "<INT>", TypeFloat: "<FLOAT>", TypeBool: "<BOOL>"}

// Help returns the help text (SPEC section 5) as shown for --help.
func (a *App) Help() string { return a.helpAt(a.name) }

func (a *App) helpAt(path string) string {
	var b strings.Builder
	b.WriteString(a.name)
	if a.hasVersion {
		b.WriteString(" " + a.version)
	}
	b.WriteString("\n")
	if a.description != "" {
		b.WriteString(a.description + "\n")
	}
	b.WriteString("\nUSAGE:\n    " + path + " [OPTIONS]")
	if len(a.subs) > 0 {
		b.WriteString(" <COMMAND>")
	}
	for _, p := range a.positionals {
		n := strings.ToUpper(p.name)
		if p.required {
			b.WriteString(" <" + n + ">")
		} else {
			b.WriteString(" [" + n + "]")
		}
	}
	b.WriteString("\n")
	if len(a.positionals) > 0 {
		rows := make([][2]string, len(a.positionals))
		for i, p := range a.positionals {
			req := ""
			if p.required {
				req = "(required)"
			}
			rows[i] = [2]string{"<" + strings.ToUpper(p.name) + ">", joinParts(p.help, req)}
		}
		b.WriteString("\n")
		section(&b, "ARGS", rows)
	}
	if len(a.subs) > 0 {
		rows := make([][2]string, len(a.subs))
		for i, s := range a.subs {
			rows[i] = [2]string{s.name, s.description}
		}
		b.WriteString("\n")
		section(&b, "COMMANDS", rows)
	}
	rows := make([][2]string, 0, len(a.args)+2)
	for _, x := range a.args {
		left := "    --" + x.name
		if x.short != 0 {
			left = "-" + string(x.short) + ", --" + x.name
		}
		if x.isFlag {
			rows = append(rows, [2]string{left, x.help})
			continue
		}
		d, e := "", ""
		if x.hasDefault {
			d = "[default: " + x.def + "]"
		}
		if x.hasEnv {
			e = "[env: " + x.env + "]"
		}
		rows = append(rows, [2]string{left + " " + placeholder[x.t], joinParts(x.help, d, e)})
	}
	rows = append(rows, [2]string{"    --help", "Print help"})
	if a.hasVersion {
		rows = append(rows, [2]string{"    --version", "Print version"})
	}
	b.WriteString("\n")
	section(&b, "OPTIONS", rows)
	return b.String()
}

// EnvLookup returns an environment variable and whether it is set.
type EnvLookup func(name string) (string, bool)

// Parse parses a full command line (args[0] is the program name) with the
// process environment for fallback values.
func (a *App) Parse(args []string) (*Matches, error) {
	if len(args) > 0 {
		args = args[1:]
	}
	return a.ParseWithEnv(args, os.LookupEnv)
}

// ParseWithEnv parses tokens (without the program name) with an explicit
// environment lookup; nil means no environment.
func (a *App) ParseWithEnv(tokens []string, env EnvLookup) (*Matches, error) {
	if err := a.Validate(); err != nil {
		return nil, err
	}
	if env == nil {
		env = func(string) (string, bool) { return "", false }
	}
	m, err := a.parseTokens(tokens, env, a.name)
	if err != nil {
		return nil, err
	}
	return m, nil
}

// ParseEnv parses os.Args.
func (a *App) ParseEnv() (*Matches, error) { return a.Parse(os.Args) }

// Run parses os.Args; it prints help or version and exits with 0, or prints
// the error and exits with 2.
func (a *App) Run() *Matches {
	m, err := a.ParseEnv()
	if err == nil {
		return m
	}
	if pe, ok := err.(*ParseError); ok && pe.IsInfo() {
		fmt.Print(pe.Text)
		os.Exit(0)
	}
	fmt.Fprintf(os.Stderr, "error: %v\n", err)
	os.Exit(2)
	return nil
}

func (a *App) set(m *Matches, x *named, raw, arg string) error {
	v, ok := ParseValue(x.t, raw)
	if !ok {
		return &ParseError{Code: "INVALID_VALUE", Arg: arg, Value: raw}
	}
	m.values[x.name] = v
	return nil
}

func (a *App) findLong(name string) *named {
	for i := range a.args {
		if a.args[i].name == name {
			return &a.args[i]
		}
	}
	return nil
}

func (a *App) findShort(c rune) *named {
	for i := range a.args {
		if a.args[i].short == c {
			return &a.args[i]
		}
	}
	return nil
}

func (a *App) parseTokens(tokens []string, env EnvLookup, path string) (*Matches, error) {
	m := newMatches()
	posIdx, i, afterDD := 0, 0, false
	for i < len(tokens) {
		tok := tokens[i]
		i++
		if !afterDD {
			if tok == "--" {
				afterDD = true
				continue
			}
			if tok == "--help" {
				return nil, &ParseError{Code: "HELP", Text: a.helpAt(path)}
			}
			if tok == "--version" && a.hasVersion {
				return nil, &ParseError{Code: "VERSION", Text: a.name + " " + a.version + "\n"}
			}
			if strings.HasPrefix(tok, "--") {
				name, inline, hasInline := strings.Cut(tok[2:], "=")
				arg := "--" + name
				x := a.findLong(name)
				if x == nil {
					return nil, &ParseError{Code: "UNKNOWN_ARGUMENT", Arg: arg}
				}
				if x.isFlag {
					if hasInline {
						return nil, &ParseError{Code: "FLAG_TAKES_NO_VALUE", Arg: arg}
					}
					m.flags[x.name] = true
					continue
				}
				if !hasInline {
					if i >= len(tokens) {
						return nil, &ParseError{Code: "MISSING_VALUE", Arg: arg}
					}
					inline = tokens[i]
					i++
				}
				if err := a.set(m, x, inline, arg); err != nil {
					return nil, err
				}
				continue
			}
			if len(tok) > 1 && tok[0] == '-' && !strings.ContainsRune("0123456789.", rune(tok[1])) {
				cluster := []rune(tok[1:])
				for k := 0; k < len(cluster); k++ {
					c := cluster[k]
					arg := "-" + string(c)
					x := a.findShort(c)
					if x == nil {
						return nil, &ParseError{Code: "UNKNOWN_ARGUMENT", Arg: arg}
					}
					if x.isFlag {
						m.flags[x.name] = true
						continue
					}
					raw := string(cluster[k+1:])
					if strings.HasPrefix(raw, "=") {
						raw = raw[1:]
					} else if raw == "" {
						if i >= len(tokens) {
							return nil, &ParseError{Code: "MISSING_VALUE", Arg: arg}
						}
						raw = tokens[i]
						i++
					}
					if err := a.set(m, x, raw, arg); err != nil {
						return nil, err
					}
					break
				}
				continue
			}
		}
		if !afterDD && len(a.subs) > 0 {
			var sub *App
			for _, s := range a.subs {
				if s.name == tok {
					sub = s
				}
			}
			if sub == nil {
				return nil, &ParseError{Code: "UNKNOWN_SUBCOMMAND", Arg: tok}
			}
			sm, err := sub.parseTokens(tokens[i:], env, path+" "+tok)
			if err != nil {
				return nil, err
			}
			m.subName, m.sub = tok, sm
			break
		}
		if posIdx < len(a.positionals) {
			p := a.positionals[posIdx]
			v, ok := ParseValue(p.t, tok)
			if !ok {
				return nil, &ParseError{Code: "INVALID_VALUE", Arg: p.name, Value: tok}
			}
			m.values[p.name] = v
			posIdx++
		} else if afterDD {
			m.rest = append(m.rest, tok)
		} else {
			return nil, &ParseError{Code: "UNEXPECTED_ARGUMENT", Arg: tok}
		}
	}
	for idx := range a.args {
		x := &a.args[idx]
		if x.isFlag {
			continue
		}
		if _, set := m.values[x.name]; set {
			continue
		}
		arg := "--" + x.name
		if v, ok := env(x.env); x.hasEnv && ok {
			if err := a.set(m, x, v, arg); err != nil {
				return nil, err
			}
		} else if x.hasDefault {
			if err := a.set(m, x, x.def, arg); err != nil {
				return nil, err
			}
		}
	}
	for _, p := range a.positionals {
		if _, ok := m.values[p.name]; p.required && !ok {
			return nil, &ParseError{Code: "MISSING_REQUIRED", Arg: p.name}
		}
	}
	return m, nil
}
