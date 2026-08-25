# Investigation service

A dependency-free Python 3.10+ HTTP and callable service over the supplied SQLite schema. `schema.sql` and `seed.sql` are read unchanged when creating a local database.

## Setup and run

No package installation or network access is required.

```powershell
python app.py init-db investigation.db
python app.py serve investigation.db --host 127.0.0.1 --port 8000
```

Examples:

```text
GET /v1/orders/O1001
GET /v1/payments/P1
GET /v1/receipts/R1
GET /v1/customers/C1/investigation
GET /v1/compact?customer_id=C1&record_type=payment_event
```

Unknown entity IDs return HTTP 404 with `{"error":"not_found","entity":"...","id":"..."}`. Invalid compact requests return HTTP 400. The same operations can be called in-process through `InvestigationService`.

## Response and data design

Entity responses preserve child source identities and deterministic ordering. Orders contain `lines`, each line contains its own `fulfillment_events`, and order-level `payments` remain separate. Payments contain events. Receipts contain independent `items` and `tender_legs`; no item-to-tender allocation is inferred.

The customer view contains `customer`, `orders`, `payments`, `receipts`, `returns`, `payment_refund_facts`, and a chronological `timeline`. Timeline ties are ordered by type then source ID. Payment/refund facts group by the event's own currency and include explicit aggregation lineage. Only posted CAPTURE events contribute gross captured value, only posted REFUND events contribute refunds, net uses capture minus refund, and AUTH attempts are excluded.

All money is represented as `{ "cents": 12000, "decimal": "120.00", "currency_code": "USD" }`. Integer cents remain the calculation source; the decimal string is exact and JSON-safe. Unknown currency remains `null`.

The compact response has this envelope:

```json
{"grain":"one source record per member; record_type declares member grain","filters":{},"count":1,"records":[]}
```

Each record is one unchanged source occurrence with a `record_type`, `record_id`, its applicable relationship keys, `event_at` when the source has a business time, and `money` when applicable. Parent totals occur only on parent records. Supported record types are `order`, `order_line`, `fulfillment_event`, `payment`, `payment_event`, `receipt`, `receipt_item`, `tender_leg`, and `return`.

Compact query filters use AND semantics:

- `customer_id`: exact customer identity.
- `record_type`: exact member grain from the list above.
- `order_id`: exact explicit order relationship. Receipt facts do not acquire an inferred order.
- `sku`: exact SKU on line, fulfillment, or receipt-item records.
- `from_at`, `to_at`: inclusive ISO-8601 lexical bounds on `event_at`. Records without a business event time are excluded when either bound is used.

Compact output is sorted by `record_type`, then `record_id`, making review/export repeatable. It intentionally does not flatten sibling or differently grained collections.

## Tests

Run the complete suite from the workspace root:

```powershell
python -m unittest -v
```

The tests build clean temporary databases from the supplied SQL, require no running server, and cover callable and HTTP behavior, lookups and 404s, all filters, ordering, timeline shape, source counts, and monetary reconciliation.
