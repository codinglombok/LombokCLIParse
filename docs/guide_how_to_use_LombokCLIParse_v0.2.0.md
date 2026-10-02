# LombokCLIParse — Guide How to Use v0.2.0

## 1. Pemasangan

| Bahasa | Perintah | Syarat |
|---|---|---|
| Rust | `cargo add lombokcliparse` | Rust 1.70+ |
| TypeScript/JS | `npm install lombokcliparse` | Node.js 20+, Deno, Bun |
| Python | `pip install lombokcliparse` | Python 3.9+ |
| Go | `go get github.com/codinglombok/lombokcliparse/go` | Go 1.22+ |
| PHP | `composer require codinglombok/lombokcliparse` | PHP 8.1+ |

## 2. Mendefinisikan app

```python
app = (App("backup", "Copy files to an archive").version("2.1.0")
       .positional("source", "Directory to copy", required=True)
       .positional("target", "Archive path")
       .flag("verbose", "Show each file", short="v")
       .option("level", "Compression level", ArgType.INT, short="l", default="6", env_var="BACKUP_LEVEL"))
```

Aturan nama: huruf/digit ASCII, `-`, `_`; short satu huruf ASCII. `help` selalu disediakan; `version` disediakan bila ada versi.

## 3. Menulis baris perintah

| Bentuk | Arti |
|---|---|
| `backup src out.tar` | dua positional |
| `-v -l 9`, `-vl9`, `-vl=9`, `--level 9`, `--level=9` | flag verbose + option level 9 |
| `--offset -5` | nilai negatif diambil apa adanya |
| `backup -- -weird-name` | setelah `--` semuanya positional; sisanya masuk `rest` |
| `cli -v query text` | opsi induk sebelum subcommand |

## 4. Menangani hasil

```go
m, err := app.ParseWithEnv(os.Args[1:], os.LookupEnv)
var pe *cli.ParseError
if errors.As(err, &pe) {
    if pe.IsInfo() { fmt.Print(pe.Text); return }   // --help / --version
    fmt.Fprintln(os.Stderr, pe.Error()); os.Exit(2)  // "UNKNOWN_ARGUMENT: unknown argument '--x'"
}
```

Atau cukup `app.Run()`. Kode error stabil: `UNKNOWN_ARGUMENT`, `MISSING_VALUE`, `INVALID_VALUE`, `MISSING_REQUIRED`, `UNEXPECTED_ARGUMENT`, `UNKNOWN_SUBCOMMAND`, `FLAG_TAKES_NO_VALUE`, `INVALID_DEFINITION`.

## 5. Menguji CLI Anda

Gunakan `parse_with_env(tokens, env)` dengan lingkungan eksplisit supaya tes tidak bergantung pada variabel lingkungan mesin:

```ts
const m = app.parseWithEnv(['src', '-l', '3'], { BACKUP_LEVEL: '9' });
assert.equal(m.getInt('level'), 3); // baris perintah mengalahkan env
```

## 6. Skenario pemakaian

1. **Alat yang ditulis ulang ke bahasa lain.** Skrip Python dipindah ke Go. Pengguna tidak merasakan perbedaan karena opsi, pesan error, dan teks `--help`-nya sama.
2. **CLI npm dan biner Rust untuk alat yang sama.** Kedua distribusi menerima argumen dan mencetak help yang identik.
3. **Utilitas server.** Port dan berkas konfigurasi dibaca dari opsi, atau dari variabel lingkungan di kontainer.
4. **Skrip PHP baris perintah.** Subcommand `import`/`export` dengan validasi tipe tanpa dependensi Composer lain.
5. **Perangkat embedded dengan shell sederhana (Rust `no_std`).** Perintah teks di-parse dengan aturan yang sama dengan alat desktopnya.

## 7. Batasan

Lihat `full_summary_project_` §2: tanpa option berulang sebagai daftar, tanpa grup saling eksklusif, tanpa completion shell.

*Lisensi dokumen: Apache-2.0 · © codinglombok*
