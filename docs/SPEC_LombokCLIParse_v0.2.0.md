# LombokCLIParse — SPEC v0.2.0

This document is the normative cross-language contract. Every language port MUST produce byte-identical output for all specified inputs. Deviations from this specification are bugs.

| Atribut | Nilai |
|---|---|
| Versi SPEC | 0.2.0 (berlaku untuk paket `lombokcliparse` 0.2.x di crates.io, npm, PyPI, Packagist, dan modul Go) |
| Acuan | POSIX.1-2024 XBD 12.2 "Utility Syntax Guidelines" (pengelompokan opsi pendek, `--` sebagai akhir opsi); konvensi GNU `--name=value`; IEEE 754 binary64 untuk float; Unicode 15.1 (hitungan code point); tinjauan 2026-10-02 |
| Vector | `vectors/lombokcliparse-vectors-v1.json` — 134 kasus (parse 24, float 18, error 16, def 15, int 12, help 12, bool 11, sub 8, num 8, env 6, version 4) — SHA-256 `2243ea8bb26914066b8e47e6185d8d34458594083fb13911a02c0879825fd504` |
| Pemeriksa referensi | implementasi Python independen di `vectors/build_vectors.py`; kasus tulis tangan divalidasi terhadapnya |
| Port | Rust, TypeScript, Python, Go, PHP — kelimanya menjalankan seluruh vector (Rust dan Go melewati satu kasus short dua karakter yang tidak dapat ditulis dengan tipe `char`/`rune`) |
| Tanggal tinjauan | 2026-10-02 |

Kata MUST, MUST NOT, SHOULD, MAY mengikuti RFC 2119.

## 0. Konvensi

1. Masukan adalah daftar token string Unicode, tanpa nama program. API "parse dari argv" membuang elemen pertama.
2. "Code point" adalah satuan karakter untuk pengelompokan opsi pendek (§4.3) dan lebar kolom help (§5). UTF-16 dan byte MUST NOT dipakai sebagai satuan.
3. Lingkungan (environment) adalah pemetaan nama → nilai yang dapat diberikan secara eksplisit. Vector selalu memberikannya secara eksplisit.

## 1. Model

Sebuah app punya nama, deskripsi (boleh kosong), versi (opsional), daftar argumen positional, daftar argumen bernama (flag dan option, dalam urutan definisi), dan daftar subcommand (masing-masing juga app).

| Jenis | Bentuk | Nilai |
|---|---|---|
| positional | token biasa, diisi menurut urutan definisi | bertipe (§3) |
| flag | `--name` atau `-c` | ada/tidak |
| option | `--name value`, `--name=value`, `-c value`, `-cvalue`, `-c=value` | bertipe (§3); bila tidak diberikan: env, lalu default |

## 2. Aturan definisi

Dilanggar → `INVALID_DEFINITION` dengan `arg` = nama atau huruf yang bermasalah, dan `reason` sesuai tabel. Pemeriksaan MUST dilakukan untuk seluruh pohon app sebelum token pertama dibaca, dengan urutan berikut:

1. Untuk setiap positional, lalu setiap argumen bernama (urutan definisi):
   1. nama tidak cocok dengan `^[A-Za-z0-9][A-Za-z0-9_-]*$` → `invalid name`;
   2. nama `help`, atau `version` bila app punya versi → `reserved name`;
   3. nama sudah dipakai di app yang sama → `duplicate name` (positional, flag, dan option berbagi satu ruang nama);
   4. short ada dan bukan satu huruf ASCII `[A-Za-z]` → `invalid short` (digit dilarang supaya `-5` selalu bilangan negatif);
   5. short sudah dipakai → `duplicate short`;
   6. default option ada dan tidak valid untuk tipenya → `invalid default`.
2. Positional wajib setelah positional opsional → `required after optional`.
3. App yang punya subcommand MUST NOT punya positional → `positionals with subcommands` (arg = nama subcommand pertama).
4. Untuk setiap subcommand: nama tidak valid → `invalid name`; nama ganda → `duplicate name`; lalu aturan 1-4 diterapkan rekursif.

## 3. Nilai

| Tipe | Diterima | Hasil |
|---|---|---|
| string | teks apa pun, termasuk kosong | teks |
| int | `^[+-]?[0-9]+$` dengan nilai dalam ±(2^53 − 1) | bilangan bulat; `-0` menjadi `0` |
| float | `^[+-]?([0-9]+(\.[0-9]*)?\|\.[0-9]+)([eE][+-]?[0-9]+)?$`, dibulatkan benar ke binary64; hasil tak hingga ditolak, underflow ke 0 diterima | binary64 |
| bool | `true`, `false`, `1`, `0`, `yes`, `no`, `on`, `off`, tidak peka huruf besar/kecil ASCII; teks non-ASCII ditolak | boolean |

