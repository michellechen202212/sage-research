# Commerce Investigation API

A deterministic, read-only JSON API over the supplied synthetic commerce schema and fixtures. It uses only the Python standard library and creates a fresh in-memory SQLite database at startup; `schema.sql` and `seed.sql` are not modified.

## Requirements and setup

- Python 3.10 or newer
- No package installation or network access is required

From this directory, run:

```powershell
python app.py
```

The service listens at `http://127.0.0.1:8000`. Use `python app.py --host 127.0.0.1 --port 9000` to select another address.

## API

- `GET /health`
- `GET /customers`
- `GET /customers/{customer_id}` — customer plus order, receipt, and return summaries
- `GET /customers/{customer_id}/activity` — complete nested investigation view
- `GET /customers/{customer_id}/timeline` — unified chronological events
- `GET /customers/{customer_id}/returns` — returns with refunds
- `GET /orders/{order_id}` — lines, fulfillment events, payments, authorizations, and settlements
- `GET /receipts/{receipt_id}` — item occurrences and tender legs

Monetary values are returned as fixed two-decimal strings to avoid JSON floating-point ambiguity. Collection rows retain their source identifiers and occurrence grain, including repeated SKUs and tender types.

Example:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/customers/C1/activity
```

## Tests

```powershell
python -m unittest -v
```

Tests create their own in-memory databases and exercise both the repository and live HTTP boundary.
