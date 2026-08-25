# Investigation service

A zero-dependency Python service over a fresh, in-memory SQLite database loaded from the supplied immutable `schema.sql` and `seed.sql`. Python 3.10+ is sufficient; no install or network access is needed.

## Run and test

```powershell
python investigation_service.py --host 127.0.0.1 --port 8000
python -m unittest -v
```

Each process reloads a clean database. The connection is switched to SQLite `query_only` mode after fixture loading.

## Interfaces

All responses are JSON. Unknown entity identifiers and routes return HTTP 404 with `{ "error": "not_found", "message": ... }`; invalid filters return 400.

- `GET /orders/O1001` — order, lines, fulfillment events, and associated payment/return IDs.
- `GET /payments/P1` — payment events and derived posted-capture/refund/net facts.
- `GET /receipts/R1` — receipt, occurrence-level items, and tender legs.
- `GET /customers/C1` — customer plus `orders`, `payments`, `receipts`, `returns`, `payment_refund_facts`, and a chronological typed `timeline`.
- `GET /projection` — compact records for orders, order lines, fulfillment events, payment events, receipt items, tender legs, and returns.

Example: `http://127.0.0.1:8000/projection?customer_id=C1&sku=SKU-A`

The same operations are directly callable through `InvestigationService`, so tests require no network service.

## Projection and filters

The projection response is `{ "filters": {...}, "count": N, "records": [...] }`. Every record has `customer_id`, `record_type`, `record_id`, and `timestamp`; relevant records additionally expose order, line, SKU, receipt, payment, status, tender, event, quantity, and money facts. Records sort by `(timestamp, record_type, record_id)`.

Supported exact-match filters are `customer_id`, `record_type`, `order_id`, and `sku`. Inclusive ISO-8601 timestamp bounds are `from_at` and `to_at`. Filters combine with AND. Associations absent from the fixtures are omitted from individual records; no inferred joins are created.

Money is represented as `{ "cents": 12000, "decimal": "120.00", "currency": "USD" }`. Integer cents are authoritative and decimal strings are produced with `Decimal`, avoiding binary floating-point errors. Nullable source currencies remain `null`.
