"""Read-only investigation interfaces over the supplied SQLite fixtures."""

from __future__ import annotations

import argparse
import json
import sqlite3
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent


class NotFoundError(LookupError):
    """Raised when a requested source entity does not exist."""


def money(cents: int, currency: str | None) -> dict[str, Any]:
    return {
        "cents": cents,
        "decimal": format(Decimal(cents) / Decimal(100), ".2f"),
        "currency": currency,
    }


def build_connection() -> sqlite3.Connection:
    """Load immutable schema.sql and seed.sql into a fresh in-memory database."""
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.executescript((ROOT / "schema.sql").read_text(encoding="utf-8"))
    connection.executescript((ROOT / "seed.sql").read_text(encoding="utf-8"))
    connection.execute("PRAGMA query_only = ON")
    return connection


class InvestigationService:
    FILTERS = frozenset({"customer_id", "record_type", "order_id", "sku", "from_at", "to_at"})

    def __init__(self, connection: sqlite3.Connection):
        self.db = connection

    def _one(self, sql: str, identifier: str, kind: str) -> sqlite3.Row:
        row = self.db.execute(sql, (identifier,)).fetchone()
        if row is None:
            raise NotFoundError(f"{kind} '{identifier}' was not found")
        return row

    @staticmethod
    def _rows(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        return [dict(row) for row in cursor.fetchall()]

    def get_order(self, order_id: str) -> dict[str, Any]:
        row = self._one("SELECT * FROM commerce_order WHERE order_id = ?", order_id, "order")
        result = dict(row)
        result["order_total"] = money(result.pop("order_total_cents"), result["currency_code"])
        lines = self._rows(self.db.execute(
            "SELECT * FROM order_line WHERE order_id = ? ORDER BY order_line_id", (order_id,)
        ))
        for line in lines:
            line["line_amount"] = money(line.pop("line_amount_cents"), result["currency_code"])
            events = self._rows(self.db.execute(
                "SELECT * FROM fulfillment_event WHERE order_line_id = ? "
                "ORDER BY event_at, fulfillment_event_id", (line["order_line_id"],)
            ))
            for event in events:
                event["amount"] = money(event.pop("amount_cents"), result["currency_code"])
            line["fulfillment_events"] = events
        result["lines"] = lines
        result["payments"] = [r[0] for r in self.db.execute(
            "SELECT payment_id FROM payment WHERE order_id = ? ORDER BY payment_id", (order_id,)
        )]
        result["returns"] = [r[0] for r in self.db.execute(
            "SELECT return_id FROM merchandise_return WHERE original_order_id = ? ORDER BY returned_at, return_id",
            (order_id,),
        )]
        return result

    def get_payment(self, payment_id: str) -> dict[str, Any]:
        result = dict(self._one("SELECT * FROM payment WHERE payment_id = ?", payment_id, "payment"))
        events = self._rows(self.db.execute(
            "SELECT * FROM payment_event WHERE payment_id = ? ORDER BY event_at, event_id", (payment_id,)
        ))
        for event in events:
            event["amount"] = money(event.pop("amount_cents"), event["currency_code"])
        result["events"] = events
        result["facts"] = self._payment_facts(events)
        return result

    @staticmethod
    def _payment_facts(events: Iterable[dict[str, Any]]) -> dict[str, Any]:
        rows = list(events)
        currencies = sorted({e["currency_code"] for e in rows if e["currency_code"] is not None})
        currency = currencies[0] if len(currencies) == 1 else None
        captured = sum(e["amount"]["cents"] for e in rows if e["event_type"] == "CAPTURE" and e["status"] == "POSTED")
        refunded = sum(e["amount"]["cents"] for e in rows if e["event_type"] == "REFUND" and e["status"] == "POSTED")
        return {
            "posted_capture": money(captured, currency),
            "posted_refund": money(refunded, currency),
            "net_captured": money(captured - refunded, currency),
        }

    def get_receipt(self, receipt_id: str) -> dict[str, Any]:
        result = dict(self._one("SELECT * FROM pos_receipt WHERE receipt_id = ?", receipt_id, "receipt"))
        currency = result["currency_code"]
        result["receipt_total"] = money(result.pop("receipt_total_cents"), currency)
        result["items"] = self._rows(self.db.execute(
            "SELECT * FROM receipt_item_occurrence WHERE receipt_id = ? ORDER BY receipt_item_id", (receipt_id,)
        ))
        for item in result["items"]:
            item["item_amount"] = money(item.pop("item_amount_cents"), currency)
        result["tender_legs"] = self._rows(self.db.execute(
            "SELECT * FROM tender_leg WHERE receipt_id = ? ORDER BY tender_leg_id", (receipt_id,)
        ))
        for leg in result["tender_legs"]:
            leg["amount"] = money(leg.pop("amount_cents"), currency)
        return result

    def get_customer(self, customer_id: str) -> dict[str, Any]:
        customer = dict(self._one("SELECT * FROM customer WHERE customer_id = ?", customer_id, "customer"))
        order_ids = [r[0] for r in self.db.execute(
            "SELECT order_id FROM commerce_order WHERE customer_id = ? ORDER BY ordered_at, order_id", (customer_id,)
        )]
        payment_ids = [r[0] for r in self.db.execute(
            "SELECT payment_id FROM payment WHERE customer_id = ? ORDER BY payment_id", (customer_id,)
        )]
        receipt_ids = [r[0] for r in self.db.execute(
            "SELECT receipt_id FROM pos_receipt WHERE customer_id = ? ORDER BY transacted_at, receipt_id", (customer_id,)
        )]
        returns = self._rows(self.db.execute(
            "SELECT * FROM merchandise_return WHERE customer_id = ? ORDER BY returned_at, return_id", (customer_id,)
        ))
        for returned in returns:
            returned["merchandise_value"] = money(returned.pop("merchandise_value_cents"), returned["currency_code"])
        payments = [self.get_payment(value) for value in payment_ids]
        result = {
            "customer": customer,
            "orders": [self.get_order(value) for value in order_ids],
            "payments": payments,
            "receipts": [self.get_receipt(value) for value in receipt_ids],
            "returns": returns,
            "payment_refund_facts": {
                "by_payment": [{"payment_id": p["payment_id"], **p["facts"]} for p in payments],
            },
        }
        result["timeline"] = self._timeline(result)
        return result

    @staticmethod
    def _timeline(view: dict[str, Any]) -> list[dict[str, Any]]:
        entries: list[dict[str, Any]] = []
        for order in view["orders"]:
            entries.append({"type": "order", "timestamp": order["ordered_at"], "id": order["order_id"]})
            for line in order["lines"]:
                for event in line["fulfillment_events"]:
                    entries.append({"type": "fulfillment_event", "timestamp": event["event_at"], "id": event["fulfillment_event_id"]})
        for payment in view["payments"]:
            for event in payment["events"]:
                entries.append({"type": "payment_event", "timestamp": event["event_at"], "id": event["event_id"]})
        for receipt in view["receipts"]:
            entries.append({"type": "receipt", "timestamp": receipt["transacted_at"], "id": receipt["receipt_id"]})
        for returned in view["returns"]:
            entries.append({"type": "return", "timestamp": returned["returned_at"], "id": returned["return_id"]})
        return sorted(entries, key=lambda value: (value["timestamp"], value["type"], value["id"]))

    def compact_projection(self, **filters: str) -> dict[str, Any]:
        unknown = set(filters) - self.FILTERS
        if unknown:
            raise ValueError(f"unsupported filters: {', '.join(sorted(unknown))}")
        records = self._projection_records()
        def keep(record: dict[str, Any]) -> bool:
            if filters.get("customer_id") and record["customer_id"] != filters["customer_id"]:
                return False
            if filters.get("record_type") and record["record_type"] != filters["record_type"]:
                return False
            if filters.get("order_id") and record.get("order_id") != filters["order_id"]:
                return False
            if filters.get("sku") and record.get("sku") != filters["sku"]:
                return False
            if filters.get("from_at") and record["timestamp"] < filters["from_at"]:
                return False
            if filters.get("to_at") and record["timestamp"] > filters["to_at"]:
                return False
            return True
        selected = sorted((r for r in records if keep(r)), key=lambda r: (r["timestamp"], r["record_type"], r["record_id"]))
        return {"filters": dict(sorted(filters.items())), "count": len(selected), "records": selected}

    def _projection_records(self) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for customer_id, in self.db.execute("SELECT customer_id FROM customer ORDER BY customer_id"):
            view = self.get_customer(customer_id)
            for order in view["orders"]:
                base = {"customer_id": customer_id, "order_id": order["order_id"]}
                records.append({**base, "record_type": "order", "record_id": order["order_id"], "timestamp": order["ordered_at"], "channel": order["channel"], "order_number": order["order_number"], "amount": order["order_total"]})
                for line in order["lines"]:
                    records.append({**base, "record_type": "order_line", "record_id": line["order_line_id"], "timestamp": order["ordered_at"], "sku": line["sku"], "quantity": line["quantity"], "amount": line["line_amount"]})
                    for event in line["fulfillment_events"]:
                        records.append({**base, "record_type": "fulfillment_event", "record_id": event["fulfillment_event_id"], "timestamp": event["event_at"], "order_line_id": line["order_line_id"], "sku": line["sku"], "event_type": event["event_type"], "amount": event["amount"]})
            for payment in view["payments"]:
                for event in payment["events"]:
                    records.append({"customer_id": customer_id, "order_id": payment["order_id"], "record_type": "payment_event", "record_id": event["event_id"], "timestamp": event["event_at"], "payment_id": payment["payment_id"], "event_type": event["event_type"], "status": event["status"], "amount": event["amount"]})
            for receipt in view["receipts"]:
                for item in receipt["items"]:
                    records.append({"customer_id": customer_id, "record_type": "receipt_item", "record_id": item["receipt_item_id"], "timestamp": receipt["transacted_at"], "receipt_id": receipt["receipt_id"], "sku": item["sku"], "quantity": item["quantity"], "amount": item["item_amount"]})
                for leg in receipt["tender_legs"]:
                    records.append({"customer_id": customer_id, "record_type": "tender_leg", "record_id": leg["tender_leg_id"], "timestamp": receipt["transacted_at"], "receipt_id": receipt["receipt_id"], "tender_type": leg["tender_type"], "amount": leg["amount"]})
            for returned in view["returns"]:
                records.append({"customer_id": customer_id, "order_id": returned["original_order_id"], "record_type": "return", "record_id": returned["return_id"], "timestamp": returned["returned_at"], "amount": returned["merchandise_value"]})
        return records


def make_handler(service: InvestigationService) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            parts = [part for part in parsed.path.split("/") if part]
            try:
                if len(parts) == 2 and parts[0] == "orders":
                    payload = service.get_order(parts[1])
                elif len(parts) == 2 and parts[0] == "payments":
                    payload = service.get_payment(parts[1])
                elif len(parts) == 2 and parts[0] == "receipts":
                    payload = service.get_receipt(parts[1])
                elif len(parts) == 2 and parts[0] == "customers":
                    payload = service.get_customer(parts[1])
                elif parts == ["projection"]:
                    payload = service.compact_projection(**{k: v[-1] for k, v in parse_qs(parsed.query).items()})
                else:
                    raise NotFoundError("route was not found")
                self._json(200, payload)
            except NotFoundError as error:
                self._json(404, {"error": "not_found", "message": str(error)})
            except ValueError as error:
                self._json(400, {"error": "bad_request", "message": str(error)})

        def _json(self, status: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: Any) -> None:
            pass
    return Handler


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8000, type=int)
    args = parser.parse_args()
    server = HTTPServer((args.host, args.port), make_handler(InvestigationService(build_connection())))
    print(f"Investigation service listening on http://{args.host}:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()

