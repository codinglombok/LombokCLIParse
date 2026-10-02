//! LombokCLIParse: a small command-line parser with positional arguments,
//! flags, typed options, subcommands, environment fallback, and generated
//! help. The same input gives the same result, error message and help text
//! in the Rust, TypeScript, Python, Go and PHP ports
//! (docs/SPEC_LombokCLIParse_v0.2.0.md).
//!
//! ```
//! use lombokcliparse::{App, ArgType, ParseError};
//!
//! let app = App::new("myapp", "My application")
//!     .version("1.0.0")
//!     .positional("input", "Input file", ArgType::Str, true)
//!     .flag("verbose", "Verbose output", Some('v'))
//!     .option("port", "Port", ArgType::Int, Some('p'), Some("8080"), None);
//!
//! let m = app.parse_from(&["myapp", "data.txt", "-v", "-p", "3000"]).unwrap();
//! assert_eq!(m.get_str("input"), Some("data.txt"));
//! assert!(m.get_bool("verbose"));
//! assert_eq!(m.get_int("port"), Some(3000));
//!
//! // --help and --version are returned, not printed: the caller decides.
//! match app.parse_from(&["myapp", "--version"]) {
//!     Err(ParseError::Version(text)) => assert_eq!(text, "myapp 1.0.0\n"),
//!     other => panic!("{other:?}"),
//! }
//! ```
#![cfg_attr(not(feature = "std"), no_std)]
#![forbid(unsafe_code)]
#![warn(missing_docs)]

extern crate alloc;

use alloc::boxed::Box;
use alloc::collections::{BTreeMap, BTreeSet};
use alloc::format;
use alloc::string::{String, ToString};
use alloc::vec::Vec;
use core::fmt;

/// Largest integer accepted by `ArgType::Int` (2^53 - 1, exact in every port).
pub const MAX_SAFE_INTEGER: i64 = 9_007_199_254_740_991;

// ── errors ─────────────────────────────────────────────────────────

/// Why parsing stopped. `Help` and `Version` are not failures: they carry the
/// text to print (SPEC section 4.2).
#[derive(Debug, Clone, PartialEq)]
pub enum ParseError {
    /// `--name` or `-c` that the app does not define.
    UnknownArgument {
        /// The argument as written, without an inline value.
        arg: String,
    },
    /// An option at the end of the command line without a value.
    MissingValue {
        /// The option as written.
        arg: String,
    },
    /// A value that does not match the type of its argument.
    InvalidValue {
        /// The option as written, or the positional name.
        arg: String,
        /// The rejected text.
        value: String,
    },
    /// A required positional argument is missing.
    MissingRequired {
        /// The positional name.
        arg: String,
    },
    /// A positional token with no positional slot left.
    UnexpectedArgument {
        /// The token.
        arg: String,
    },
    /// A token where a subcommand was expected.
    UnknownSubcommand {
        /// The token.
        arg: String,
    },
    /// `--flag=value`.
    FlagTakesNoValue {
        /// The flag as written.
        arg: String,
    },
    /// The app definition breaks a rule of SPEC section 2.
    InvalidDefinition {
        /// The offending name or short letter.
        arg: String,
        /// The rule, for example `"duplicate name"`.
        reason: &'static str,
    },
    /// `--help` was given; the text ends with a newline.
    Help(String),
    /// `--version` was given; the text is `"name version\n"`.
    Version(String),
}

