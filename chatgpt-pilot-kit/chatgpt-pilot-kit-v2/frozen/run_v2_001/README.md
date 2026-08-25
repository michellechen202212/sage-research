# Commerce Investigation API

A deterministic, dependency-free JSON API over the supplied synthetic commerce data. The database is rebuilt in memory from `schema.sql` and `seed.sql` on each start; those supplied files are not modified.

## Requirements and setup

- Python 3.10 or newer
- No package installation and no network dependency

From this directory, run:

```powershell
python app.py
```

The server listens on `http://127.0.0.1:8000`. Use `python app.py --host 127.0.0.1 --port 9000` to change the bind address or port.

## Endpoints

- `GET /health`
- `GET /customers/C1` — complete customer investigation view
- `GET /customers/C1/timeline` — chronological unified activity
- `GET /orders/O1` — lines, fulfillment, and payment details
- `GET /payments/P1` — authorization attempts and settlement legs
- `GET /receipts/R1` — receipt facts, item occurrences, and tender legs
- `GET /receipts` — compact receipt investigation projection

Receipt projection filters can be combined: `customer_id`, `location_id`, `business_date`, `sku`, and `tender_type`. For example:

```text
http://127.0.0.1:8000/receipts?sku=SKU-X&tender_type=VISA
```

Money is emitted as fixed two-decimal strings and quantities as fixed three-decimal strings, avoiding ambiguous JSON floating-point presentation. Every event, item, tender leg, and source entity retains its stable source identifier.

## Tests

```powershell
python -m unittest -v
```
