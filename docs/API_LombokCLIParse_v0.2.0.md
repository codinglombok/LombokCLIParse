# LombokCLIParse — API v0.2.0

Perilaku normatif ada di SPEC. Dokumen ini memetakan konsep SPEC ke nama di setiap port.

## 1. Ringkasan lintas port

| Konsep (SPEC) | Rust | TypeScript | Python | Go | PHP |
|---|---|---|---|---|---|
| buat aplikasi | `App::new(name, desc)` | `new App(name, desc)` | `App(name, desc)` | `NewApp(name, desc)` | `new App($name, $desc)` |
| versi | `.version(v)` | `.version(v)` | `.version(v)` | `.Version(v)` | `->version($v)` |
| positional | `.positional(n, h, ty, req)` | `.positional(n, h, type?, req?)` | `.positional(n, h, arg_type=, required=)` | `.Positional(n, h, t, req)` | `->positional($n, $h, $type, $req)` |
| flag | `.flag(n, h, Some('v'))` | `.flag(n, h, 'v'?)` | `.flag(n, h, short=)` | `.Flag(n, h, 'v')` (0 = tanpa) | `->flag($n, $h, 'v')` |
| option | `.option(n, h, ty, short, default, env)` | `.option(n, h, type, short?, default?, env?)` | `.option(n, h, arg_type, short=, default=, env=)` | `.Option(n, h, t, short, def, env)` (`""` = tanpa) / `.OptionFull(...)` | `->option($n, $h, $type, $short, $default, $envVar)` |
| subcommand | `.subcommand(app)` | `.subcommand(app)` / `.sub` | `.subcommand(app)` / `.sub` | `.Subcommand(app)` / `.Sub` | `->subcommand($app)` / `->sub` |
| validasi definisi | `validate() -> Result<(), ParseError>` | `validate()` (throw) | `validate()` (raise) | `Validate() error` | `validate()` (throw) |
| teks help | `help() -> String` | `help()` | `help()` | `Help()` | `help()` |
| parse argv lengkap | `parse_from(&argv)` | `parse(argv)` | `parse(argv)` | `Parse(args)` | `parse($argv)` |
| parse token + env | `parse_with_env(&tokens, fn)` | `parseWithEnv(tokens, fn \| record)` | `parse_with_env(tokens, fn \| dict)` | `ParseWithEnv(tokens, EnvLookup)` | `parseWithEnv($tokens, array \| callable)` |
| parse proses | `parse_env()` | `parseEnv()` | `parse_env()` | `ParseEnv()` | `parseEnv()` |
| perilaku CLI | `run()` | `run()` | `run()` | `Run()` | `run()` |
| tata bahasa nilai | `parse_value(ty, raw)` | `parseValue(type, raw)` | `parse_value(type, raw)` | `ParseValue(t, raw)` | `App::parseValue($type, $raw)` |
| kode error | `e.code()` | `e.code` | `e.code` | `e.Code` | `$e->errorCode` |
| argumen / nilai | `e.arg()` / `e.value()` | `e.arg` / `e.value` | `e.arg` / `e.value` | `e.Arg` / `e.Value` | `$e->arg` / `$e->value` |
| help/version bukan kegagalan | `e.is_info()` | `e.isInfo` | `e.is_info` | `e.IsInfo()` | `$e->isInfo()` |

`parse*` tanpa akhiran `with_env` menerima argv lengkap (elemen pertama adalah nama program dan diabaikan). `parse_with_env` menerima token tanpa nama program. `run()` mencetak help/version ke stdout lalu keluar dengan 0, atau mencetak `error: CODE: message` ke stderr lalu keluar dengan 2.

## 2. Kode error

| Kode | Arti | `arg` | `value` |
|---|---|---|---|
| `UNKNOWN_ARGUMENT` | opsi panjang/pendek tidak terdefinisi | argumen seperti ditulis | - |
| `MISSING_VALUE` | opsi di akhir baris tanpa nilai | opsi | - |
| `INVALID_VALUE` | nilai tidak sesuai tipe (argv, env, atau default) | opsi atau nama positional | teks yang ditolak |
| `MISSING_REQUIRED` | positional wajib tidak ada | nama positional | - |
| `UNEXPECTED_ARGUMENT` | positional berlebih | token | - |
| `UNKNOWN_SUBCOMMAND` | token bukan subcommand yang dikenal | token | - |
| `FLAG_TAKES_NO_VALUE` | `--flag=x` | flag | - |
| `INVALID_DEFINITION` | definisi melanggar SPEC §2 (`reason` berisi aturannya) | nama atau huruf pendek | - |
| `HELP` / `VERSION` | `--help` / `--version`; `text` berisi teks yang dicetak | `""` | - |

Pesan error: `CODE: message`, identik di semua port (SPEC §6).

## 3. Rust (`lombokcliparse`)

| Item | Tanda tangan |
|---|---|
| `ArgType` | `enum { Str, Int, Float, Bool }` |
| `Value` | `enum { Str(String), Int(i64), Float(f64), Bool(bool) }` |
| `MAX_SAFE_INTEGER` | `const i64 = 2^53 - 1` |
| `parse_value` | `fn parse_value(ty: ArgType, raw: &str) -> Option<Value>` |
| `ParseError` | enum `UnknownArgument{arg}`, `MissingValue{arg}`, `InvalidValue{arg, value}`, `MissingRequired{arg}`, `UnexpectedArgument{arg}`, `UnknownSubcommand{arg}`, `FlagTakesNoValue{arg}`, `InvalidDefinition{arg, reason}`, `Help(String)`, `Version(String)`; `code()`, `arg()`, `value()`, `is_info()`; `Display` = pesan SPEC; `std::error::Error` (fitur `std`) |
| `App` | builder dengan pemilik (`self -> Self`): `new`, `version`, `positional`, `flag(name, help, Option<char>)`, `option(name, help, ArgType, Option<char>, Option<&str>, Option<&str>)`, `subcommand`; `validate`, `help`, `parse_from<S: AsRef<str>>(&[S])`, `parse_with_env(&[S], impl Fn(&str) -> Option<String>)`; `parse_env`, `run` (fitur `std`) |
| `Matches` | `get_str -> Option<&str>`, `get_int -> Option<i64>`, `get_float -> Option<f64>`, `get_bool -> bool`, `get -> Option<&Value>`, `values()`, `flags()`, `subcommand() -> Option<(&str, &Matches)>`, `rest() -> &[String]` |
| fitur | `std` (bawaan); tanpa `std` crate tetap `no_std` + `alloc` |

