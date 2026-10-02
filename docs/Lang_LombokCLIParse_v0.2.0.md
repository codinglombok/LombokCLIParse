# LombokCLIParse — Bahasa & i18n v0.2.0

| Atribut | Nilai |
|---|---|
| Versi | 0.2.0 |
| Tingkat i18n (masterplan §13) | **E**: kode error, pesan bahasa Inggris, dokumentasi; nilai Unicode diterima apa adanya |
| Katalog pesan | belum ada berkas `locales/`; ID pesan dicadangkan di §2 |
| Fallback | teks bahasa Inggris tertanam di kode (SPEC §6) |
| Cakupan katalog saat ini | en + id (2/20) di tabel §2; Nusantara 0/6 |

## 1. Prinsip

1. Program MUST memeriksa kode error, bukan teks pesan.
2. Nilai argumen diterima sebagai Unicode apa pun dan tidak dinormalisasi. Lebar kolom help dihitung per code point. Aksara yang lebar di terminal (CJK, emoji) dapat membuat kolom tidak rata secara visual; ini tercatat sebagai batasan.
3. Bool hanya mengenali kata bahasa Inggris (`true/false/yes/no/on/off/1/0`) supaya hasil tidak bergantung locale.
4. Tidak ada format angka lokal: float memakai titik desimal.

## 2. Katalog ID pesan (dicadangkan)

| ID | Kode | en | id |
|---|---|---|---|
| `lombokcliparse.unknown_argument` | `UNKNOWN_ARGUMENT` | unknown argument '{$arg}' | argumen tidak dikenal '{$arg}' |
| `lombokcliparse.missing_value` | `MISSING_VALUE` | missing value for '{$arg}' | nilai untuk '{$arg}' tidak ada |
| `lombokcliparse.invalid_value` | `INVALID_VALUE` | invalid value '{$value}' for '{$arg}' | nilai '{$value}' tidak valid untuk '{$arg}' |
| `lombokcliparse.missing_required` | `MISSING_REQUIRED` | missing required argument '{$arg}' | argumen wajib '{$arg}' tidak ada |
| `lombokcliparse.unexpected_argument` | `UNEXPECTED_ARGUMENT` | unexpected argument '{$arg}' | argumen tidak terduga '{$arg}' |
| `lombokcliparse.unknown_subcommand` | `UNKNOWN_SUBCOMMAND` | unknown subcommand '{$arg}' | subcommand tidak dikenal '{$arg}' |
| `lombokcliparse.flag_takes_no_value` | `FLAG_TAKES_NO_VALUE` | flag '{$arg}' does not take a value | flag '{$arg}' tidak menerima nilai |
| `lombokcliparse.help.usage` | — | USAGE / ARGS / COMMANDS / OPTIONS / Print help / Print version | PENGGUNAAN / ARGUMEN / PERINTAH / OPSI / Tampilkan bantuan / Tampilkan versi |

## 3. RTL

Teks help ditulis dari kiri ke kanan dengan kolom berbasis spasi. Untuk deskripsi berbahasa Arab, Persia, atau Urdu, kolom kiri tetap LTR; tampilan bergantung pada terminal.

## 4. Rencana

- Pesan dan judul help terlokalisasi lewat LombokLocale (opsional), sementara keluaran bawaan (bahasa Inggris) tetap menjadi kontrak SPEC dan vector.

*Lisensi dokumen: Apache-2.0 · © codinglombok*
