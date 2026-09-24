# LombokCLIParse

**Lightweight CLI argument parser** — positional args, flags, options, subcommands, auto-help, env fallback, type parsing. Zero dependencies.

Part of the [LombokRAGFrameworks](https://github.com/codinglombok) ecosystem (I8 — Infrastructure Layer).

## Features

- **Positional arguments** — required & optional, with type parsing
- **Boolean flags** — `--verbose`, `-v`, combined `-vn`
- **Key-value options** — `--port 8080`, `--port=8080`, `-p 8080`
- **Subcommands** — nested command trees with independent args
- **Auto-help** — `--help` generates formatted usage text
- **Environment variable fallback** — options read from env when not provided
- **Type parsing** — string, int, float, bool with error reporting
- **Builder pattern** — fluent API across all languages
- **Zero dependencies** — stdlib only in every language

## Languages

| Language   | Package                         | Min Version |
|------------|---------------------------------|-------------|
| Rust       | `lombokcliparse`                | 1.56+       |
| TypeScript | `lombokcliparse`                | ES2022      |
| Python     | `lombokcliparse`                | 3.8+        |
| Go         | `github.com/codinglombok/LombokCLIParse/go` | 1.21+ |
| PHP        | `codinglombok/lombokcliparse`   | 8.1+        |

## Quick Start

### Rust

```rust
use lombokcliparse::{App, ArgType};

let matches = App::new("myapp", "My application")
    .version("1.0.0")
    .positional("input", "Input file", ArgType::Str, true)
    .flag("verbose", "Enable verbose", Some('v'))
    .option("port", "Port", ArgType::Int, Some('p'), Some("8080"), None)
    .parse_from(&["myapp", "data.txt", "--verbose", "-p", "3000"])?;

let input = matches.get_str("input").unwrap();
let port = matches.get_int("port").unwrap();
let verbose = matches.get_bool("verbose");
```

### TypeScript

```typescript
import { App, ArgType } from 'lombokcliparse';

const matches = new App('myapp', 'My application')
    .version('1.0.0')
    .positional('input', 'Input file', ArgType.Str, true)
    .flag('verbose', 'Enable verbose', 'v')
    .option('port', 'Port', ArgType.Int, 'p', '8080')
    .parse(['myapp', 'data.txt', '--verbose', '-p', '3000']);

const input = matches.getStr('input');
const port = matches.getInt('port');
const verbose = matches.getBool('verbose');
```

### Python

```python
from lombokcliparse import App, ArgType

matches = (App("myapp", "My application")
    .version("1.0.0")
    .positional("input", "Input file", ArgType.STR, required=True)
    .flag("verbose", "Enable verbose", short="v")
    .option("port", "Port", ArgType.INT, short="p", default="8080")
    .parse(["myapp", "data.txt", "--verbose", "-p", "3000"]))

input_file = matches.get_str("input")
port = matches.get_int("port")
verbose = matches.get_bool("verbose")
```

### Go

```go
import cli "github.com/codinglombok/LombokCLIParse/go"

app := cli.NewApp("myapp", "My application").
    Version("1.0.0").
    Positional("input", "Input file", cli.TypeStr, true).
    Flag("verbose", "Enable verbose", 'v').
    Option("port", "Port", cli.TypeInt, 'p', "8080", "")

matches, err := app.Parse(os.Args)
input, _ := matches.GetStr("input")
port, _ := matches.GetInt("port")
verbose := matches.GetBool("verbose")
```

### PHP

```php
use LombokCLIParse\App;
use LombokCLIParse\ArgType;

$matches = (new App('myapp', 'My application'))
    ->version('1.0.0')
    ->positional('input', 'Input file', ArgType::STR, required: true)
    ->flag('verbose', 'Enable verbose', short: 'v')
    ->option('port', 'Port', ArgType::INT, short: 'p', default: '8080')
    ->parse(['myapp', 'data.txt', '--verbose', '-p', '3000']);

$input = $matches->getStr('input');
$port = $matches->getInt('port');
$verbose = $matches->getBool('verbose');
```

## Subcommands

```rust
let app = App::new("cli", "CLI tool")
    .flag("verbose", "Verbose", Some('v'))
    .subcommand(
        App::new("ingest", "Ingest data")
            .positional("path", "Data path", ArgType::Str, true)
            .flag("force", "Force overwrite", Some('f'))
    )
    .subcommand(
        App::new("query", "Query data")
            .positional("text", "Query text", ArgType::Str, true)
            .option("limit", "Result limit", ArgType::Int, Some('l'), Some("10"), None)
    );

let matches = app.parse_from(&["cli", "ingest", "data/", "--force"])?;
if let Some((name, sub)) = matches.subcommand() {
    // name = "ingest", sub has the subcommand's matches
}
```

## Auto-Help

Pass `--help` to any app to get formatted usage:

```
testapp 0.1.0
A test application

USAGE:
    testapp [OPTIONS] <INPUT> [OUTPUT]

ARGS:
    <INPUT>    Input file (required)
    <OUTPUT>   Output file

OPTIONS:
    -v, --verbose         Verbose output
    -n, --dry-run         Dry run mode
    -p, --port            Port number [default: 8080]
    -h, --host            Hostname [default: localhost]
    -c, --config          Config path [env: TEST_CONFIG]
    -r, --rate            Rate limit
        --help            Show this help message
```

## Testing

```bash
# Rust
cd rust && cargo test

# TypeScript
cd typescript && npx tsx src/test.ts

# Python
cd python && python tests/test_smoke.py

# Go
cd go && go test ./...

# PHP
cd php && php tests/smoke.php
```

## License

Apache 2.0 — see [LICENSE](LICENSE).
