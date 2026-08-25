# Commerce Investigation API

A deterministic, read-only JSON API over the supplied synthetic commerce schema and fixtures. It uses only Python's standard library and creates an in-memory SQLite database at startup; the supplied `schema.sql` and `seed.sql` remain unchanged.

## Requirements

- Python 3.10 or newer

No installation or network access is required.

## Run

From this directory:

```powershell
python app.py
```

The server listens on `http://127.0.0.1:8000`. Use `python app.py --host 0.0.0.0 --port 9000` to choose another address.

Useful endpoints:

- `GET /health`
- `GET /customers`
- `GET /customers/C1` — customer orders, receipts, returns, and refunds
- `GET /orders/O1` — lines, fulfillment, payments, authorizations, settlements, and returns
- `GET /receipts/R1` — item occurrences, individual tender legs, and returns
- `GET /customers/C1/timeline` — unified chronological investigation activity

Amounts are JSON strings with two decimal places and quantities are strings with three decimal places, preserving the precision implied by the schema.

## Test

```powershell
python -m unittest discover -v
```

Tests load a fresh in-memory database from the fixtures for each case.
