// Package lombokcliparse provides a lightweight CLI argument parser.
//
// Positional args, flags, options, subcommands, auto-help,
// env fallback, type parsing. Zero dependencies.
package lombokcliparse

import (
	"fmt"
	"os"
	"sort"
	"strconv"
	"strings"
)

// ArgType defines the type of an argument value.
type ArgType int

const (
	TypeStr   ArgType = iota
	TypeInt
	TypeBool
	TypeFloat
)

// Value holds a parsed argument value.
type Value struct {
	Str   string
	Int   int64
	Float float64
	Bool  bool
	Type  ArgType
}

// ParseError represents an argument parsing error.
type ParseError struct {
	Kind    string
	Message string
}

func (e *ParseError) Error() string { return e.Message }

type positional struct {
	Name     string
	Help     string
	ArgType  ArgType
	Required bool
}

type flag struct {
	Name  string
	Help  string
	Short rune
}

type option struct {
	Name    string
	Help    string
	ArgType ArgType
	Short   rune
	Default string
	EnvVar  string
}

// Matches holds parsed argument results.
type Matches struct {
	values     map[string]Value
	flags      map[string]bool
	subcommand *struct {
		Name    string
		Matches *Matches
	}
	rest []string
}

// GetStr returns a string value by name.
func (m *Matches) GetStr(name string) (string, bool) {
	v, ok := m.values[name]
	if !ok || v.Type != TypeStr {
		return "", false
	}
	return v.Str, true
}

// GetInt returns an integer value by name.
func (m *Matches) GetInt(name string) (int64, bool) {
	v, ok := m.values[name]
	if !ok || v.Type != TypeInt {
		return 0, false
	}
	return v.Int, true
}

// GetFloat returns a float value by name.
func (m *Matches) GetFloat(name string) (float64, bool) {
	v, ok := m.values[name]
	if !ok || v.Type != TypeFloat {
		return 0, false
	}
	return v.Float, true
}

// GetBool returns whether a flag is set.
func (m *Matches) GetBool(name string) bool {
	return m.flags[name]
}

// Get returns the raw Value.
func (m *Matches) Get(name string) (Value, bool) {
	v, ok := m.values[name]
	return v, ok
}

// Subcommand returns the matched subcommand name and matches.
func (m *Matches) Subcommand() (string, *Matches, bool) {
	if m.subcommand == nil {
		return "", nil, false
	}
	return m.subcommand.Name, m.subcommand.Matches, true
}

// Rest returns remaining args after --.
func (m *Matches) Rest() []string {
	return m.rest
}

// App is the CLI application builder.
type App struct {
	name        string
	description string
	version     string
	positionals []positional
	flags       []flag
	options     []option
	subcommands map[string]*App
}

// NewApp creates a new CLI app.
func NewApp(name, description string) *App {
	return &App{
		name:        name,
		description: description,
		subcommands: make(map[string]*App),
	}
}

// Version sets the version string.
func (a *App) Version(v string) *App {
	a.version = v
	return a
}

// Positional adds a positional argument.
func (a *App) Positional(name, help string, argType ArgType, required bool) *App {
	a.positionals = append(a.positionals, positional{name, help, argType, required})
	return a
}

// Flag adds a boolean flag.
func (a *App) Flag(name, help string, short rune) *App {
	a.flags = append(a.flags, flag{name, help, short})
	return a
}

// Option adds a key-value option.
func (a *App) Option(name, help string, argType ArgType, short rune, defaultVal, envVar string) *App {
	a.options = append(a.options, option{name, help, argType, short, defaultVal, envVar})
	return a
}

// Sub adds a subcommand.
func (a *App) Sub(sub *App) *App {
	a.subcommands[sub.name] = sub
	return a
}

