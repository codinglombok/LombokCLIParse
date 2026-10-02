# LombokCLIParse — Map v0.2.0

## 1. Posisi di ekosistem

```
Cluster 01 Fondasi & Runtime · tingkat L0 (tanpa dependensi Lombok wajib)

L0  LombokCLIParse
     dependensi wajib    : (tidak ada)
     dependensi opsional : (tidak ada; rencana: LombokLocale untuk pesan terlokalisasi)
     dependensi dev      : serde_json (runner vector Rust), typescript + @types/node (TS), pytest + coverage (Python, CI)
```

## 2. Contoh pemakai di ekosistem

Library ini mandiri dan dapat dipakai siapa pun. Aplikasi dan library Lombok yang dapat memakainya (arah dependensi selalu pemakai ke library):

| Pemakai | Pemakaian |
|---|---|
| LombokDNSProxy (aplikasi) | opsi baris perintah server (port, upstream, berkas konfigurasi lewat env) |
| LombokMiner (aplikasi) | subcommand untuk job dan laporan |
| LombokFuzzer (library) | CLI harness fuzz (jumlah eksekusi, mode) |
| LombokPDF (aplikasi) | alat konversi baris perintah |

## 3. Peta fitur x port

| Fitur | Rust | TypeScript | Python | Go | PHP |
|---|---|---|---|---|---|
| positional, flag, option (SPEC §4) | YA | YA | YA | YA | YA |
| subcommand bertingkat | YA | YA | YA | YA | YA |
| env fallback + default | YA | YA | YA | YA | YA |
| validasi definisi (§2) | YA | YA | YA | YA | YA |
| teks help (§5) | YA | YA | YA | YA | YA |
| `run()` | YA | YA | YA | YA | YA |
| vector | 133/134* | 134/134 | 134/134 | 133/134* | 134/134 |

\* satu kasus memakai short dua karakter, yang tidak dapat dinyatakan dengan tipe `char`/`rune`; aturan yang sama diuji lewat tes API (short non-ASCII).

*Lisensi dokumen: Apache-2.0 · © codinglombok*
