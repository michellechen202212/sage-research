"""SQLite-backed investigation interfaces using only the Python standard library."""

from __future__ import annotations

import argparse
import json
import sqlite3
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parent


def money(cents: int, currency: str | None) -> dict[str, Any]:
    """Return an exact, JSON-safe monetary representation."""
    return {"cents": cents, "decimal": str((Decimal(cents) / 100).quantize(Decimal("0.00"))), "currency": currency}


def load_fixture_database(connection: sqlite3.Connection) -> None:
    """Load the supplied immutable schema and fixture into a clean connection."""
    connection.executescript((ROOT / "schema.sql").read_text(encoding="utf-8"))
    connection.executescript((ROOT / "seed.sql").read_text(encoding="utf-8"))


def fixture_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    load_fixture_database(connection)
    return connection


class InvestigationService:
    def __init__(self, connection: sqlite3.Connection):
        self.db = connection
        self.db.row_factory = sqlite3.Row

    def _one(self, sql: str, values: Iterable[Any]) -> sqlite3.Row | None:
        return self.db.execute(sql, tuple(values)).fetchone()

    @staticmethod
    def _not_found(entity: str, identifier: str) -> dict[str, Any]:
        return {"found": False, "error": "not_found", "entity": entity, "id": identifier}

    def order_detail(self, order_id: str) -> dict[str, Any]:
        row = self._one("SELECT * FROM commerce_order WHERE order_id = ?", [order_id])
        if row is None:
            return self._not_found("order", order_id)
        lines = []
        for line in self.db.execute("SELECT * FROM order_line WHERE order_id=? ORDER BY order_line_id", [order_id]):
            events = [
                {"fulfillment_event_id": e["fulfillment_event_id"], "event_type": e["event_type"],
                 "amount": money(e["amount_cents"], row["currency_code"]), "event_at": e["event_at"]}
                for e in self.db.execute(
                    "SELECT * FROM fulfillment_event WHERE order_line_id=? ORDER BY event_at, fulfillment_event_id",
                    [line["order_line_id"]],
                )
            ]
            lines.append({"order_line_id": line["order_line_id"], "sku": line["sku"],
                          "quantity": line["quantity"], "line_amount": money(line["line_amount_cents"], row["currency_code"]),
                          "fulfillment_events": events})
        payments = [p["payment_id"] for p in self.db.execute("SELECT payment_id FROM payment WHERE order_id=? ORDER BY payment_id", [order_id])]
        returns = [r["return_id"] for r in self.db.execute("SELECT return_id FROM merchandise_return WHERE original_order_id=? ORDER BY return_id", [order_id])]
        return {"found": True, "order": {"order_id": row["order_id"], "customer_id": row["customer_id"],
                "channel": row["channel"], "order_number": row["order_number"],
                "order_total": money(row["order_total_cents"], row["currency_code"]), "created_at": row["created_at"],
                "ordered_at": row["ordered_at"], "updated_at": row["updated_at"], "lines": lines,
                "payment_ids": payments, "return_ids": returns}}

    def payment_detail(self, payment_id: str) -> dict[str, Any]:
        row = self._one("SELECT * FROM payment WHERE payment_id=?", [payment_id])
        if row is None:
            return self._not_found("payment", payment_id)
        events = [{"event_id": e["event_id"], "event_type": e["event_type"], "status": e["status"],
                   "amount": money(e["amount_cents"], e["currency_code"]), "event_at": e["event_at"], "ingested_at": e["ingested_at"]}
                  for e in self.db.execute("SELECT * FROM payment_event WHERE payment_id=? ORDER BY event_at, event_id", [payment_id])]
        facts = self._payment_facts(events)
        return {"found": True, "payment": {"payment_id": row["payment_id"], "customer_id": row["customer_id"],
                "order_id": row["order_id"], "provider_reference": row["provider_reference"], "events": events, "facts": facts}}

    @staticmethod
    def _payment_facts(events: list[dict[str, Any]]) -> dict[str, Any]:
        posted_capture = sum(e["amount"]["cents"] for e in events if e["event_type"] == "CAPTURE" and e["status"] == "POSTED")
        posted_refund = sum(e["amount"]["cents"] for e in events if e["event_type"] == "REFUND" and e["status"] == "POSTED")
        currency = next((e["amount"]["currency"] for e in events if e["amount"]["currency"]), None)
        return {"posted_capture": money(posted_capture, currency), "posted_refund": money(posted_refund, currency),
                "net_posted": money(posted_capture - posted_refund, currency)}

    def receipt_detail(self, receipt_id: str) -> dict[str, Any]:
        row = self._one("SELECT * FROM pos_receipt WHERE receipt_id=?", [receipt_id])
        if row is None:
            return self._not_found("receipt", receipt_id)
        items = [{"receipt_item_id": i["receipt_item_id"], "sku": i["sku"], "quantity": i["quantity"],
                  "item_amount": money(i["item_amount_cents"], row["currency_code"])}
                 for i in self.db.execute("SELECT * FROM receipt_item_occurrence WHERE receipt_id=? ORDER BY receipt_item_id", [receipt_id])]
        tenders = [{"tender_leg_id": t["tender_leg_id"], "tender_type": t["tender_type"],
                    "amount": money(t["amount_cents"], row["currency_code"])}
                   for t in self.db.execute("SELECT * FROM tender_leg WHERE receipt_id=? ORDER BY tender_leg_id", [receipt_id])]
        return {"found": True, "receipt": {"receipt_id": row["receipt_id"], "customer_id": row["customer_id"],
                "store_code": row["store_code"], "receipt_number": row["receipt_number"],
                "receipt_total": money(row["receipt_total_cents"], row["currency_code"]),
                "transacted_at": row["transacted_at"], "items": items, "tender_legs": tenders}}

    def customer_view(self, customer_id: str) -> dict[str, Any]:
        customer = self._one("SELECT * FROM customer WHERE customer_id=?", [customer_id])
        if customer is None:
            return self._not_found("customer", customer_id)
        orders = [self.order_detail(r["order_id"])["order"] for r in self.db.execute(
            "SELECT order_id FROM commerce_order WHERE customer_id=? ORDER BY ordered_at, order_id", [customer_id])]
        payments = [self.payment_detail(r["payment_id"])["payment"] for r in self.db.execute(
            "SELECT payment_id FROM payment WHERE customer_id=? ORDER BY payment_id", [customer_id])]
        receipts = [self.receipt_detail(r["receipt_id"])["receipt"] for r in self.db.execute(
            "SELECT receipt_id FROM pos_receipt WHERE customer_id=? ORDER BY transacted_at, receipt_id", [customer_id])]
        returns = [{"return_id": r["return_id"], "original_order_id": r["original_order_id"],
                    "merchandise_value": money(r["merchandise_value_cents"], r["currency_code"]), "returned_at": r["returned_at"]}
                   for r in self.db.execute("SELECT * FROM merchandise_return WHERE customer_id=? ORDER BY returned_at, return_id", [customer_id])]
        timeline = self._timeline(orders, payments, receipts, returns)
        capture = sum(p["facts"]["posted_capture"]["cents"] for p in payments)
        refund = sum(p["facts"]["posted_refund"]["cents"] for p in payments)
        return {"found": True, "customer": {"customer_id": customer_id, "display_name": customer["display_name"]},
                "orders": orders, "payments": payments, "receipts": receipts, "returns": returns,
                "payment_refund_facts": {"posted_capture": money(capture, "USD"), "posted_refund": money(refund, "USD"),
                                         "net_posted": money(capture-refund, "USD")}, "timeline": timeline}

    @staticmethod
    def _timeline(orders, payments, receipts, returns):
        result = []
        for o in orders:
            result.append({"type": "order", "timestamp": o["ordered_at"], "id": o["order_id"]})
            for line in o["lines"]:
                result.extend({"type": "fulfillment_event", "timestamp": e["event_at"], "id": e["fulfillment_event_id"]} for e in line["fulfillment_events"])
        for p in payments:
            result.extend({"type": "payment_event", "timestamp": e["event_at"], "id": e["event_id"]} for e in p["events"])
        result.extend({"type": "receipt", "timestamp": r["transacted_at"], "id": r["receipt_id"]} for r in receipts)
        result.extend({"type": "return", "timestamp": r["returned_at"], "id": r["return_id"]} for r in returns)
        return sorted(result, key=lambda x: (x["timestamp"], x["type"], x["id"]))

    def compact_projection(self, *, customer_id: str | None = None, record_type: str | None = None,
                           order_id: str | None = None, receipt_id: str | None = None, sku: str | None = None,
                           from_timestamp: str | None = None, to_timestamp: str | None = None) -> dict[str, Any]:
        records = self._projection_records()
        criteria = {"customer_id": customer_id, "record_type": record_type, "order_id": order_id,
                    "receipt_id": receipt_id, "sku": sku}
        for key, value in criteria.items():
            if value is not None:
                records = [r for r in records if r.get(key) == value]
        if from_timestamp is not None:
            records = [r for r in records if r["timestamp"] >= from_timestamp]
        if to_timestamp is not None:
            records = [r for r in records if r["timestamp"] <= to_timestamp]
        return {"filters": {**criteria, "from_timestamp": from_timestamp, "to_timestamp": to_timestamp},
                "count": len(records), "records": records}

    def _projection_records(self) -> list[dict[str, Any]]:
        records = []
        orders = self.db.execute("SELECT * FROM commerce_order ORDER BY order_id").fetchall()
        for o in orders:
            currency = o["currency_code"]
            for l in self.db.execute("SELECT * FROM order_line WHERE order_id=? ORDER BY order_line_id", [o["order_id"]]):
                base = {"customer_id": o["customer_id"], "order_id": o["order_id"], "receipt_id": None, "sku": l["sku"]}
                records.append({**base, "record_type": "order_line", "record_id": l["order_line_id"], "timestamp": o["ordered_at"],
                                "facts": {"quantity": l["quantity"], "amount": money(l["line_amount_cents"], currency), "channel": o["channel"], "order_number": o["order_number"]}})
                for e in self.db.execute("SELECT * FROM fulfillment_event WHERE order_line_id=? ORDER BY event_at, fulfillment_event_id", [l["order_line_id"]]):
                    records.append({**base, "record_type": "fulfillment_event", "record_id": e["fulfillment_event_id"], "timestamp": e["event_at"],
                                    "facts": {"order_line_id": l["order_line_id"], "event_type": e["event_type"], "amount": money(e["amount_cents"], currency)}})
        for e in self.db.execute("SELECT e.*, p.customer_id, p.order_id FROM payment_event e JOIN payment p USING(payment_id) ORDER BY e.event_at, e.event_id"):
            records.append({"record_type": "payment_event", "record_id": e["event_id"], "timestamp": e["event_at"], "customer_id": e["customer_id"],
                            "order_id": e["order_id"], "receipt_id": None, "sku": None,
                            "facts": {"payment_id": e["payment_id"], "event_type": e["event_type"], "status": e["status"],
                                      "amount": money(e["amount_cents"], e["currency_code"]), "ingested_at": e["ingested_at"]}})
        for r in self.db.execute("SELECT * FROM pos_receipt ORDER BY receipt_id"):
            for i in self.db.execute("SELECT * FROM receipt_item_occurrence WHERE receipt_id=? ORDER BY receipt_item_id", [r["receipt_id"]]):
                records.append({"record_type": "receipt_item", "record_id": i["receipt_item_id"], "timestamp": r["transacted_at"], "customer_id": r["customer_id"],
                                "order_id": None, "receipt_id": r["receipt_id"], "sku": i["sku"],
                                "facts": {"quantity": i["quantity"], "amount": money(i["item_amount_cents"], r["currency_code"]), "store_code": r["store_code"], "receipt_number": r["receipt_number"]}})
            for t in self.db.execute("SELECT * FROM tender_leg WHERE receipt_id=? ORDER BY tender_leg_id", [r["receipt_id"]]):
                records.append({"record_type": "tender_leg", "record_id": t["tender_leg_id"], "timestamp": r["transacted_at"], "customer_id": r["customer_id"],
                                "order_id": None, "receipt_id": r["receipt_id"], "sku": None,
                                "facts": {"tender_type": t["tender_type"], "amount": money(t["amount_cents"], r["currency_code"])}})
        for r in self.db.execute("SELECT * FROM merchandise_return ORDER BY returned_at, return_id"):
            records.append({"record_type": "return", "record_id": r["return_id"], "timestamp": r["returned_at"], "customer_id": r["customer_id"],
                            "order_id": r["original_order_id"], "receipt_id": None, "sku": None,
                            "facts": {"merchandise_value": money(r["merchandise_value_cents"], r["currency_code"])}})
        return sorted(records, key=lambda r: (r["timestamp"], r["record_type"], r["record_id"]))


def main() -> None:
    parser = argparse.ArgumentParser(description="Query the supplied investigation fixtures")
    parser.add_argument("interface", choices=["order", "payment", "receipt", "customer", "projection"])
    parser.add_argument("identifier", nargs="?")
    parser.add_argument("--customer-id"); parser.add_argument("--record-type"); parser.add_argument("--order-id")
    parser.add_argument("--receipt-id"); parser.add_argument("--sku"); parser.add_argument("--from-timestamp"); parser.add_argument("--to-timestamp")
    args = parser.parse_args(); service = InvestigationService(fixture_connection())
    if args.interface == "projection":
        result = service.compact_projection(customer_id=args.customer_id, record_type=args.record_type, order_id=args.order_id,
            receipt_id=args.receipt_id, sku=args.sku, from_timestamp=args.from_timestamp, to_timestamp=args.to_timestamp)
    else:
        if not args.identifier: parser.error("identifier is required for entity/customer interfaces")
        result = getattr(service, f"{args.interface}_detail" if args.interface != "customer" else "customer_view")(args.identifier)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
