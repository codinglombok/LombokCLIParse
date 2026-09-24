//! # LombokCLIParse
//!
//! Lightweight CLI argument parser — positional args, flags, options,
//! subcommands, auto-help, env fallback, type parsing.
//!
//! Zero dependencies. Builder pattern API.
//!
//! ## Quick Start
//!
//! ```rust
//! use lombokcliparse::{App, ArgType};
//!
//! let app = App::new("myapp", "My application")
//!     .version("1.0.0")
//!     .positional("input", "Input file path", ArgType::Str, true)
//!     .flag("verbose", "Enable verbose output", Some('v'))
//!     .option("port", "Server port", ArgType::Int, Some('p'), Some("8080"), None)
//!     .option("config", "Config file", ArgType::Str, Some('c'), None, Some("MYAPP_CONFIG"));
//!
//! let args = vec!["myapp", "data.txt", "--verbose", "-p", "3000"];
//! let matches = app.parse_from(&args).unwrap();
//!
//! assert_eq!(matches.get_str("input"), Some("data.txt"));
//! assert!(matches.get_bool("verbose"));
//! assert_eq!(matches.get_int("port"), Some(3000));
//! ```

#[cfg(not(feature = "std"))]
extern crate alloc;

#[cfg(not(feature = "std"))]
use alloc::{format, string::String, string::ToString, vec, vec::Vec};

use core::fmt;

#[cfg(not(feature = "std"))]
use alloc::collections::BTreeMap as Map;
#[cfg(feature = "std")]
use std::collections::HashMap as Map;

// ── Error ──────────────────────────────────────────────────────────

/// Parse error.
#[derive(Debug, Clone, PartialEq)]
pub enum ParseError {
    /// Unknown flag or option.
    UnknownArg(String),
    /// Missing required positional argument.
    MissingRequired(String),
    /// Missing value for an option.
    MissingValue(String),
    /// Type conversion failed.
    InvalidType(String, String),
    /// Unknown subcommand.
    UnknownSubcommand(String),
}

impl fmt::Display for ParseError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::UnknownArg(n) => write!(f, "unknown argument: {n}"),
            Self::MissingRequired(n) => write!(f, "missing required argument: {n}"),
            Self::MissingValue(n) => write!(f, "missing value for: --{n}"),
            Self::InvalidType(n, v) => write!(f, "invalid value '{v}' for {n}"),
            Self::UnknownSubcommand(n) => write!(f, "unknown subcommand: {n}"),
        }
    }
}

#[cfg(feature = "std")]
impl std::error::Error for ParseError {}

// ── Types ──────────────────────────────────────────────────────────

/// Argument value type.
#[derive(Debug, Clone, Copy, PartialEq)]
pub enum ArgType {
    Str,
    Int,
    Bool,
    Float,
}

/// Stored value.
#[derive(Debug, Clone, PartialEq)]
pub enum Value {
    Str(String),
    Int(i64),
    Bool(bool),
    Float(f64),
}

// ── Arg definitions ────────────────────────────────────────────────

#[derive(Debug, Clone)]
struct Positional {
    name: String,
    help: String,
    arg_type: ArgType,
    required: bool,
}

#[derive(Debug, Clone)]
struct Flag {
    name: String,
    help: String,
    short: Option<char>,
}

#[derive(Debug, Clone)]
struct Opt {
    name: String,
    help: String,
    arg_type: ArgType,
    short: Option<char>,
    default: Option<String>,
    env_var: Option<String>,
}

// ── Matches ────────────────────────────────────────────────────────

/// Parsed argument results.
#[derive(Debug, Clone)]
pub struct Matches {
    values: Map<String, Value>,
    flags: Map<String, bool>,
    subcommand: Option<(String, Box<Matches>)>,
    rest: Vec<String>,
}

impl Matches {
    fn new() -> Self {
        Self {
            values: Map::new(),
            flags: Map::new(),
            subcommand: None,
            rest: Vec::new(),
        }
    }

