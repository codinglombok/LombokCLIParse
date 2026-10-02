use lombokcliparse::*;

fn app() -> App {
    App::new("tool", "A tool")
        .version("1.0")
        .positional("input", "Input", ArgType::Str, true)
        .flag("verbose", "Verbose", Some('v'))
        .option(
            "level",
            "Level",
            ArgType::Int,
            Some('l'),
            Some("3"),
            Some("TOOL_LEVEL"),
        )
        .option("ratio", "Ratio", ArgType::Float, None, None, None)
        .option("color", "Colour", ArgType::Bool, None, None, None)
}

#[test]
fn getters() {
    let m = app()
        .parse_with_env(&["in", "-v", "--ratio", "0.5", "--color", "on"], |_| None)
        .unwrap();
    assert_eq!(m.get_str("input"), Some("in"));
    assert_eq!(m.get_int("level"), Some(3));
    assert_eq!(m.get_float("ratio"), Some(0.5));
    assert!(m.get_bool("verbose"));
    assert!(m.get_bool("color"));
    assert!(!m.get_bool("missing"));
    assert_eq!(m.get("level"), Some(&Value::Int(3)));
    assert_eq!(m.get_int("input"), None);
    assert_eq!(m.get_str("level"), None);
    assert_eq!(m.get_float("level"), None);
    assert!(m.subcommand().is_none());
    assert!(m.rest().is_empty());
}

#[test]
fn env_lookup_and_parse_from() {
    let m = app()
        .parse_with_env(&["x"], |k| (k == "TOOL_LEVEL").then(|| "9".to_string()))
        .unwrap();
    assert_eq!(m.get_int("level"), Some(9));
    std::env::set_var("LOMBOKCLIPARSE_TEST_LEVEL", "7");
    let a = App::new("t", "").option(
        "level",
        "",
        ArgType::Int,
        None,
        None,
        Some("LOMBOKCLIPARSE_TEST_LEVEL"),
    );
    assert_eq!(a.parse_from(&["t"]).unwrap().get_int("level"), Some(7));
    assert!(a.parse_from::<&str>(&[]).is_ok());
}

#[test]
fn help_version_and_errors() {
    let e = app().parse_with_env(&["--help"], |_| None).unwrap_err();
    assert!(e.is_info());
    assert_eq!(e.code(), "HELP");
    assert_eq!(e.arg(), "");
    assert_eq!(e.to_string(), app().help());
    let v = app().parse_with_env(&["--version"], |_| None).unwrap_err();
    assert_eq!(v, ParseError::Version("tool 1.0\n".into()));
    assert_eq!(v.code(), "VERSION");
    let bad = app()
        .parse_with_env(&["x", "-l", "z"], |_| None)
        .unwrap_err();
    assert!(!bad.is_info());
    assert_eq!(bad.value(), Some("z"));
    assert_eq!(bad.to_string(), "INVALID_VALUE: invalid value 'z' for '-l'");
    let boxed: Box<dyn std::error::Error> = Box::new(bad);
    assert!(boxed.to_string().starts_with("INVALID_VALUE"));
}

#[test]
fn definition_errors() {
    let e = App::new("d", "")
        .flag("a", "", Some('ä'))
        .validate()
        .unwrap_err();
    assert_eq!(
        e,
        ParseError::InvalidDefinition {
            arg: "ä".into(),
            reason: "invalid short"
        }
    );
    let e = App::new("d", "")
        .subcommand(App::new("bad name", ""))
        .validate()
        .unwrap_err();
    assert_eq!(
        e.to_string(),
        "INVALID_DEFINITION: invalid name: 'bad name'"
    );
    assert!(App::new("d", "")
        .subcommand(App::new("s", ""))
        .validate()
        .is_ok());
}

#[test]
fn value_parsing() {
    assert_eq!(
        parse_value(ArgType::Int, "-9007199254740991"),
        Some(Value::Int(-MAX_SAFE_INTEGER))
    );
    assert_eq!(
        parse_value(ArgType::Int, "00000000000000000000000001"),
        Some(Value::Int(1))
    );
    assert_eq!(parse_value(ArgType::Int, "99999999999999999"), None);
    assert_eq!(parse_value(ArgType::Float, "1e5"), Some(Value::Float(1e5)));
    assert_eq!(parse_value(ArgType::Float, "1e+"), None);
    assert_eq!(parse_value(ArgType::Bool, "ÿes"), None);
}