// Help generates the help text.
func (a *App) Help() string {
	var b strings.Builder
	b.WriteString(a.name)
	if a.version != "" {
		b.WriteString(" " + a.version)
	}
	b.WriteString("\n" + a.description + "\n\n")

	b.WriteString("USAGE:\n    " + a.name)
	if len(a.subcommands) > 0 {
		b.WriteString(" <COMMAND>")
	}
	if len(a.options) > 0 || len(a.flags) > 0 {
		b.WriteString(" [OPTIONS]")
	}
	for _, p := range a.positionals {
		if p.Required {
			b.WriteString(fmt.Sprintf(" <%s>", strings.ToUpper(p.Name)))
		} else {
			b.WriteString(fmt.Sprintf(" [%s]", strings.ToUpper(p.Name)))
		}
	}
	b.WriteString("\n\n")

	if len(a.positionals) > 0 {
		b.WriteString("ARGS:\n")
		for _, p := range a.positionals {
			req := ""
			if p.Required {
				req = " (required)"
			}
			b.WriteString(fmt.Sprintf("    <%s>    %s%s\n", strings.ToUpper(p.Name), p.Help, req))
		}
		b.WriteString("\n")
	}

	if len(a.subcommands) > 0 {
		b.WriteString("COMMANDS:\n")
		names := make([]string, 0, len(a.subcommands))
		for n := range a.subcommands {
			names = append(names, n)
		}
		sort.Strings(names)
		for _, n := range names {
			sub := a.subcommands[n]
			b.WriteString(fmt.Sprintf("    %-16s%s\n", n, sub.description))
		}
		b.WriteString("\n")
	}

	if len(a.flags) > 0 || len(a.options) > 0 {
		b.WriteString("OPTIONS:\n")
		for _, f := range a.flags {
			s := "    "
			if f.Short != 0 {
				s = fmt.Sprintf("-%c, ", f.Short)
			}
			b.WriteString(fmt.Sprintf("    %s--%-16s%s\n", s, f.Name, f.Help))
		}
		for _, o := range a.options {
			s := "    "
			if o.Short != 0 {
				s = fmt.Sprintf("-%c, ", o.Short)
			}
			def := ""
			if o.Default != "" {
				def = fmt.Sprintf(" [default: %s]", o.Default)
			}
			env := ""
			if o.EnvVar != "" {
				env = fmt.Sprintf(" [env: %s]", o.EnvVar)
			}
			b.WriteString(fmt.Sprintf("    %s--%-16s%s%s%s\n", s, o.Name, o.Help, def, env))
		}
		b.WriteString("        --help            Show this help message\n")
	}

	return b.String()
}

// Parse parses args (first element = program name, skipped).
func (a *App) Parse(args []string) (*Matches, error) {
	if len(args) == 0 {
		return a.parseSlice(nil)
	}
	return a.parseSlice(args[1:])
}

// ParseEnv parses from os.Args.
func (a *App) ParseEnv() (*Matches, error) {
	return a.Parse(os.Args)
}