    /// Get a string value by name.
    pub fn get_str(&self, name: &str) -> Option<&str> {
        match self.values.get(name) {
            Some(Value::Str(s)) => Some(s.as_str()),
            _ => None,
        }
    }

    /// Get an integer value by name.
    pub fn get_int(&self, name: &str) -> Option<i64> {
        match self.values.get(name) {
            Some(Value::Int(v)) => Some(*v),
            _ => None,
        }
    }

    /// Get a float value by name.
    pub fn get_float(&self, name: &str) -> Option<f64> {
        match self.values.get(name) {
            Some(Value::Float(v)) => Some(*v),
            _ => None,
        }
    }

    /// Check if a flag was set.
    pub fn get_bool(&self, name: &str) -> bool {
        self.flags.get(name).copied().unwrap_or(false)
    }

    /// Get the raw Value.
    pub fn get(&self, name: &str) -> Option<&Value> {
        self.values.get(name)
    }

    /// Get matched subcommand name and its matches.
    pub fn subcommand(&self) -> Option<(&str, &Matches)> {
        self.subcommand
            .as_ref()
            .map(|(n, m)| (n.as_str(), m.as_ref()))
    }

    /// Remaining unparsed arguments after `--`.
    pub fn rest(&self) -> &[String] {
        &self.rest
    }
}

// ── App (builder) ──────────────────────────────────────────────────

/// CLI application builder.
#[derive(Debug, Clone)]
pub struct App {
    name: String,
    description: String,
    version: Option<String>,
    positionals: Vec<Positional>,
    flags: Vec<Flag>,
    options: Vec<Opt>,
    subcommands: Map<String, App>,
}

impl App {
    /// Create a new CLI app.
    pub fn new(name: &str, description: &str) -> Self {
        Self {
            name: name.to_string(),
            description: description.to_string(),
            version: None,
            positionals: Vec::new(),
            flags: Vec::new(),
            options: Vec::new(),
            subcommands: Map::new(),
        }
    }

    /// Set the version string.
    pub fn version(mut self, v: &str) -> Self {
        self.version = Some(v.to_string());
        self
    }

    /// Add a positional argument.
    pub fn positional(mut self, name: &str, help: &str, arg_type: ArgType, required: bool) -> Self {
        self.positionals.push(Positional {
            name: name.to_string(),
            help: help.to_string(),
            arg_type,
            required,
        });
        self
    }

    /// Add a boolean flag (e.g. `--verbose` / `-v`).
    pub fn flag(mut self, name: &str, help: &str, short: Option<char>) -> Self {
        self.flags.push(Flag {
            name: name.to_string(),
            help: help.to_string(),
            short,
        });
        self
    }

    /// Add a key-value option (e.g. `--port 8080`).
    pub fn option(
        mut self,
        name: &str,
        help: &str,
        arg_type: ArgType,
        short: Option<char>,
        default: Option<&str>,
        env_var: Option<&str>,
    ) -> Self {
        self.options.push(Opt {
            name: name.to_string(),
            help: help.to_string(),
            arg_type,
            short,
            default: default.map(|s| s.to_string()),
            env_var: env_var.map(|s| s.to_string()),
        });
        self
    }

    /// Add a subcommand.
    pub fn subcommand(mut self, sub: App) -> Self {
        self.subcommands.insert(sub.name.clone(), sub);
        self
    }

