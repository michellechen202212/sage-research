# Investigation service

A dependency-free Python 3.10+ read service over the supplied SQLite schema and fixtures. Source SQL is never modified; each process/test builds a clean in-memory database from it.

## Run and test

```powershell
python -m unittest discover -s tests -v
python server.py
```

No installation or network service is required. The HTTP server binds only to `127.0.0.1:8000`.

## Interfaces

- `GET /v1/orders/{order_id}`: order, distinct lines, each line's fulfillment events, and payments.
- `GET /v1/payments/{payment_id}`: payment and independent payment events.
- `GET /v1/receipts/{receipt_id}`: receipt with sibling item occurrences and tender legs.
- `GET /v1/customers/{customer_id}`: orders, payments, receipts, returns, payment/refund facts with declared derived-total semantics, and a typed chronological timeline.
- `GET /v1/compact`: export/review projection. Optional exact filters are `customer_id`, `fact_type`, `order_id`, and `sku`; inclusive ISO-8601 lexical bounds are `from_at` and `to_at`. Filters combine with AND.

Examples: `http://127.0.0.1:8000/v1/customers/C1` and `http://127.0.0.1:8000/v1/compact?fact_type=payment_event&order_id=O1001`.

Unknown entities/routes return HTTP 404 with `{"error":"not_found",...}`. Unknown compact filters return HTTP 400. Callable Python methods return the same shapes.

## Design notes

Compact output has one row per source occurrence. `fact_type` declares the row grain: `order`, `order_line`, `fulfillment_event`, `payment_event`, `receipt`, `receipt_item`, `tender_leg`, or `return`. Common fields are `source_id`, `customer_id`, nullable `order_id`/`sku`/`timestamp`, exact `amount`, and type-specific `attributes`. Ordering is `(fact_type, source_id)`. The heterogeneous collection preserves each source grain and never joins siblings into cross-products or invents allocations/bridges.

Money is represented as integer `amount_cents`, an exact two-place decimal string `amount`, and nullable source `currency_code`; binary floats and currency inference are avoided. Parent totals remain parent rows. The only derived monetary projection groups source CAPTURE and REFUND events independently by customer, event type, status, and source currency; AUTH is excluded, values are unsigned gross facts, and refunds are not inferred to match returns.
