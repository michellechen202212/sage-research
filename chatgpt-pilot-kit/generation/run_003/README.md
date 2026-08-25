# Commerce Investigation API

A deterministic, dependency-free Python API over the supplied synthetic commerce data. It exposes customer activity, order and receipt details, payment activity, returns/refunds, and a unified chronological timeline while preserving source grains and identities.

## Requirements

- Python 3.10 or newer
- No third-party packages and no network access at runtime

## Setup and run

From this directory:

```powershell
python app.py --rebuild
```

The server listens on `http://127.0.0.1:8000`. `--rebuild` creates `investigation.db` from the supplied, unmodified `schema.sql` and `seed.sql`. On later runs, omit it to reuse the database. Optional arguments are `--host`, `--port`, and `--database`.

Available GET routes:

- `/api/customers`
- `/api/customers/C1`
- `/api/customers/C1/timeline`
- `/api/orders/O1`
- `/api/receipts/R1`
- `/api/payments/P1`
- `/api/returns/RET1`

Example:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/customers/C1/timeline
```

## Tests

```powershell
python -m unittest discover -s tests -v
```

Tests use temporary SQLite databases and an ephemeral local HTTP port. They exercise identity, grain, independent-child, monetary-lineage, timestamp-meaning, event-separation, and timeline semantics.

## Response conventions

Every serving object declares `grain`. Money objects include a decimal string, `semantic_type`, and source/aggregation `lineage`; currency is explicitly `UNKNOWN` because the source does not provide one. Timestamp objects contain both their source value and event meaning. Collections nest only along explicit foreign-key relationships. The timeline is marked as a derived projection and links each typed event back to its source fact.