    /// Generate help text.
    pub fn help(&self) -> String {
        let mut out = String::new();

        // Header
        out.push_str(&self.name);
        if let Some(ref v) = self.version {
            out.push(' ');
            out.push_str(v);
        }
        out.push('\n');
        out.push_str(&self.description);
        out.push_str("\n\n");

        // Usage
        out.push_str("USAGE:\n    ");
        out.push_str(&self.name);
        if !self.subcommands.is_empty() {
            out.push_str(" <COMMAND>");
        }
        if !self.options.is_empty() || !self.flags.is_empty() {
            out.push_str(" [OPTIONS]");
        }
        for p in &self.positionals {
            if p.required {
                out.push_str(&format!(" <{}>", p.name.to_uppercase()));
            } else {
                out.push_str(&format!(" [{}]", p.name.to_uppercase()));
            }
        }
        out.push_str("\n\n");

        // Positionals
        if !self.positionals.is_empty() {
            out.push_str("ARGS:\n");
            for p in &self.positionals {
                let req = if p.required { " (required)" } else { "" };
                out.push_str(&format!("    <{}>    {}{}\n", p.name.to_uppercase(), p.help, req));
            }
            out.push('\n');
        }

        // Subcommands
        if !self.subcommands.is_empty() {
            out.push_str("COMMANDS:\n");
            let mut names: Vec<&String> = self.subcommands.keys().collect();
            names.sort();
            for name in names {
                let sub = &self.subcommands[name];
                out.push_str(&format!("    {:<16}{}\n", name, sub.description));
            }
            out.push('\n');
        }

        // Options + Flags
        if !self.flags.is_empty() || !self.options.is_empty() {
            out.push_str("OPTIONS:\n");
            for f in &self.flags {
                let short = f
                    .short
                    .map(|c| format!("-{}, ", c))
                    .unwrap_or_else(|| "    ".to_string());
                out.push_str(&format!("    {}--{:<16}{}\n", short, f.name, f.help));
            }
            for o in &self.options {
                let short = o
                    .short
                    .map(|c| format!("-{}, ", c))
                    .unwrap_or_else(|| "    ".to_string());
                let def = o
                    .default
                    .as_ref()
                    .map(|d| format!(" [default: {}]", d))
                    .unwrap_or_default();
                let env = o
                    .env_var
                    .as_ref()
                    .map(|e| format!(" [env: {}]", e))
                    .unwrap_or_default();
                out.push_str(&format!(
                    "    {}--{:<16}{}{}{}\n",
                    short, o.name, o.help, def, env
                ));
            }
            out.push_str("        --help            Show this help message\n");
        }

        out
    }

    /// Parse from an iterator of strings (first element = program name, skipped).
    pub fn parse_from<S: AsRef<str>>(&self, args: &[S]) -> Result<Matches, ParseError> {
        let strs: Vec<&str> = args.iter().map(|s| s.as_ref()).collect();
        if strs.is_empty() {
            return self.parse_slice(&[]);
        }
        self.parse_slice(&strs[1..])
    }

