# Changelog

All notable changes to **LombokCLIParse** are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

## [0.2.0] — 2026-10-02

Brings the library in line with the Lombok Ecosystem v3.6 standards: one
normative specification, shared vectors executed by all five ports, and
claims that match the code. Behaviour changes in every port (0.x release).

### Added
- `docs/SPEC_LombokCLIParse_v0.2.0.md`: definition rules, value grammar, token-by-token parsing, help layout, error messages.
- `vectors/lombokcliparse-vectors-v1.json`: 134 cases (parse results, errors with message, help and version text) from an independent Python reference; runners in Rust, TypeScript, Python, Go and PHP.
- `--version` when a version is set; `run()` in every port (help/version to stdout with exit 0, errors to stderr with exit 2).
- `parse_with_env` / `parseWithEnv` / `ParseWithEnv` with an explicit environment, for tests and embedding.
- Definition validation (`INVALID_DEFINITION`): names, shorts, reserved names, duplicates, defaults, positional order.
- Error codes `UNKNOWN_ARGUMENT`, `MISSING_VALUE`, `INVALID_VALUE`, `MISSING_REQUIRED`, `UNEXPECTED_ARGUMENT`, `UNKNOWN_SUBCOMMAND`, `FLAG_TAKES_NO_VALUE` with the argument and rejected value.
- `-c=value` short form; bool options; `get_bool` also reads bool options.
- Ten standard documents under `docs/`, `scripts/lombok-doctor.sh`, CI for all five ports with coverage thresholds.

### Changed
- Help text has one layout in every port: per-section column width, `<TYPE>` placeholders, `[default: …]` and `[env: …]`, `--version` row. Options and flags are listed in definition order.
- Values follow one grammar in every port (integers within ±(2^53 − 1), decimal floats, ASCII booleans); 0.1 used each language's own parser (for example Python accepted `1_000`).
- Go module path is now `github.com/codinglombok/lombokcliparse/go`.
- Python: `ArgType` values are `"string"`, `"int"`, `"float"`, `"bool"`; `ParseError` has `code`, `arg`, `value`, `text`.

### Fixed
- `--help` called `exit` inside the library (Rust `process::exit`, others similar), which made it impossible to embed or test.
- Negative numbers (`-5`, `-.5`) were treated as unknown short options.
- `--flag=value` silently ignored the value.
- Invalid default and environment values were silently ignored.
- Extra positional arguments were silently collected instead of reported.
- Help columns ran together when a name was longer than 16 characters.
- Values and help were inconsistent between ports.

### Removed
- README claims that tied the library to one application framework.

## [0.1.0] — 2026-09-24

Initial version in Rust, TypeScript, Python, Go and PHP (not published to any registry).
