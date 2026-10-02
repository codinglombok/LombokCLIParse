# LombokCLIParse — Structure Repo v0.2.0

```
LombokCLIParse/
├── README.md · CHANGELOG.md · LICENSE (Apache-2.0)
├── .github/workflows/  ci.yml (5 port + standards) · release.yml (terbit pada tag v*)
├── docs/               10 dokumen publik; masterplan_ dan architecture_ adalah dokumen internal (ADR-024), tidak di-commit
├── vectors/            lombokcliparse-vectors-v1.json · SHA256SUMS · build_vectors.py (implementasi referensi Python)
├── scripts/            lombok-doctor.sh (pemeriksaan standar v3.6)
├── rust/               Cargo.toml · src/lib.rs · tests/{vectors,api}.rs
├── typescript/         package.json · src/index.ts · tests/{api,vectors}.test.ts · scripts/coverage.mjs
├── python/             pyproject.toml · lombokcliparse/__init__.py · tests/{test_api,test_vectors}.py
├── go/                 go.mod · cliparse.go · {cliparse,vectors}_test.go
└── php/                composer.json · src/{App,ArgType,Matches,ParseError,Value}.php · tests/{run,api,vectors,bootstrap}.php
```

Aturan: perubahan perilaku mengubah SPEC dan vector lebih dulu, lalu kelima port; setiap port punya README, LICENSE, dan manifest sendiri; hasil build tidak di-commit.

*Lisensi dokumen: Apache-2.0 · © codinglombok*