    /// Parse from a slice (no program name).
    fn parse_slice(&self, args: &[&str]) -> Result<Matches, ParseError> {
        let mut matches = Matches::new();
        let mut pos_idx: usize = 0;
        let mut i = 0;
        let mut after_double_dash = false;

        while i < args.len() {
            let arg = args[i];

            if after_double_dash {
                matches.rest.push(arg.to_string());
                i += 1;
                continue;
            }

            if arg == "--" {
                after_double_dash = true;
                i += 1;
                continue;
            }

            // --name=value or --name value
            if let Some(rest) = arg.strip_prefix("--") {
                if rest == "help" {
                    // Just return empty matches; caller checks
                    // In practice, print help and exit
                    #[cfg(feature = "std")]
                    {
                        print!("{}", self.help());
                        std::process::exit(0);
                    }
                    #[cfg(not(feature = "std"))]
                    {
                        return Ok(matches);
                    }
                }

                let (name, inline_val) = if let Some(eq) = rest.find('=') {
                    (&rest[..eq], Some(&rest[eq + 1..]))
                } else {
                    (rest, None)
                };

                // Check flags
                if let Some(_f) = self.flags.iter().find(|f| f.name == name) {
                    matches.flags.insert(name.to_string(), true);
                    i += 1;
                    continue;
                }

                // Check options
                if let Some(opt) = self.options.iter().find(|o| o.name == name) {
                    let val_str = if let Some(v) = inline_val {
                        v.to_string()
                    } else {
                        i += 1;
                        if i >= args.len() {
                            return Err(ParseError::MissingValue(name.to_string()));
                        }
                        args[i].to_string()
                    };
                    let val = parse_value(&opt.name, &val_str, opt.arg_type)?;
                    matches.values.insert(opt.name.clone(), val);
                    i += 1;
                    continue;
                }

                return Err(ParseError::UnknownArg(format!("--{}", name)));
            }

            // -v or -p value (short flags/options)
            if arg.starts_with('-') && arg.len() > 1 && !arg.starts_with("--") {
                let chars: Vec<char> = arg[1..].chars().collect();
                let mut ci = 0;
                while ci < chars.len() {
                    let ch = chars[ci];

                    // Check flags
                    if let Some(_f) = self.flags.iter().find(|f| f.short == Some(ch)) {
                        matches.flags.insert(_f.name.clone(), true);
                        ci += 1;
                        continue;
                    }

                    // Check options
                    if let Some(opt) = self.options.iter().find(|o| o.short == Some(ch)) {
                        // Rest of chars or next arg is the value
                        let val_str = if ci + 1 < chars.len() {
                            chars[ci + 1..].iter().collect::<String>()
                        } else {
                            i += 1;
                            if i >= args.len() {
                                return Err(ParseError::MissingValue(opt.name.clone()));
                            }
                            args[i].to_string()
                        };
                        let val = parse_value(&opt.name, &val_str, opt.arg_type)?;
                        matches.values.insert(opt.name.clone(), val);
                        break;
                    }

                    return Err(ParseError::UnknownArg(format!("-{}", ch)));
                }
                i += 1;
                continue;
            }

            // Subcommand?
            if pos_idx == 0 && self.subcommands.contains_key(arg) {
                let sub = &self.subcommands[arg];
                let sub_matches = sub.parse_slice(&args[i + 1..])?;
                matches.subcommand = Some((arg.to_string(), Box::new(sub_matches)));
                return Ok(matches);
            }

            // Positional
            if pos_idx < self.positionals.len() {
                let p = &self.positionals[pos_idx];
                let val = parse_value(&p.name, arg, p.arg_type)?;
                matches.values.insert(p.name.clone(), val);
                pos_idx += 1;
            } else {
                matches.rest.push(arg.to_string());
            }

            i += 1;
        }

        // Apply defaults and env vars for missing options
        for opt in &self.options {
            if !matches.values.contains_key(&opt.name) {
                // Try env var
                #[cfg(feature = "std")]
                if let Some(ref env_key) = opt.env_var {
                    if let Ok(val) = std::env::var(env_key) {
                        if let Ok(v) = parse_value(&opt.name, &val, opt.arg_type) {
                            matches.values.insert(opt.name.clone(), v);
                            continue;
                        }
                    }
                }

                // Try default
                if let Some(ref def) = opt.default {
                    if let Ok(v) = parse_value(&opt.name, def, opt.arg_type) {
                        matches.values.insert(opt.name.clone(), v);
                    }
                }
            }
        }

        // Check required positionals
        for p in &self.positionals {
            if p.required && !matches.values.contains_key(&p.name) {
                return Err(ParseError::MissingRequired(p.name.clone()));
            }
        }

        Ok(matches)
    }

    /// Parse from `std::env::args()`.
    #[cfg(feature = "std")]
    pub fn parse_env(&self) -> Result<Matches, ParseError> {
        let args: Vec<String> = std::env::args().collect();
        self.parse_from(&args)
    }
}

