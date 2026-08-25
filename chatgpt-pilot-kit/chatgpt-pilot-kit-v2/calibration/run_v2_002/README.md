# Commerce Investigation API

A deterministic local investigation service over the supplied synthetic fixture data. It uses only the Python standard library and an in-memory SQLite database rebuilt from the unchanged `schema.sql` and `seed.sql` at startup.

## Requirements and commands

Python 3.10 or newer is sufficient. No package installation or network access is required.

```powershell
python -m unittest -v
python app.py --host 127.0.0.1 --port 8000
```

## API

- `GET /health`
- `GET /customers/C1`
- `GET /orders/O1`
- `GET /payments/P1`
- `GET /receipts/R1`
- `GET /receipts?customer_id=C1&sku=SKU-X&tender_type=CASH`
- `GET /customers/C1/returns`
- `GET /customers/C1/timeline`

The receipt list is the compact, filterable investigation projection. Each returned receipt remains one receipt-grain object, with independent item-occurrence and tender-leg collections. Filters select receipts; they do not discard nonmatching children or create item/tender pairings.

Every domain object declares its grain. Money is serialized as an exact decimal string plus currency (`UNKNOWN`, because none is supplied), semantic type, source table/type, source identifier, and source field. Dates and timestamps carry their source-event meaning. Timeline rows are typed, bounded facts and retain their source IDs; no inferred allocations or relationships are produced.
