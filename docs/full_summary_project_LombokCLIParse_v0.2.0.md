# LombokCLIParse — Full Summary Project v0.2.0

| Item | Nilai |
|---|---|
| Deskripsi | Parser baris perintah (positional, flag, option bertipe, subcommand, env, help) dengan hasil, pesan error, dan teks help yang sama di 5 bahasa; tanpa dependensi runtime |
| Cluster · tingkat | 01 Fondasi & Runtime · L0 |
| Referensi | SPEC + implementasi Python di `vectors/build_vectors.py`; kelima port setara |
| Port | Rust (`no_std` + `alloc`), TypeScript, Python, Go, PHP |
| Vector | 134 kasus · SHA-256 `2243ea8b...25fd504` |
| Test | Rust 5 tes API + runner vector + doctest · TS 139 · Python 140 · Go tes API + runner vector · PHP 22 cek API + 135 cek vector |
| Coverage | Rust 97,4% baris · TS 96,8% baris / 98,5% cabang · Python 100% · Go 97,8% · PHP 97,7% baris |
| Registry | crates.io, npm, PyPI `lombokcliparse`; Go `github.com/codinglombok/lombokcliparse/go`; Packagist `codinglombok/lombokcliparse` (semua belum terbit) |
| Lisensi | Apache-2.0 |

## 1. Tabel gap vs pembanding (jujur)

| Kemampuan | LombokCLIParse 0.2.0 | clap (Rust) | argparse (Python) | cobra (Go) | commander (JS) |
|---|---|---|---|---|---|
| Perilaku dan teks help identik lintas bahasa (SPEC + vector) | YA | TIDAK | TIDAK | TIDAK | TIDAK |
| Subcommand bertingkat | YA | YA | YA | YA | YA |
| Env fallback per option | YA | YA (fitur `env`) | TIDAK | lewat viper | TIDAK |
| Parsing tidak mencetak/keluar (dapat disematkan) | YA | YA (`try_get_matches`) | parsial (`exit_on_error`) | YA | parsial |
| Option berulang sebagai daftar, flag berhitung | TIDAK | YA | YA | YA | YA |
| Grup saling eksklusif, dependensi antar-opsi | TIDAK | YA | YA | YA | parsial |
| Completion shell | TIDAK | YA | pihak ketiga | YA | pihak ketiga |
| Derive/annotation API | TIDAK | YA | TIDAK | TIDAK | TIDAK |
| Tanpa dependensi | YA | TIDAK (opsional) | YA (stdlib) | TIDAK | YA |

Posisi unik yang dibuktikan test: satu definisi CLI berperilaku sama persis, sampai ke teks help dan pesan error, di lima bahasa. Ini berguna bila sebuah alat punya beberapa implementasi (misalnya CLI Node dan biner Rust) atau dipindah antar-bahasa.

## 2. Batasan yang Diketahui

1. Tidak ada option berulang sebagai daftar (nilai terakhir menang) dan tidak ada flag berhitung.
2. Tidak ada grup saling eksklusif, option wajib, atau validasi antar-opsi; aplikasi memeriksanya sendiri setelah parse.
3. Tidak ada completion shell dan tidak ada pemotongan teks help sesuai lebar terminal.
4. Pesan error hanya dalam bahasa Inggris (lihat `Lang_`).
5. Nama argumen dan short hanya ASCII; nilai boleh Unicode apa pun.
6. Rust dan Go menerima short sebagai `char`/`rune`, sehingga short multi-karakter tidak dapat ditulis. Validasinya tetap diuji, tetapi satu kasus vector dilewati di kedua port itu.
7. Paket PHP berada di subdirektori; Packagist butuh repositori split.
8. Rust `run()` dan pembacaan env proses membutuhkan fitur `std`; tanpa `std`, gunakan `parse_with_env`.

## 3. Prinsip Universal (ringkas, untuk publik)

| Prinsip | Status | Bukti |
|---|---|---|
| U1 Mandiri | YA | README tanpa klaim kepemilikan; skenario netral di guide_ §6 |
| U2 Modern | YA | SPEC: POSIX.1-2024 Utility Syntax Guidelines, IEEE 754, Unicode 15.1, tanggal tinjauan |
| U3 Multi-platform | YA | CI ubuntu/windows/macos; Rust `no_std` + `alloc` |
| U4 Multi-bahasa | YA | 5 port, runner vector di semua port |
| U5 Rentang skala | SEBAGIAN | skrip kecil hingga alat bersubcommand; tanpa fitur CLI besar (completion, grup) |
| U6 Lengkap & unik | SEBAGIAN | tabel gap di atas |
| U7 Aman & teruji | YA | SPEC §7; `forbid(unsafe_code)`; coverage ≥ 96% di semua port |
| U8 Ekosistem tanpa kopling | YA | 0 dependensi wajib |
| U9 Internasional | SEBAGIAN | Lang_: tingkat E; nilai Unicode, padding per code point |
| U10 Lisensi | YA | Apache-2.0 di root dan setiap port |
| U11 Siap registri | SEBAGIAN | crates/npm/PyPI/Go siap; Packagist butuh split repo |
| U12 Dokumentasi | YA | 10 dokumen publik + 2 internal |
| U13 Kerahasiaan & dokumen bersih | YA | `lombok-doctor.sh`: 0 emoji, `.gitignore` ADR-024 |

*Lisensi dokumen: Apache-2.0 · © codinglombok*
