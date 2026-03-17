# Procurement Agent CLI

This project provides a CLI-based procurement assistant with four capabilities:
- category management
- anomaly detection
- intelligent recommendation
- package consolidation analysis

## Setup (Linux, uv + venv)

```bash
uv venv .venv
source .venv/bin/activate
uv sync
cp .env.example .env
```

## 1) Prepare SQLite Database

- database file: `pengadaan.db`
- tables: `dokumen_pengadaan`, `master_vendor`, `master_divisi`, `mapping_3_database`

## 2) Run Preflight Checks

```bash
uv run python -m src.main preflight
```

This validates:
- runtime skill pack
- output contract
- SQLite database health
- NVIDIA NIM connectivity (when enabled)

## 3) Run Query

```bash
uv run python -m src.main query "Sort HR procurement plans by highest HPS value"
```

## 4) Run Tests

```bash
uv run pytest
```

Test scope:
- unit
- integration
- contract
- safety
- performance smoke

Coverage gate:
- minimum 85%