Tata bahasa ini MUST dipakai apa adanya. Parser bawaan bahasa yang lebih longgar (misalnya Python `int("1_000")`, `float("inf")`, atau JavaScript `Number("0x10")`) MUST NOT menentukan hasil. Rentang int dibatasi 2^53 − 1 supaya nilainya tepat di semua port, termasuk JavaScript.

## 4. Parsing

### 4.1 Status

`pos_idx` (positional berikutnya), `after_dd` (sesudah `--`). Token dibaca satu per satu; masalah pertama dalam urutan token yang dilaporkan.

### 4.2 Token

Untuk setiap token `t`, selama `after_dd` salah:

1. `t == "--"` → `after_dd` menjadi benar; token berikutnya.
2. `t == "--help"` → hasil HELP dengan teks help app saat ini (§5); parsing berhenti.
3. `t == "--version"` dan app punya versi → hasil VERSION dengan teks `nama + " " + versi + "\n"`. Tanpa versi, `--version` diperlakukan seperti argumen panjang biasa (umumnya `UNKNOWN_ARGUMENT`).
4. `t` diawali `--` → argumen panjang (§4.3).
5. `t` diawali `-`, panjangnya lebih dari 1, dan karakter kedua bukan digit ASCII atau `.` → kelompok pendek (§4.3).
6. Selain itu, `t` adalah token positional (§4.4). Ini mencakup `-`, `-5`, `-.5`, dan semua token setelah `--`.

### 4.3 Argumen bernama

Panjang: badan = `t` tanpa `--`; dipisah pada `=` pertama menjadi nama dan nilai inline.
- Nama tidak dikenal → `UNKNOWN_ARGUMENT`, `arg` = `--nama` (tanpa nilai inline).
- Flag dengan nilai inline → `FLAG_TAKES_NO_VALUE`.
- Option tanpa nilai inline mengambil token berikutnya **apa adanya**, termasuk yang diawali `-`. Bila tidak ada token berikutnya → `MISSING_VALUE`.
- Nilai tidak valid → `INVALID_VALUE`, `arg` = `--nama`, `value` = teks mentah.

Pendek: karakter setelah `-` dibaca per code point dari kiri.
- Huruf flag → flag diset, lanjut ke huruf berikutnya.
- Huruf option → sisa karakter adalah nilainya, setelah membuang satu `=` di depan bila ada. Bila sisanya kosong, token berikutnya diambil apa adanya (atau `MISSING_VALUE`). Kelompok selesai.
- Huruf tak dikenal → `UNKNOWN_ARGUMENT`, `arg` = `-` + code point tersebut.

Flag yang diulang tetap satu flag. Option yang diulang: nilai terakhir menang.

### 4.4 Token positional

1. Bila `after_dd` salah dan app punya subcommand: token MUST sama dengan nama subcommand, bila tidak → `UNKNOWN_SUBCOMMAND`. Sisa token di-parse oleh subcommand itu (dengan path help `path + " " + nama`), dan parsing app ini selesai. Opsi milik app induk harus ditulis sebelum nama subcommand. Subcommand boleh tidak dipilih.
2. Bila masih ada positional (`pos_idx` < jumlah) → nilai di-parse dengan tipenya (`INVALID_VALUE`, `arg` = nama positional), lalu `pos_idx` bertambah.
3. Bila `after_dd` benar → token masuk `rest`.
4. Selain itu → `UNEXPECTED_ARGUMENT`.

### 4.5 Penyelesaian

Setelah semua token (atau setelah subcommand dipilih):
1. Untuk setiap option yang tidak diberikan, menurut urutan definisi: bila variabel env-nya ada (nilai kosong juga dihitung ada), nilainya di-parse; bila tidak, default-nya dipakai. Nilai env yang tidak valid → `INVALID_VALUE` dengan `arg` = `--nama`.
2. Positional wajib yang kosong → `MISSING_REQUIRED`, `arg` = nama positional (yang pertama menurut urutan definisi).

### 4.6 Hasil

`values` (nama → nilai bertipe), `flags` (himpunan nama), `rest` (daftar), dan `subcommand` (nama + hasil, atau tidak ada). Di vector: int ditulis sebagai string desimal, float sebagai pola bit binary64, dan flag diurutkan.

## 5. Teks help

```
{nama}[ {versi}]
[{deskripsi}]                    baris ini tidak ada bila deskripsi kosong

USAGE:
    {path} [OPTIONS][ <COMMAND>][ <POS>| [POS]]...

[ARGS:
    <POS>  {help} [(required)]
]
[COMMANDS:
    {nama}  {deskripsi}
]
OPTIONS:
    -c, --nama <TIPE>  {help} [default: X] [env: Y]
        --help         Print help
       [--version      Print version]
```

