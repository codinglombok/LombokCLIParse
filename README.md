# LombokCLIParse

> Command-line parser with positional arguments, flags, typed options, subcommands, environment fallback, and generated help. The same command line gives the same result, error message, and help text in Rust, TypeScript, Python, Go, and PHP. Zero runtime dependencies.

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![CI](https://github.com/codinglombok/LombokCLIParse/actions/workflows/ci.yml/badge.svg)](https://github.com/codinglombok/LombokCLIParse/actions/workflows/ci.yml)
[![Vectors](https://img.shields.io/badge/shared%20vectors-134%20x%205%20ports-success)](vectors/)
[![Lombok Ecosystem](https://img.shields.io/badge/Lombok-Ecosystem-2e7d5b?logo=github)](https://github.com/codinglombok)

Part of the [Lombok Ecosystem](https://github.com/codinglombok).

## Mengapa library ini? (Why this library?)

- **One behaviour, five languages.** A tool rewritten from Python to Go, or shipped as both an npm CLI and a Rust binary, accepts exactly the same command lines and prints the same help and errors. The rules are written down ([SPEC](docs/SPEC_LombokCLIParse_v0.2.0.md)) and 134 shared cases, including help text byte for byte, run in CI for every port.
- **Predictable edge cases.** Negative numbers are values, not options; `--name value` takes the next token verbatim; `--` ends options; `-p=3000`, `-p3000` and `-vp 3000` all work; `--flag=x` is an error instead of being ignored.
- **Library-friendly.** Parsing never prints or exits: `--help` and `--version` come back as results, errors carry a stable code, the argument, and the rejected value. `run()` gives the usual CLI behaviour (exit 0 for help, 2 for errors) when you want it.
- **Strict, shared value grammar.** Integers within ±(2^53 − 1), decimal floats, and `true/false/yes/no/on/off/1/0` booleans are parsed the same way everywhere, not by each language's lenient built-ins.

## Installation

| Language | Package | Status |
|---|---|---|
| Rust | `lombokcliparse` (crates.io) | not yet published |
| TypeScript / JavaScript | `lombokcliparse` (npm) | not yet published |
| Python | `lombokcliparse` (PyPI) | not yet published |
| Go | `github.com/codinglombok/lombokcliparse/go` | tag `go/v0.2.0` on release |
| PHP | `codinglombok/lombokcliparse` (Packagist) | needs a split repository first |

## Quick start

### Rust

```rust
use lombokcliparse::{App, ArgType};

let app = App::new("myapp", "My application")
    .version("1.0.0")
    .positional("input", "Input file", ArgType::Str, true)
    .flag("verbose", "Verbose output", Some('v'))
    .option("port", "Port", ArgType::Int, Some('p'), Some("8080"), Some("MYAPP_PORT"));

let m = app.run(); // prints help/version and exits 0, or an error and exits 2
let port = m.get_int("port").unwrap();
```

### TypeScript

```ts
import { App, ArgType, ParseError } from 'lombokcliparse';

const app = new App('myapp', 'My application')
    .version('1.0.0')
    .positional('input', 'Input file', ArgType.Str, true)
    .flag('verbose', 'Verbose output', 'v')
    .option('port', 'Port', ArgType.Int, 'p', '8080');

const m = app.run();               // or app.parse(process.argv.slice(1)) and catch ParseError
m.getInt('port');                  // 8080
```

### Python

```python
from lombokcliparse import App, ArgType

app = (App("myapp", "My application").version("1.0.0")
       .positional("input", "Input file", ArgType.STR, required=True)
       .flag("verbose", "Verbose output", short="v")
       .option("port", "Port", ArgType.INT, short="p", default="8080"))
m = app.run()
m.get_int("port")
```

### Go

```go
import cli "github.com/codinglombok/lombokcliparse/go"

app := cli.NewApp("myapp", "My application").Version("1.0.0").
    Positional("input", "Input file", cli.TypeStr, true).
    Flag("verbose", "Verbose output", 'v').
    Option("port", "Port", cli.TypeInt, 'p', "8080", "")
m := app.Run()
port, _ := m.GetInt("port")
```

### PHP

```php
use LombokCLIParse\App;
use LombokCLIParse\ArgType;

$m = (new App('myapp', 'My application'))->version('1.0.0')
    ->positional('input', 'Input file', ArgType::STR, true)
    ->flag('verbose', 'Verbose output', 'v')
    ->option('port', 'Port', ArgType::INT, 'p', '8080')
    ->run();
$m->getInt('port');
```

### Generated help

```
myapp 1.0.0
My application

USAGE:
    myapp [OPTIONS] <INPUT>

ARGS:
    <INPUT>  Input file (required)

OPTIONS:
    -v, --verbose     Verbose output
    -p, --port <INT>  Port [default: 8080]
        --help        Print help
        --version     Print version
```

## Subcommands

```rust
let app = App::new("cli", "Data tool")
    .flag("verbose", "Verbose", Some('v'))
    .subcommand(App::new("ingest", "Ingest data").positional("path", "Data path", ArgType::Str, true))
    .subcommand(App::new("query", "Query data").positional("text", "Query text", ArgType::Str, true));

let m = app.parse_from(&["cli", "-v", "ingest", "data/"])?;
if let Some(("ingest", sub)) = m.subcommand() { /* sub.get_str("path") */ }
```

Options of the parent come before the subcommand name; `cli query --help` shows help for `cli query`.

## Known limitations

No option groups or mutually exclusive options, no repeated-option lists (the last value wins), no counted flags (`-vvv`), no shell completion, no localized messages yet. See [docs/full_summary_project_LombokCLIParse_v0.2.0.md](docs/full_summary_project_LombokCLIParse_v0.2.0.md#2-batasan-yang-diketahui).

## Upgrading from 0.1.0

`--help` no longer exits the process from inside the library, negative numbers are values, invalid defaults and environment values are errors, extra positional arguments are errors unless they follow `--`, and the Go module path is now lowercase. See [CHANGELOG.md](CHANGELOG.md).

## Development

```bash
cd rust && cargo test && cargo clippy --all-targets -- -D warnings
cd typescript && npm ci && npm run coverage
cd python && python -m pytest
cd go && go test ./...
cd php && php tests/run.php
python3 vectors/build_vectors.py && bash scripts/lombok-doctor.sh LombokCLIParse
```

## License

Apache-2.0. See [LICENSE](LICENSE).
