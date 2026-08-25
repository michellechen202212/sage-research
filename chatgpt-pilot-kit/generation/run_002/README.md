# Synthetic Commerce Investigation API

A deterministic, dependency-free Python API over the supplied SQLite schema and fixtures. Projections retain source identities, event meanings, monetary semantics, and independent child collections.

## Requirements and setup

- Python 3.10 or newer
- No package installation and no network access are required.

From this directory, start the service:

```powershell
python app.py
```

The service builds an in-memory SQLite database from the unchanged `schema.sql` and `seed.sql` on every start and listens at `http://127.0.0.1:8000`.

Optional persistence (an empty/nonexistent database is initialized once):

```powershell
python app.py --database investigation.db --port 8000
```

## API

- `GET /api/customers`
- `GET /api/customers/C1`
- `GET /api/customers/C1/activity`
- `GET /api/customers/C1/orders`
- `GET /api/customers/C1/receipts`
- `GET /api/customers/C1/returns`
- `GET /api/customers/C1/timeline`
- `GET /api/orders/O1`
- `GET /api/receipts/R1`
- `GET /api/payments/P1`

Every entity and envelope declares its grain. Money is represented as a decimal string plus semantic, source-ID lineage, aggregation method, and `UNKNOWN` currency (the source does not provide currency). Nested collections are bounded and independently queried; the API never invents line/payment or item/tender allocations. POS business dates appear at midnight only as explicitly typed `pos_receipt_business_date` timeline events.

## Tests

```powershell
python -m unittest discover -s tests -v
```

The tests assert semantic behavior including preservation of repeated identities, collection independence, authorization/settlement separation, monetary lineage, unknown currency, and chronological typed events.