impl ParseError {
    /// The code shared by every port, for example `"UNKNOWN_ARGUMENT"`.
    pub fn code(&self) -> &'static str {
        match self {
            Self::UnknownArgument { .. } => "UNKNOWN_ARGUMENT",
            Self::MissingValue { .. } => "MISSING_VALUE",
            Self::InvalidValue { .. } => "INVALID_VALUE",
            Self::MissingRequired { .. } => "MISSING_REQUIRED",
            Self::UnexpectedArgument { .. } => "UNEXPECTED_ARGUMENT",
            Self::UnknownSubcommand { .. } => "UNKNOWN_SUBCOMMAND",
            Self::FlagTakesNoValue { .. } => "FLAG_TAKES_NO_VALUE",
            Self::InvalidDefinition { .. } => "INVALID_DEFINITION",
            Self::Help(_) => "HELP",
            Self::Version(_) => "VERSION",
        }
    }

    /// The argument the error is about (empty for `Help` and `Version`).
    pub fn arg(&self) -> &str {
        match self {
            Self::UnknownArgument { arg }
            | Self::MissingValue { arg }
            | Self::InvalidValue { arg, .. }
            | Self::MissingRequired { arg }
            | Self::UnexpectedArgument { arg }
            | Self::UnknownSubcommand { arg }
            | Self::FlagTakesNoValue { arg }
            | Self::InvalidDefinition { arg, .. } => arg,
            Self::Help(_) | Self::Version(_) => "",
        }
    }

    /// The rejected value for `InvalidValue`.
    pub fn value(&self) -> Option<&str> {
        match self {
            Self::InvalidValue { value, .. } => Some(value),
            _ => None,
        }
    }

    /// True for `Help` and `Version`, which should exit with status 0.
    pub fn is_info(&self) -> bool {
        matches!(self, Self::Help(_) | Self::Version(_))
    }
}

impl fmt::Display for ParseError {
    /// `"CODE: message"` (SPEC section 6), or the help/version text itself.
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        let code = self.code();
        match self {
            Self::UnknownArgument { arg } => write!(f, "{code}: unknown argument '{arg}'"),
            Self::MissingValue { arg } => write!(f, "{code}: missing value for '{arg}'"),
            Self::InvalidValue { arg, value } => {
                write!(f, "{code}: invalid value '{value}' for '{arg}'")
            }
            Self::MissingRequired { arg } => write!(f, "{code}: missing required argument '{arg}'"),
            Self::UnexpectedArgument { arg } => write!(f, "{code}: unexpected argument '{arg}'"),
            Self::UnknownSubcommand { arg } => write!(f, "{code}: unknown subcommand '{arg}'"),
            Self::FlagTakesNoValue { arg } => {
                write!(f, "{code}: flag '{arg}' does not take a value")
            }
            Self::InvalidDefinition { arg, reason } => write!(f, "{code}: {reason}: '{arg}'"),
            Self::Help(t) | Self::Version(t) => f.write_str(t),
        }
    }
}

#[cfg(feature = "std")]
impl std::error::Error for ParseError {}

// ── values ─────────────────────────────────────────────────────────

/// Type of a positional argument or option (SPEC section 3).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ArgType {
    /// Any text.
    Str,
    /// `[+-]?[0-9]+` within ±(2^53 - 1).
    Int,
    /// Decimal floating point, finite after rounding to binary64.
    Float,
    /// `true/false/1/0/yes/no/on/off`, ASCII case-insensitive.
    Bool,
}

impl ArgType {
    fn placeholder(self) -> &'static str {
        match self {
            ArgType::Str => "<VALUE>",
            ArgType::Int => "<INT>",
            ArgType::Float => "<FLOAT>",
            ArgType::Bool => "<BOOL>",
        }
    }
}

/// A parsed value.
#[derive(Debug, Clone, PartialEq)]
pub enum Value {
    /// Text.
    Str(String),
    /// Integer within ±(2^53 - 1).
    Int(i64),
    /// Finite binary64.
    Float(f64),
    /// Boolean.
    Bool(bool),
}

fn all_digits(s: &str) -> bool {
    !s.is_empty() && s.bytes().all(|b| b.is_ascii_digit())
}

fn strip_sign(s: &str) -> &str {
    s.strip_prefix(['+', '-']).unwrap_or(s)
}