1. `path` = nama app, atau rantai nama dari akar untuk subcommand (`cli query`).
2. Nama positional ditulis dengan huruf besar ASCII. Usage menulis `<NAMA>` untuk yang wajib dan `[NAMA]` untuk yang opsional.
3. Bagian ARGS dan COMMANDS hanya ada bila tidak kosong. Bagian OPTIONS selalu ada. Bagian dipisah oleh satu baris kosong. Teks berakhir dengan `\n` setelah baris terakhir.
4. Kolom kiri:

   | Baris | Kolom kiri |
   |---|---|
   | positional | `<NAMA>` |
   | subcommand | namanya |
   | flag | `-c, --nama` atau `    --nama` (empat spasi bila tanpa short) |
   | option | seperti flag, ditambah placeholder: `<VALUE>` (string), `<INT>`, `<FLOAT>`, `<BOOL>` |

5. Kolom kanan: bagian yang tidak kosong dari [help, `(required)`] atau [help, `[default: X]`, `[env: Y]`], digabung dengan satu spasi.
6. Lebar kolom kiri dihitung per bagian: panjang terbesar dalam code point. Setiap baris = 4 spasi + kiri + spasi sampai lebar + 2 spasi + kanan. Bila kanan kosong, baris hanya 4 spasi + kiri, tanpa spasi di akhir.
7. Baris `--help` selalu ada; baris `--version` ada bila app punya versi.

## 6. Error dan hasil info

| Kode | Pesan setelah `"KODE: "` |
|---|---|
| `UNKNOWN_ARGUMENT` | `unknown argument '{arg}'` |
| `MISSING_VALUE` | `missing value for '{arg}'` |
| `INVALID_VALUE` | `invalid value '{value}' for '{arg}'` |
| `MISSING_REQUIRED` | `missing required argument '{arg}'` |
| `UNEXPECTED_ARGUMENT` | `unexpected argument '{arg}'` |
| `UNKNOWN_SUBCOMMAND` | `unknown subcommand '{arg}'` |
| `FLAG_TAKES_NO_VALUE` | `flag '{arg}' does not take a value` |
| `INVALID_DEFINITION` | `{reason}: '{arg}'` |
| `HELP`, `VERSION` | bukan error; teks help/version dibawa apa adanya |

| Port | Bentuk |
|---|---|
| Rust | `Err(ParseError)`; `code()`, `arg()`, `value()`, `is_info()`, `Display` = pesan |
| TypeScript | `throw ParseError` dengan `code`, `arg`, `value`, `text`, `isInfo`, `message` |
| Python | `raise ParseError` dengan `code`, `arg`, `value`, `text`, `is_info`, `str(e)` |
| Go | `error` bertipe `*ParseError` dengan `Code`, `Arg`, `Value`, `Text`, `IsInfo()` |
| PHP | `throw ParseError` dengan `errorCode`, `arg`, `value`, `text`, `isInfo()`, `getMessage()` |

Setiap port menyediakan `run()`. Fungsi ini mem-parse argv proses, lalu:
- HELP/VERSION: mencetak teksnya ke stdout dan keluar dengan status 0;
- error: mencetak `error: {pesan}` ke stderr dan keluar dengan status 2.

Parsing itu sendiri tidak pernah mencetak atau mengakhiri proses.

## 7. Keamanan (normatif)

1. Parser tidak mengeksekusi, tidak mengakses berkas, dan tidak mengubah lingkungan. Satu-satunya akses ke lingkungan adalah pencarian variabel yang dideklarasikan untuk option.
2. Waktu O(token × argumen terdefinisi), memori linear. Tidak ada rekursi yang bergantung pada masukan, kecuali kedalaman subcommand yang ditentukan oleh definisi.
3. Nilai mentah dimuat dalam pesan error apa adanya. Aplikasi yang menampilkan pesan di terminal sebaiknya menyaring karakter kontrol bila argumen berasal dari pihak yang tidak tepercaya.
4. Rust: `#![forbid(unsafe_code)]`. Tidak ada dependensi runtime di semua port.

## 8. Perubahan dari 0.1.0

Rilis 0.x; perilaku 0.1 berbeda di setiap port. Perubahan utama:

- `--help` tidak lagi memanggil `exit` dari dalam library; hasilnya dikembalikan sebagai HELP;
- `--version` ditambahkan;
- bilangan negatif menjadi positional, bukan opsi tak dikenal;
- `--flag=value` ditolak;
- default dan env yang tidak valid kini menjadi error (sebelumnya diabaikan);
- positional berlebih menjadi `UNEXPECTED_ARGUMENT`, kecuali setelah `--`;
- teks help seragam, dengan lebar kolom dinamis (sebelumnya terpotong pada nama lebih dari 16 karakter);
- tata bahasa int/float/bool seragam;
- definisi divalidasi;
- path modul Go menjadi `github.com/codinglombok/lombokcliparse/go`.

*Lisensi dokumen: Apache-2.0 · © codinglombok*