## 4. TypeScript (`lombokcliparse`)

| Item | Tanda tangan |
|---|---|
| `ArgType` | `enum { Str = 'string', Int = 'int', Float = 'float', Bool = 'bool' }` |
| `Value` | `string \| number \| boolean` |
| `parseValue` | `(type: ArgType, raw: string) => Value \| undefined` |
| `ParseError` | `extends Error`; `code: ParseErrorCode`, `arg`, `value?`, `reason?`, `text?`, getter `isInfo` |
| `App` | `version`, `positional`, `flag`, `option`, `subcommand`/`sub`, `validate()`, `help()`, `parse(argv)`, `parseWithEnv(tokens, EnvLookup \| Record)`, `parseEnv()` (`process.argv.slice(1)`), `run()` |
| `Matches` | `getStr`, `getInt`, `getFloat`, `getBool`, `get`, `typeOf(name): ArgType \| undefined`, `values(): [string, Value][]`, `flags()`, `subcommand(): {name, matches} \| undefined`, `rest()` |

## 5. Python (`lombokcliparse`)

| Item | Tanda tangan |
|---|---|
| `ArgType` | `Enum`: `STR`, `INT`, `FLOAT`, `BOOL` |
| `parse_value` | `(arg_type, raw) -> Optional[Value]` |
| `ParseError` | `Exception`; atribut `code`, `arg`, `value`, `reason`, `text`; properti `is_info` |
| `App` | `version`, `positional`, `flag`, `option`, `subcommand`/`sub`, `validate()`, `help()`, `parse(argv)`, `parse_with_env(tokens, env)`, `parse_env()` (`sys.argv`), `run()` |
| `Matches` | `get_str`, `get_int`, `get_float`, `get_bool`, `get`, `type_of`, `values()`, `flags()`, `subcommand() -> Optional[Tuple[str, Matches]]`, `rest()` |

## 6. Go (`github.com/codinglombok/lombokcliparse/go`, package `lombokcliparse`)

| Item | Tanda tangan |
|---|---|
| `ArgType` | `string`: `TypeStr`, `TypeInt`, `TypeFloat`, `TypeBool` |
| `Value` | `struct{ Type ArgType; Str string; Int int64; Float float64; Bool bool }` |
| `ParseValue` | `func ParseValue(t ArgType, raw string) (Value, bool)` |
| `ParseError` | `struct{ Code, Arg, Value, Reason, Text string }`; `Error()`, `IsInfo()`; dapatkan dengan `errors.As` |
| `App` | `NewApp`, `Version`, `Positional`, `Flag(name, help, rune)`, `Option(name, help, t, short, def, env)` (string kosong = tidak ada), `OptionFull(..., def, hasDefault, env, hasEnv)` (default kosong yang sah), `Subcommand`/`Sub`, `Validate() error`, `Help()`, `Parse([]string)`, `ParseWithEnv([]string, EnvLookup)`, `ParseEnv()`, `Run()` |
| `EnvLookup` | `func(name string) (string, bool)`; `os.LookupEnv` cocok langsung |
| `Matches` | `GetStr`, `GetInt`, `GetFloat` (masing-masing dengan `ok`), `GetBool`, `Get`, `Names()`, `Flags()`, `Subcommand() (string, *Matches, bool)`, `Rest()` |

## 7. PHP (`codinglombok/lombokcliparse`, namespace `LombokCLIParse`)

| Item | Tanda tangan |
|---|---|
| `ArgType` | backed enum `STR = 'string'`, `INT`, `FLOAT`, `BOOL` |
| `Value` | `type`, `str`, `int`, `float`, `bool`; konstruktor `Value::str/int/float/bool` |
| `ParseError` | `extends RuntimeException`; properti readonly `errorCode`, `arg`, `value`, `reason`, `text`; `isInfo()`; `getMessage()` = pesan SPEC |
| `App` | `version`, `positional`, `flag`, `option`, `subcommand`/`sub`, `validate()`, `help()`, `parse(array $argv)`, `parseWithEnv(array $tokens, array\|callable $env)`, `parseEnv()` (`$_SERVER['argv']`), `run()`, statis `parseValue` |
| `Matches` | `getStr`, `getInt`, `getFloat`, `getBool`, `get`, `hasValue`, `values()`, `flags()`, `subcommand(): ?array{string, Matches}`, `rest()` |

## 8. Kompatibilitas dengan 0.1.0

0.2.0 mengubah perilaku di semua port; lihat CHANGELOG bagian Changed. Nama builder (`App`, `version`, `positional`, `flag`, `option`, `subcommand`) dan getter `Matches` dipertahankan. Yang berubah: `--help` tidak lagi menghentikan proses dari dalam library (pakai `run()`), error menjadi tipe `ParseError` dengan kode, path modul Go menjadi huruf kecil.

*Lisensi dokumen: Apache-2.0 · © codinglombok*