func (a *App) parseSlice(args []string) (*Matches, error) {
	m := &Matches{
		values: make(map[string]Value),
		flags:  make(map[string]bool),
	}
	posIdx := 0
	i := 0
	afterDD := false

	for i < len(args) {
		arg := args[i]

		if afterDD {
			m.rest = append(m.rest, arg)
			i++
			continue
		}

		if arg == "--" {
			afterDD = true
			i++
			continue
		}

		// --name=value or --name value
		if strings.HasPrefix(arg, "--") {
			rest := arg[2:]
			if rest == "help" {
				fmt.Print(a.Help())
				os.Exit(0)
			}

			var name, inlineVal string
			hasInline := false
			if eq := strings.Index(rest, "="); eq != -1 {
				name = rest[:eq]
				inlineVal = rest[eq+1:]
				hasInline = true
			} else {
				name = rest
			}

			// Flag?
			if fd := a.findFlag(name); fd != nil {
				m.flags[name] = true
				i++
				continue
			}

			// Option?
			if od := a.findOpt(name); od != nil {
				var valStr string
				if hasInline {
					valStr = inlineVal
				} else {
					i++
					if i >= len(args) {
						return nil, &ParseError{"missing_value", fmt.Sprintf("missing value for: --%s", name)}
					}
					valStr = args[i]
				}
				v, err := parseValue(od.Name, valStr, od.ArgType)
				if err != nil {
					return nil, err
				}
				m.values[od.Name] = v
				i++
				continue
			}

			return nil, &ParseError{"unknown_arg", fmt.Sprintf("unknown argument: --%s", name)}
		}

		// Short: -v, -p value, -vn
		if strings.HasPrefix(arg, "-") && len(arg) > 1 {
			chars := []rune(arg[1:])
			ci := 0
			for ci < len(chars) {
				ch := chars[ci]

				if fd := a.findFlagShort(ch); fd != nil {
					m.flags[fd.Name] = true
					ci++
					continue
				}

				if od := a.findOptShort(ch); od != nil {
					var valStr string
					if ci+1 < len(chars) {
						valStr = string(chars[ci+1:])
					} else {
						i++
						if i >= len(args) {
							return nil, &ParseError{"missing_value", fmt.Sprintf("missing value for: %s", od.Name)}
						}
						valStr = args[i]
					}
					v, err := parseValue(od.Name, valStr, od.ArgType)
					if err != nil {
						return nil, err
					}
					m.values[od.Name] = v
					goto nextArg
				}

				return nil, &ParseError{"unknown_arg", fmt.Sprintf("unknown argument: -%c", ch)}
			}
		nextArg:
			i++
			continue
		}

		// Subcommand?
		if posIdx == 0 {
			if sub, ok := a.subcommands[arg]; ok {
				subM, err := sub.parseSlice(args[i+1:])
				if err != nil {
					return nil, err
				}
				m.subcommand = &struct {
					Name    string
					Matches *Matches
				}{arg, subM}
				return m, nil
			}
		}

		// Positional
		if posIdx < len(a.positionals) {
			p := a.positionals[posIdx]
			v, err := parseValue(p.Name, arg, p.ArgType)
			if err != nil {
				return nil, err
			}
			m.values[p.Name] = v
			posIdx++
		} else {
			m.rest = append(m.rest, arg)
		}

		i++
	}

	// Defaults and env vars
	for _, o := range a.options {
		if _, exists := m.values[o.Name]; !exists {
			if o.EnvVar != "" {
				if envVal, ok := os.LookupEnv(o.EnvVar); ok {
					if v, err := parseValue(o.Name, envVal, o.ArgType); err == nil {
						m.values[o.Name] = v
						continue
					}
				}
			}
			if o.Default != "" {
				if v, err := parseValue(o.Name, o.Default, o.ArgType); err == nil {
					m.values[o.Name] = v
				}
			}
		}
	}

	// Required check
	for _, p := range a.positionals {
		if p.Required {
			if _, exists := m.values[p.Name]; !exists {
				return nil, &ParseError{"missing_required", fmt.Sprintf("missing required argument: %s", p.Name)}
			}
		}
	}

	return m, nil
}

func (a *App) findFlag(name string) *flag {
	for i := range a.flags {
		if a.flags[i].Name == name {
			return &a.flags[i]
		}
	}
	return nil
}

func (a *App) findFlagShort(ch rune) *flag {
	for i := range a.flags {
		if a.flags[i].Short == ch {
			return &a.flags[i]
		}
	}
	return nil
}

func (a *App) findOpt(name string) *option {
	for i := range a.options {
		if a.options[i].Name == name {
			return &a.options[i]
		}
	}
	return nil
}

func (a *App) findOptShort(ch rune) *option {
	for i := range a.options {
		if a.options[i].Short == ch {
			return &a.options[i]
		}
	}
	return nil
}

func parseValue(name, raw string, ty ArgType) (Value, error) {
	switch ty {
	case TypeStr:
		return Value{Str: raw, Type: TypeStr}, nil
	case TypeInt:
		n, err := strconv.ParseInt(raw, 10, 64)
		if err != nil {
			return Value{}, &ParseError{"invalid_type", fmt.Sprintf("invalid value '%s' for %s", raw, name)}
		}
		return Value{Int: n, Type: TypeInt}, nil
	case TypeFloat:
		f, err := strconv.ParseFloat(raw, 64)
		if err != nil {
			return Value{}, &ParseError{"invalid_type", fmt.Sprintf("invalid value '%s' for %s", raw, name)}
		}
		return Value{Float: f, Type: TypeFloat}, nil
	case TypeBool:
		switch raw {
		case "true", "1", "yes", "on":
			return Value{Bool: true, Type: TypeBool}, nil
		case "false", "0", "no", "off":
			return Value{Bool: false, Type: TypeBool}, nil
		}
		return Value{}, &ParseError{"invalid_type", fmt.Sprintf("invalid value '%s' for %s", raw, name)}
	}
	return Value{}, &ParseError{"invalid_type", "unknown type"}
}