fn is_float_syntax(s: &str) -> bool {
    let s = strip_sign(s);
    let (mantissa, exp) = match s.find(['e', 'E']) {
        Some(i) => (&s[..i], Some(&s[i + 1..])),
        None => (s, None),
    };
    let ok_mantissa = match mantissa.split_once('.') {
        Some((a, b)) => {
            (all_digits(a) && (b.is_empty() || all_digits(b))) || (a.is_empty() && all_digits(b))
        }
        None => all_digits(mantissa),
    };
    ok_mantissa && exp.map_or(true, |e| all_digits(strip_sign(e)))
}

/// Parses `raw` as `ty`; `None` when the text is not valid for the type.
pub fn parse_value(ty: ArgType, raw: &str) -> Option<Value> {
    match ty {
        ArgType::Str => Some(Value::Str(raw.to_string())),
        ArgType::Int => {
            if !all_digits(strip_sign(raw)) {
                return None;
            }
            // more than 16 digits is always out of range; avoids overflow
            let digits = strip_sign(raw).trim_start_matches('0');
            if digits.len() > 16 {
                return None;
            }
            let v: i64 = raw.trim_start_matches('+').parse().ok()?;
            (-MAX_SAFE_INTEGER..=MAX_SAFE_INTEGER)
                .contains(&v)
                .then_some(Value::Int(v))
        }
        ArgType::Float => {
            if !is_float_syntax(raw) {
                return None;
            }
            let v: f64 = raw.parse().ok()?;
            v.is_finite().then_some(Value::Float(v))
        }
        ArgType::Bool => {
            let l = raw.to_ascii_lowercase();
            if !raw.is_ascii() {
                return None;
            }
            match l.as_str() {
                "true" | "1" | "yes" | "on" => Some(Value::Bool(true)),
                "false" | "0" | "no" | "off" => Some(Value::Bool(false)),
                _ => None,
            }
        }
    }
}

// ── definitions ────────────────────────────────────────────────────

#[derive(Debug, Clone)]
struct Positional {
    name: String,
    help: String,
    ty: ArgType,
    required: bool,
}

#[derive(Debug, Clone)]
enum Kind {
    Flag,
    Option {
        ty: ArgType,
        default: Option<String>,
        env: Option<String>,
    },
}

#[derive(Debug, Clone)]
struct Named {
    name: String,
    help: String,
    short: Option<char>,
    kind: Kind,
}

// ── matches ────────────────────────────────────────────────────────

/// The result of a successful parse.
#[derive(Debug, Clone, Default, PartialEq)]
pub struct Matches {
    values: BTreeMap<String, Value>,
    flags: BTreeSet<String>,
    subcommand: Option<(String, Box<Matches>)>,
    rest: Vec<String>,
}

impl Matches {
    /// The text of a `Str` value.
    pub fn get_str(&self, name: &str) -> Option<&str> {
        match self.values.get(name) {
            Some(Value::Str(s)) => Some(s),
            _ => None,
        }
    }

    /// An `Int` value.
    pub fn get_int(&self, name: &str) -> Option<i64> {
        match self.values.get(name) {
            Some(Value::Int(v)) => Some(*v),
            _ => None,
        }
    }

    /// A `Float` value.
    pub fn get_float(&self, name: &str) -> Option<f64> {
        match self.values.get(name) {
            Some(Value::Float(v)) => Some(*v),
            _ => None,
        }
    }

    /// True when the flag was given or a `Bool` option is true.
    pub fn get_bool(&self, name: &str) -> bool {
        self.flags.contains(name) || matches!(self.values.get(name), Some(Value::Bool(true)))
    }

    /// Any value by name.
    pub fn get(&self, name: &str) -> Option<&Value> {
        self.values.get(name)
    }

    /// All values, sorted by name.
    pub fn values(&self) -> impl Iterator<Item = (&str, &Value)> {
        self.values.iter().map(|(k, v)| (k.as_str(), v))
    }

    /// Names of the flags that were given, sorted.
    pub fn flags(&self) -> impl Iterator<Item = &str> {
        self.flags.iter().map(String::as_str)
    }

