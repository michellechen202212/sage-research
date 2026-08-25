# Investigation service

A dependency-free Python 3 service over the supplied immutable SQLite schema and fixtures. It builds a fresh in-memory database for each process/test; runtime requires no network and does not alter `schema.sql` or `seed.sql`.

## Run and test

Python 3.10+ is sufficient; there is no install step.

```powershell
python -m unittest -v
python investigation_service.py order O1001
python investigation_service.py payment P1
python investigation_service.py receipt R1
python investigation_service.py customer C1
python investigation_service.py projection --record-type payment_event --order-id O1001
```

The module also exposes `InvestigationService` for direct callable use. Entity and customer calls return `{"found": false, "error": "not_found", ...}` for unknown IDs.

## Interfaces and response design

- `order_detail(id)` includes order facts, lines, each line's fulfillment events, and supported payment/return IDs.
- `payment_detail(id)` includes all events and posted capture/refund/net facts.
- `receipt_detail(id)` includes item occurrences and every tender leg.
- `customer_view(id)` includes customer, orders, payments, receipts, returns, aggregate payment/refund facts, and a timeline sorted by `(timestamp, type, id)`.
- `compact_projection(...)` emits export-friendly typed records sorted by `(timestamp, record_type, record_id)`. Types are `order_line`, `fulfillment_event`, `payment_event`, `receipt_item`, `tender_leg`, and `return`. Stable common fields are `record_type`, `record_id`, `timestamp`, `customer_id`, nullable `order_id`, nullable `receipt_id`, nullable `sku`, and type-specific `facts`.

Projection filters are exact-match `customer_id`, `record_type`, `order_id`, `receipt_id`, and `sku`, plus inclusive ISO-8601 `from_timestamp` and `to_timestamp`. Filters compose with AND semantics. The CLI equivalents use hyphenated names (for example `--customer-id`).

Money is never represented as a binary float: each value contains integer `cents`, a two-place decimal string, and nullable source `currency`. Repeated SKUs, order numbers, tender types, partial fulfillments, and payment events remain separate source occurrences. No receipt-to-order association is inferred.