fn parse_value(name: &str, raw: &str, ty: ArgType) -> Result<Value, ParseError> {
    match ty {
        ArgType::Str => Ok(Value::Str(raw.to_string())),
        ArgType::Int => raw
            .parse::<i64>()
            .map(Value::Int)
            .map_err(|_| ParseError::InvalidType(name.to_string(), raw.to_string())),
        ArgType::Float => raw
            .parse::<f64>()
            .map(Value::Float)
            .map_err(|_| ParseError::InvalidType(name.to_string(), raw.to_string())),
        ArgType::Bool => match raw {
            "true" | "1" | "yes" | "on" => Ok(Value::Bool(true)),
            "false" | "0" | "no" | "off" => Ok(Value::Bool(false)),
            _ => Err(ParseError::InvalidType(name.to_string(), raw.to_string())),
        },
    }
}

// ── Tests ──────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    fn test_app() -> App {
        App::new("testapp", "A test application")
            .version("0.1.0")
            .positional("input", "Input file", ArgType::Str, true)
            .positional("output", "Output file", ArgType::Str, false)
            .flag("verbose", "Verbose output", Some('v'))
            .flag("dry-run", "Dry run mode", Some('n'))
            .option("port", "Port number", ArgType::Int, Some('p'), Some("8080"), None)
            .option("host", "Hostname", ArgType::Str, Some('h'), Some("localhost"), None)
            .option("config", "Config path", ArgType::Str, Some('c'), None, Some("TEST_CONFIG"))
            .option("rate", "Rate limit", ArgType::Float, Some('r'), None, None)
    }

    #[test]
    fn test_basic_positional() {
        let app = test_app();
        let m = app.parse_from(&["app", "input.txt"]).unwrap();
        assert_eq!(m.get_str("input"), Some("input.txt"));
    }

    #[test]
    fn test_two_positionals() {
        let app = test_app();
        let m = app.parse_from(&["app", "in.txt", "out.txt"]).unwrap();
        assert_eq!(m.get_str("input"), Some("in.txt"));
        assert_eq!(m.get_str("output"), Some("out.txt"));
    }

    #[test]
    fn test_missing_required() {
        let app = test_app();
        let err = app.parse_from(&["app"]).unwrap_err();
        assert_eq!(err, ParseError::MissingRequired("input".into()));
    }

    #[test]
    fn test_flags_long() {
        let app = test_app();
        let m = app.parse_from(&["app", "f.txt", "--verbose"]).unwrap();
        assert!(m.get_bool("verbose"));
        assert!(!m.get_bool("dry-run"));
    }

    #[test]
    fn test_flags_short() {
        let app = test_app();
        let m = app.parse_from(&["app", "f.txt", "-v", "-n"]).unwrap();
        assert!(m.get_bool("verbose"));
        assert!(m.get_bool("dry-run"));
    }

    #[test]
    fn test_combined_short_flags() {
        let app = test_app();
        let m = app.parse_from(&["app", "f.txt", "-vn"]).unwrap();
        assert!(m.get_bool("verbose"));
        assert!(m.get_bool("dry-run"));
    }

    #[test]
    fn test_option_long() {
        let app = test_app();
        let m = app.parse_from(&["app", "f.txt", "--port", "3000"]).unwrap();
        assert_eq!(m.get_int("port"), Some(3000));
    }

    #[test]
    fn test_option_long_equals() {
        let app = test_app();
        let m = app.parse_from(&["app", "f.txt", "--port=9090"]).unwrap();
        assert_eq!(m.get_int("port"), Some(9090));
    }

    #[test]
    fn test_option_short() {
        let app = test_app();
        let m = app.parse_from(&["app", "f.txt", "-p", "4000"]).unwrap();
        assert_eq!(m.get_int("port"), Some(4000));
    }

    #[test]
    fn test_defaults() {
        let app = test_app();
        let m = app.parse_from(&["app", "f.txt"]).unwrap();
        assert_eq!(m.get_int("port"), Some(8080));
        assert_eq!(m.get_str("host"), Some("localhost"));
    }

    #[test]
    fn test_float_option() {
        let app = test_app();
        let m = app.parse_from(&["app", "f.txt", "--rate", "1.5"]).unwrap();
        assert_eq!(m.get_float("rate"), Some(1.5));
    }

    #[test]
    fn test_invalid_type() {
        let app = test_app();
        let err = app.parse_from(&["app", "f.txt", "--port", "abc"]).unwrap_err();
        assert!(matches!(err, ParseError::InvalidType(_, _)));
    }

    #[test]
    fn test_unknown_flag() {
        let app = test_app();
        let err = app.parse_from(&["app", "f.txt", "--unknown"]).unwrap_err();
        assert!(matches!(err, ParseError::UnknownArg(_)));
    }

    #[test]
    fn test_double_dash() {
        let app = test_app();
        let m = app.parse_from(&["app", "f.txt", "--", "--not-a-flag", "extra"]).unwrap();
        assert_eq!(m.rest(), &["--not-a-flag", "extra"]);
    }

    #[test]
    fn test_subcommand() {
        let app = App::new("cli", "CLI tool")
            .flag("verbose", "Verbose", Some('v'))
            .subcommand(
                App::new("ingest", "Ingest data")
                    .positional("path", "Data path", ArgType::Str, true)
                    .flag("force", "Force overwrite", Some('f')),
            )
            .subcommand(
                App::new("query", "Query data")
                    .positional("text", "Query text", ArgType::Str, true)
                    .option("limit", "Result limit", ArgType::Int, Some('l'), Some("10"), None),
            );

        let m = app.parse_from(&["cli", "ingest", "data/", "--force"]).unwrap();
        let (name, sub) = m.subcommand().unwrap();
        assert_eq!(name, "ingest");
        assert_eq!(sub.get_str("path"), Some("data/"));
        assert!(sub.get_bool("force"));
    }

    #[test]
    fn test_subcommand_query() {
        let app = App::new("cli", "CLI tool")
            .subcommand(
                App::new("query", "Query data")
                    .positional("text", "Query text", ArgType::Str, true)
                    .option("limit", "Result limit", ArgType::Int, Some('l'), Some("10"), None),
            );

        let m = app.parse_from(&["cli", "query", "hello world", "-l", "5"]).unwrap();
        let (name, sub) = m.subcommand().unwrap();
        assert_eq!(name, "query");
        assert_eq!(sub.get_str("text"), Some("hello world"));
        assert_eq!(sub.get_int("limit"), Some(5));
    }

    #[test]
    fn test_help_text() {
        let app = test_app();
        let help = app.help();
        assert!(help.contains("testapp"));
        assert!(help.contains("A test application"));
        assert!(help.contains("--verbose"));
        assert!(help.contains("-v"));
        assert!(help.contains("--port"));
        assert!(help.contains("[default: 8080]"));
        assert!(help.contains("[env: TEST_CONFIG]"));
        assert!(help.contains("<INPUT>"));
    }

    #[test]
    fn test_env_var_fallback() {
        std::env::set_var("TEST_CONFIG", "/etc/test.toml");
        let app = test_app();
        let m = app.parse_from(&["app", "f.txt"]).unwrap();
        assert_eq!(m.get_str("config"), Some("/etc/test.toml"));
        std::env::remove_var("TEST_CONFIG");
    }

    #[test]
    fn test_mixed_flags_and_positionals() {
        let app = test_app();
        let m = app
            .parse_from(&["app", "-v", "input.txt", "--port", "3000", "output.txt", "-n"])
            .unwrap();
        assert!(m.get_bool("verbose"));
        assert!(m.get_bool("dry-run"));
        assert_eq!(m.get_str("input"), Some("input.txt"));
        assert_eq!(m.get_str("output"), Some("output.txt"));
        assert_eq!(m.get_int("port"), Some(3000));
    }
}