    /// The selected subcommand and its matches.
    pub fn subcommand(&self) -> Option<(&str, &Matches)> {
        self.subcommand
            .as_ref()
            .map(|(n, m)| (n.as_str(), m.as_ref()))
    }

    /// Tokens after `--` that did not fill a positional argument.
    pub fn rest(&self) -> &[String] {
        &self.rest
    }
}

// ── app ────────────────────────────────────────────────────────────

/// A command-line application or subcommand definition (builder).
#[derive(Debug, Clone)]
pub struct App {
    name: String,
    description: String,
    version: Option<String>,
    positionals: Vec<Positional>,
    args: Vec<Named>,
    subcommands: Vec<App>,
}

fn def_err(arg: &str, reason: &'static str) -> ParseError {
    ParseError::InvalidDefinition {
        arg: arg.to_string(),
        reason,
    }
}

fn valid_name(n: &str) -> bool {
    let mut b = n.bytes();
    matches!(b.next(), Some(c) if c.is_ascii_alphanumeric())
        && b.all(|c| c.is_ascii_alphanumeric() || c == b'_' || c == b'-')
}

fn join_parts(parts: &[&str]) -> String {
    let mut out = String::new();
    for p in parts.iter().filter(|p| !p.is_empty()) {
        if !out.is_empty() {
            out.push(' ');
        }
        out.push_str(p);
    }
    out
}

fn section(out: &mut String, title: &str, rows: &[(String, String)]) {
    let width = rows
        .iter()
        .map(|(l, _)| l.chars().count())
        .max()
        .unwrap_or(0);
    out.push_str(title);
    out.push_str(":\n");
    for (left, help) in rows {
        out.push_str("    ");
        out.push_str(left);
        if !help.is_empty() {
            for _ in left.chars().count()..width + 2 {
                out.push(' ');
            }
            out.push_str(help);
        }
        out.push('\n');
    }
}

impl App {
    /// A new app. `description` may be empty.
    pub fn new(name: &str, description: &str) -> Self {
        App {
            name: name.to_string(),
            description: description.to_string(),
            version: None,
            positionals: Vec::new(),
            args: Vec::new(),
            subcommands: Vec::new(),
        }
    }

    /// Sets the version; enables `--version`.
    pub fn version(mut self, v: &str) -> Self {
        self.version = Some(v.to_string());
        self
    }

    /// Adds a positional argument (filled in definition order).
    pub fn positional(mut self, name: &str, help: &str, ty: ArgType, required: bool) -> Self {
        self.positionals.push(Positional {
            name: name.to_string(),
            help: help.to_string(),
            ty,
            required,
        });
        self
    }

    /// Adds a boolean flag, `--name` or `-c`.
    pub fn flag(mut self, name: &str, help: &str, short: Option<char>) -> Self {
        self.args.push(Named {
            name: name.to_string(),
            help: help.to_string(),
            short,
            kind: Kind::Flag,
        });
        self
    }

    /// Adds an option taking a value. When it is absent, the environment
    /// variable `env` and then `default` are used (SPEC section 4.4).
    pub fn option(
        mut self,
        name: &str,
        help: &str,
        ty: ArgType,
        short: Option<char>,
        default: Option<&str>,
        env: Option<&str>,
    ) -> Self {
        self.args.push(Named {
            name: name.to_string(),
            help: help.to_string(),
            short,
            kind: Kind::Option {
                ty,
                default: default.map(str::to_string),
                env: env.map(str::to_string),
            },
        });
        self
    }

    /// Adds a subcommand. An app with subcommands has no positional arguments.
    pub fn subcommand(mut self, sub: App) -> Self {
        self.subcommands.push(sub);
        self
    }

