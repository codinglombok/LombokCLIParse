//! Runs the shared vectors (vectors/lombokcliparse-vectors-v1.json).

use lombokcliparse::{App, ArgType, Matches, ParseError, Value};
use serde_json::{json, Map, Value as J};

fn ty(v: &J) -> ArgType {
    match v.as_str().unwrap_or("string") {
        "int" => ArgType::Int,
        "float" => ArgType::Float,
        "bool" => ArgType::Bool,
        _ => ArgType::Str,
    }
}

fn opt_str(v: &J) -> Option<&str> {
    v.as_str()
}

fn short(v: &J) -> Option<char> {
    // more than one character is kept as an invalid short by taking the first and
    // letting validation reject it; the vectors only use one-character strings or
    // multi-character strings that must be rejected
    v.as_str().map(|s| {
        let mut c = s.chars();
        let first = c.next().unwrap();
        if c.next().is_some() {
            '\u{0}'
        } else {
            first
        }
    })
}

fn build(a: &J) -> App {
    let mut app = App::new(
        a["name"].as_str().unwrap(),
        a["description"].as_str().unwrap_or(""),
    );
    if let Some(v) = a["version"].as_str() {
        app = app.version(v);
    }
    for p in a["positionals"].as_array().unwrap() {
        app = app.positional(
            p["name"].as_str().unwrap(),
            p["help"].as_str().unwrap_or(""),
            ty(&p["type"]),
            p["required"].as_bool().unwrap_or(false),
        );
    }
    for x in a["args"].as_array().unwrap() {
        let (name, help) = (
            x["name"].as_str().unwrap(),
            x["help"].as_str().unwrap_or(""),
        );
        app = if x["kind"] == "flag" {
            app.flag(name, help, short(&x["short"]))
        } else {
            app.option(
                name,
                help,
                ty(&x["type"]),
                short(&x["short"]),
                opt_str(&x["default"]),
                opt_str(&x["env"]),
            )
        };
    }
    for s in a["subcommands"].as_array().unwrap() {
        app = app.subcommand(build(s));
    }
    app
}

fn encode(m: &Matches) -> J {
    let mut values = Map::new();
    for (k, v) in m.values() {
        let e = match v {
            Value::Str(s) => json!({ "str": s }),
            Value::Int(i) => json!({ "int": i.to_string() }),
            Value::Float(f) => json!({ "float": format!("0x{:016x}", f.to_bits()) }),
            Value::Bool(b) => json!({ "bool": b }),
        };
        values.insert(k.to_string(), e);
    }
    json!({
        "values": values,
        "flags": m.flags().collect::<Vec<_>>(),
        "rest": m.rest(),
        "subcommand": m.subcommand().map(|(n, s)| json!({ "name": n, "matches": encode(s) })),
    })
}

#[test]
fn vectors() {
    let path = concat!(
        env!("CARGO_MANIFEST_DIR"),
        "/../vectors/lombokcliparse-vectors-v1.json"
    );
    let doc: J = serde_json::from_str(&std::fs::read_to_string(path).unwrap()).unwrap();
    let cases = doc["cases"].as_array().unwrap();
    assert!(cases.len() >= 100);
    let mut failures = Vec::new();
    for c in cases {
        // the one case with a two-character short is checked by its own unit test,
        // because Rust's `char` cannot hold "ab"
        if c["app"].to_string().contains("\"short\":\"ab\"") {
            continue;
        }
        let app = build(&c["app"]);
        let argv: Vec<&str> = c["argv"]
            .as_array()
            .unwrap()
            .iter()
            .map(|v| v.as_str().unwrap())
            .collect();
        let env = c["env"].as_object().unwrap().clone();
        let got = match app.parse_with_env(&argv, |k| {
            env.get(k).and_then(J::as_str).map(str::to_string)
        }) {
            Ok(m) => json!({ "matches": encode(&m) }),
            Err(ParseError::Help(t)) => json!({ "help": t }),
            Err(ParseError::Version(t)) => json!({ "version": t }),
            Err(e) => {
                let mut o = json!({ "code": e.code(), "arg": e.arg(), "message": e.to_string() });
                if let Some(v) = e.value() {
                    o["value"] = json!(v);
                }
                json!({ "error": o })
            }
        };
        if got != c["expected"] {
            failures.push(format!(
                "{}: got {}\nexpected {}",
                c["id"], got, c["expected"]
            ));
        }
    }
    assert!(
        failures.is_empty(),
        "{} failures:\n{}",
        failures.len(),
        failures.join("\n")
    );
}