    /// Checks the rules of SPEC section 2 for this app and its subcommands.
    ///
    /// # Errors
    /// `InvalidDefinition` naming the first broken rule.
    pub fn validate(&self) -> Result<(), ParseError> {
        let mut names: Vec<&str> = Vec::new();
        let mut shorts: Vec<char> = Vec::new();
        let reserved = |n: &str| n == "help" || (n == "version" && self.version.is_some());
        let check_name = |n: &'_ str| -> Result<(), ParseError> {
            if !valid_name(n) {
                return Err(def_err(n, "invalid name"));
            }
            if reserved(n) {
                return Err(def_err(n, "reserved name"));
            }
            Ok(())
        };
        let entries = self
            .positionals
            .iter()
            .map(|p| (p.name.as_str(), None, None))
            .chain(
                self.args
                    .iter()
                    .map(|a| (a.name.as_str(), a.short, Some(&a.kind))),
            );
        for (n, short, kind) in entries {
            check_name(n)?;
            if names.contains(&n) {
                return Err(def_err(n, "duplicate name"));
            }
            names.push(n);
            if let Some(c) = short {
                if !c.is_ascii_alphabetic() {
                    return Err(def_err(&c.to_string(), "invalid short"));
                }
                if shorts.contains(&c) {
                    return Err(def_err(&c.to_string(), "duplicate short"));
                }
                shorts.push(c);
            }
            if let Some(Kind::Option {
                ty,
                default: Some(d),
                ..
            }) = kind
            {
                if parse_value(*ty, d).is_none() {
                    return Err(def_err(n, "invalid default"));
                }
            }
        }
        let mut seen_optional = false;
        for p in &self.positionals {
            if p.required && seen_optional {
                return Err(def_err(&p.name, "required after optional"));
            }
            seen_optional |= !p.required;
        }
        if let Some(first) = self.subcommands.first() {
            if !self.positionals.is_empty() {
                return Err(def_err(&first.name, "positionals with subcommands"));
            }
        }
        let mut sub_names: Vec<&str> = Vec::new();
        for s in &self.subcommands {
            if !valid_name(&s.name) {
                return Err(def_err(&s.name, "invalid name"));
            }
            if sub_names.contains(&s.name.as_str()) {
                return Err(def_err(&s.name, "duplicate name"));
            }
            sub_names.push(&s.name);
            s.validate()?;
        }
        Ok(())
    }

    /// The help text (SPEC section 5) as shown for `--help`.
    pub fn help(&self) -> String {
        self.help_at(&self.name)
    }

    fn help_at(&self, path: &str) -> String {
        let mut out = self.name.clone();
        if let Some(v) = &self.version {
            out.push(' ');
            out.push_str(v);
        }
        out.push('\n');
        if !self.description.is_empty() {
            out.push_str(&self.description);
            out.push('\n');
        }
        out.push_str("\nUSAGE:\n    ");
        out.push_str(path);
        out.push_str(" [OPTIONS]");
        if !self.subcommands.is_empty() {
            out.push_str(" <COMMAND>");
        }
        for p in &self.positionals {
            let n = p.name.to_ascii_uppercase();
            out.push_str(&if p.required {
                format!(" <{n}>")
            } else {
                format!(" [{n}]")
            });
        }
        out.push('\n');
        if !self.positionals.is_empty() {
            let rows: Vec<(String, String)> = self
                .positionals
                .iter()
                .map(|p| {
                    let req = if p.required { "(required)" } else { "" };
                    (
                        format!("<{}>", p.name.to_ascii_uppercase()),
                        join_parts(&[&p.help, req]),
                    )
                })
                .collect();
            out.push('\n');
            section(&mut out, "ARGS", &rows);
        }
        if !self.subcommands.is_empty() {
            let rows: Vec<(String, String)> = self
                .subcommands
                .iter()
                .map(|s| (s.name.clone(), s.description.clone()))
                .collect();
            out.push('\n');
            section(&mut out, "COMMANDS", &rows);
        }
        let mut rows: Vec<(String, String)> = Vec::new();
        for a in &self.args {
            let mut left = match a.short {
                Some(c) => format!("-{c}, --{}", a.name),
                None => format!("    --{}", a.name),
            };
            let help = match &a.kind {
                Kind::Flag => a.help.clone(),
                Kind::Option { ty, default, env } => {
                    left.push(' ');
                    left.push_str(ty.placeholder());
                    let d = default
                        .as_ref()
                        .map(|d| format!("[default: {d}]"))
                        .unwrap_or_default();
                    let e = env
                        .as_ref()
                        .map(|e| format!("[env: {e}]"))
                        .unwrap_or_default();
                    join_parts(&[&a.help, &d, &e])
                }
            };
            rows.push((left, help));
        }
        rows.push(("    --help".to_string(), "Print help".to_string()));
        if self.version.is_some() {
            rows.push(("    --version".to_string(), "Print version".to_string()));
        }
        out.push('\n');
        section(&mut out, "OPTIONS", &rows);
        out
    }

    /// Parses a full command line; the first element (program name) is skipped.
    /// Environment fallback reads the process environment (with `std`).
    ///
    /// # Errors
    /// See [`ParseError`]; `Help` and `Version` carry text to print.
    pub fn parse_from<S: AsRef<str>>(&self, args: &[S]) -> Result<Matches, ParseError> {
        let tokens = args.get(1..).unwrap_or(&[]);
        #[cfg(feature = "std")]
        {
            self.parse_with_env(tokens, |k| std::env::var(k).ok())
        }
        #[cfg(not(feature = "std"))]
        {
            self.parse_with_env(tokens, |_| None)
        }
    }

    /// Parses `tokens` (without the program name) with an explicit
    /// environment lookup.
    ///
    /// # Errors
    /// See [`ParseError`].
    pub fn parse_with_env<S: AsRef<str>>(
        &self,
        tokens: &[S],
        env: impl Fn(&str) -> Option<String>,
    ) -> Result<Matches, ParseError> {
        self.validate()?;
        let tokens: Vec<&str> = tokens.iter().map(AsRef::as_ref).collect();
        self.parse_tokens(&tokens, &env, &self.name)
    }

    /// Parses `std::env::args()`.
    ///
    /// # Errors
    /// See [`ParseError`].
    #[cfg(feature = "std")]
    pub fn parse_env(&self) -> Result<Matches, ParseError> {
        let args: Vec<String> = std::env::args().collect();
        self.parse_from(&args)
    }

    /// Parses `std::env::args()`; prints help or version to stdout and exits
    /// with 0, or prints the error to stderr and exits with 2.
    #[cfg(feature = "std")]
    pub fn run(&self) -> Matches {
        match self.parse_env() {
            Ok(m) => m,
            Err(e) if e.is_info() => {
                print!("{e}");
                std::process::exit(0)
            }
            Err(e) => {
                eprintln!("error: {e}");
                std::process::exit(2)
            }
        }
    }

    fn set_option(m: &mut Matches, a: &Named, raw: &str, arg: &str) -> Result<(), ParseError> {
        let Kind::Option { ty, .. } = &a.kind else {
            unreachable!("set_option on a flag")
        };
        match parse_value(*ty, raw) {
            Some(v) => {
                m.values.insert(a.name.clone(), v);
                Ok(())
            }
            None => Err(ParseError::InvalidValue {
                arg: arg.to_string(),
                value: raw.to_string(),
            }),
        }
    }

    fn parse_tokens(
        &self,
        tokens: &[&str],
        env: &dyn Fn(&str) -> Option<String>,
        path: &str,
    ) -> Result<Matches, ParseError> {
        let mut m = Matches::default();
        let mut pos_idx = 0;
        let mut i = 0;
        let mut after_dd = false;
        while i < tokens.len() {
            let tok = tokens[i];
            i += 1;
            if !after_dd {
                if tok == "--" {
                    after_dd = true;
                    continue;
                }
                if tok == "--help" {
                    return Err(ParseError::Help(self.help_at(path)));
                }
                if tok == "--version" {
                    if let Some(v) = &self.version {
                        return Err(ParseError::Version(format!("{} {}\n", self.name, v)));
                    }
                }
                if let Some(body) = tok.strip_prefix("--") {
                    let (name, inline) = match body.split_once('=') {
                        Some((n, v)) => (n, Some(v)),
                        None => (body, None),
                    };
                    let arg = format!("--{name}");
                    let Some(a) = self.args.iter().find(|a| a.name == name) else {
                        return Err(ParseError::UnknownArgument { arg });
                    };
                    if let Kind::Flag = a.kind {
                        if inline.is_some() {
                            return Err(ParseError::FlagTakesNoValue { arg });
                        }
                        m.flags.insert(a.name.clone());
                        continue;
                    }
                    let raw = match inline {
                        Some(v) => v,
                        None => {
                            let Some(&v) = tokens.get(i) else {
                                return Err(ParseError::MissingValue { arg });
                            };
                            i += 1;
                            v
                        }
                    };
                    Self::set_option(&mut m, a, raw, &arg)?;
                    continue;
                }
                let mut chars = tok.chars();
                if chars.next() == Some('-') {
                    if let Some(second) = chars.clone().next() {
                        if !second.is_ascii_digit() && second != '.' {
                            let cluster: Vec<char> = chars.collect();
                            let mut k = 0;
                            while k < cluster.len() {
                                let c = cluster[k];
                                let arg = format!("-{c}");
                                let Some(a) = self.args.iter().find(|a| a.short == Some(c)) else {
                                    return Err(ParseError::UnknownArgument { arg });
                                };
                                if let Kind::Flag = a.kind {
                                    m.flags.insert(a.name.clone());
                                    k += 1;
                                    continue;
                                }
                                let attached: String = cluster[k + 1..].iter().collect();
                                let raw = if let Some(v) = attached.strip_prefix('=') {
                                    v.to_string()
                                } else if !attached.is_empty() {
                                    attached
                                } else {
                                    let Some(&v) = tokens.get(i) else {
                                        return Err(ParseError::MissingValue { arg });
                                    };
                                    i += 1;
                                    v.to_string()
                                };
                                Self::set_option(&mut m, a, &raw, &arg)?;
                                break;
                            }
                            continue;
                        }
                    }
                }
            }
            // a positional token
            if !after_dd && !self.subcommands.is_empty() {
                let Some(sub) = self.subcommands.iter().find(|s| s.name == tok) else {
                    return Err(ParseError::UnknownSubcommand {
                        arg: tok.to_string(),
                    });
                };
                let sub_path = format!("{path} {tok}");
                let sm = sub.parse_tokens(&tokens[i..], env, &sub_path)?;
                m.subcommand = Some((tok.to_string(), Box::new(sm)));
                break;
            }
            if let Some(p) = self.positionals.get(pos_idx) {
                match parse_value(p.ty, tok) {
                    Some(v) => {
                        m.values.insert(p.name.clone(), v);
                    }
                    None => {
                        return Err(ParseError::InvalidValue {
                            arg: p.name.clone(),
                            value: tok.to_string(),
                        })
                    }
                }
                pos_idx += 1;
            } else if after_dd {
                m.rest.push(tok.to_string());
            } else {
                return Err(ParseError::UnexpectedArgument {
                    arg: tok.to_string(),
                });
            }
        }
        for a in &self.args {
            if m.values.contains_key(&a.name) {
                continue;
            }
            if let Kind::Option {
                env: env_name,
                default,
                ..
            } = &a.kind
            {
                let arg = format!("--{}", a.name);
                if let Some(v) = env_name.as_deref().and_then(env) {
                    Self::set_option(&mut m, a, &v, &arg)?;
                } else if let Some(d) = default {
                    Self::set_option(&mut m, a, d, &arg)?;
                }
            }
        }
        for p in &self.positionals {
            if p.required && !m.values.contains_key(&p.name) {
                return Err(ParseError::MissingRequired {
                    arg: p.name.clone(),
                });
            }
        }
        Ok(m)
    }
}
