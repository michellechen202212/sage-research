"""Read-only investigation interfaces over the supplied SQLite model."""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable


MONEY_COLUMNS = {
    "order_total_cents",
    "line_amount_cents",
    "amount_cents",
    "receipt_total_cents",
    "item_amount_cents",
    "merchandise_value_cents",
}


def money(cents: int, currency_code: str | None) -> dict[str, Any]:
    """Return exact, JSON-safe money. Decimal is serialized as a string."""
    return {
        "cents": cents,
        "decimal": format(Decimal(cents) / Decimal(100), ".2f"),
        "currency_code": currency_code,
    }


def _dict(row: sqlite3.Row) -> dict[str, Any]:
    return dict(row)


class NotFoundError(LookupError):
    def __init__(self, entity: str, identifier: str):
        self.entity = entity
        self.identifier = identifier
        super().__init__(f"{entity} not found: {identifier}")

    def as_dict(self) -> dict[str, Any]:
        return {"error": "not_found", "entity": self.entity, "id": self.identifier}


class InvestigationService:
    def __init__(self, database: str | Path):
        self.database = str(database)

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(self.database)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
        finally:
            connection.close()

    @staticmethod
    def _one(connection: sqlite3.Connection, sql: str, values: Iterable[Any], entity: str, identifier: str) -> sqlite3.Row:
        row = connection.execute(sql, tuple(values)).fetchone()
        if row is None:
            raise NotFoundError(entity, identifier)
        return row

    def order(self, order_id: str) -> dict[str, Any]:
        with self._connect() as db:
            parent = self._one(db, "SELECT * FROM commerce_order WHERE order_id = ?", [order_id], "order", order_id)
            result = _dict(parent)
            result["order_total"] = money(result.pop("order_total_cents"), result["currency_code"])
            lines = []
            for row in db.execute("SELECT * FROM order_line WHERE order_id = ? ORDER BY order_line_id", [order_id]):
                line = _dict(row)
                line["line_amount"] = money(line.pop("line_amount_cents"), result["currency_code"])
                events = []
                for event_row in db.execute(
                    "SELECT * FROM fulfillment_event WHERE order_line_id = ? ORDER BY event_at, fulfillment_event_id",
                    [line["order_line_id"]],
                ):
                    event = _dict(event_row)
                    event["amount"] = money(event.pop("amount_cents"), result["currency_code"])
                    events.append(event)
                line["fulfillment_events"] = events
                lines.append(line)
            result["lines"] = lines
            result["payments"] = [self._payment_from_row(db, row) for row in db.execute(
                "SELECT * FROM payment WHERE order_id = ? ORDER BY payment_id", [order_id]
            )]
            return result

    def _payment_from_row(self, db: sqlite3.Connection, row: sqlite3.Row) -> dict[str, Any]:
        result = _dict(row)
        events = []
        for event_row in db.execute(
            "SELECT * FROM payment_event WHERE payment_id = ? ORDER BY event_at, event_id", [result["payment_id"]]
        ):
            event = _dict(event_row)
            event["amount"] = money(event.pop("amount_cents"), event["currency_code"])
            events.append(event)
        result["events"] = events
        return result

    def payment(self, payment_id: str) -> dict[str, Any]:
        with self._connect() as db:
            row = self._one(db, "SELECT * FROM payment WHERE payment_id = ?", [payment_id], "payment", payment_id)
            return self._payment_from_row(db, row)

    def receipt(self, receipt_id: str) -> dict[str, Any]:
        with self._connect() as db:
            parent = self._one(db, "SELECT * FROM pos_receipt WHERE receipt_id = ?", [receipt_id], "receipt", receipt_id)
            result = _dict(parent)
            currency = result["currency_code"]
            result["receipt_total"] = money(result.pop("receipt_total_cents"), currency)
            result["items"] = []
            for row in db.execute("SELECT * FROM receipt_item_occurrence WHERE receipt_id = ? ORDER BY receipt_item_id", [receipt_id]):
                item = _dict(row)
                item["item_amount"] = money(item.pop("item_amount_cents"), currency)
                result["items"].append(item)
            result["tender_legs"] = []
            for row in db.execute("SELECT * FROM tender_leg WHERE receipt_id = ? ORDER BY tender_leg_id", [receipt_id]):
                leg = _dict(row)
                leg["amount"] = money(leg.pop("amount_cents"), currency)
                result["tender_legs"].append(leg)
            return result

    def customer(self, customer_id: str) -> dict[str, Any]:
        with self._connect() as db:
            customer = _dict(self._one(db, "SELECT * FROM customer WHERE customer_id = ?", [customer_id], "customer", customer_id))
        orders = self._ids("commerce_order", "order_id", customer_id)
        payments = self._ids("payment", "payment_id", customer_id)
        receipts = self._ids("pos_receipt", "receipt_id", customer_id)
        result = {
            "customer": customer,
            "orders": [self.order(value) for value in orders],
            "payments": [self.payment(value) for value in payments],
            "receipts": [self.receipt(value) for value in receipts],
            "returns": self._returns(customer_id),
        }
        result["payment_refund_facts"] = self._payment_refund_facts(result["payments"])
        result["timeline"] = self._timeline(result)
        return result

    def _ids(self, table: str, key: str, customer_id: str) -> list[str]:
        with self._connect() as db:
            return [row[0] for row in db.execute(f"SELECT {key} FROM {table} WHERE customer_id = ? ORDER BY {key}", [customer_id])]

    def _returns(self, customer_id: str) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = []
            for row in db.execute("SELECT * FROM merchandise_return WHERE customer_id = ? ORDER BY returned_at, return_id", [customer_id]):
                item = _dict(row)
                item["merchandise_value"] = money(item.pop("merchandise_value_cents"), item["currency_code"])
                rows.append(item)
            return rows

    @staticmethod
    def _payment_refund_facts(payments: list[dict[str, Any]]) -> list[dict[str, Any]]:
        grouped: dict[str | None, dict[str, int]] = defaultdict(lambda: {"captured": 0, "refunded": 0})
        for payment in payments:
            for event in payment["events"]:
                if event["event_type"] == "CAPTURE" and event["status"] == "POSTED":
                    grouped[event["currency_code"]]["captured"] += event["amount"]["cents"]
                elif event["event_type"] == "REFUND" and event["status"] == "POSTED":
                    grouped[event["currency_code"]]["refunded"] += event["amount"]["cents"]
        facts = []
        for currency, values in sorted(grouped.items(), key=lambda pair: (pair[0] is None, pair[0] or "")):
            facts.append({
                "currency_code": currency,
                "gross_captured": money(values["captured"], currency),
                "posted_refunds": money(values["refunded"], currency),
                "net_captured_after_refunds": money(values["captured"] - values["refunded"], currency),
                "lineage": {
                    "grouping_keys": ["customer_id", "currency_code"],
                    "gross_captured": "SUM(payment_event.amount_cents) WHERE event_type=CAPTURE AND status=POSTED",
                    "posted_refunds": "SUM(payment_event.amount_cents) WHERE event_type=REFUND AND status=POSTED",
                    "net_captured_after_refunds": "gross_captured - posted_refunds",
                    "auth_events_included": False,
                    "currency_handling": "events grouped by their own currency_code; unknown remains null",
                },
            })
        return facts

    @staticmethod
    def _timeline(view: dict[str, Any]) -> list[dict[str, Any]]:
        entries = []
        for order in view["orders"]:
            entries.append({"type": "ORDER_PLACED", "timestamp": order["ordered_at"], "id": order["order_id"]})
            for line in order["lines"]:
                for event in line["fulfillment_events"]:
                    entries.append({"type": "FULFILLMENT_EVENT", "timestamp": event["event_at"], "id": event["fulfillment_event_id"], "event_type": event["event_type"], "order_line_id": line["order_line_id"]})
        for payment in view["payments"]:
            for event in payment["events"]:
                entries.append({"type": "PAYMENT_EVENT", "timestamp": event["event_at"], "id": event["event_id"], "event_type": event["event_type"], "payment_id": payment["payment_id"]})
        for receipt in view["receipts"]:
            entries.append({"type": "RECEIPT_TRANSACTED", "timestamp": receipt["transacted_at"], "id": receipt["receipt_id"]})
        for item in view["returns"]:
            entries.append({"type": "MERCHANDISE_RETURN", "timestamp": item["returned_at"], "id": item["return_id"]})
        return sorted(entries, key=lambda entry: (entry["timestamp"], entry["type"], entry["id"]))

    def compact(self, *, customer_id: str | None = None, record_type: str | None = None,
                order_id: str | None = None, sku: str | None = None,
                from_at: str | None = None, to_at: str | None = None) -> dict[str, Any]:
        """Return a union of explicit-grain records; filters use AND semantics."""
        allowed = {"order", "order_line", "fulfillment_event", "payment", "payment_event", "receipt", "receipt_item", "tender_leg", "return"}
        if record_type is not None and record_type not in allowed:
            raise ValueError(f"record_type must be one of: {', '.join(sorted(allowed))}")
        records = self._compact_records()
        def keep(r: dict[str, Any]) -> bool:
            if customer_id is not None and r["customer_id"] != customer_id: return False
            if record_type is not None and r["record_type"] != record_type: return False
            if order_id is not None and r.get("order_id") != order_id: return False
            if sku is not None and r.get("sku") != sku: return False
            if from_at is not None and (r.get("event_at") is None or r["event_at"] < from_at): return False
            if to_at is not None and (r.get("event_at") is None or r["event_at"] > to_at): return False
            return True
        selected = [r for r in records if keep(r)]
        return {"grain": "one source record per member; record_type declares member grain", "filters": {
            "customer_id": customer_id, "record_type": record_type, "order_id": order_id,
            "sku": sku, "from_at": from_at, "to_at": to_at,
        }, "count": len(selected), "records": selected}

    def _compact_records(self) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        with self._connect() as db:
            queries = [
                ("order", "order_id", "SELECT o.*, o.ordered_at event_at FROM commerce_order o", "order_total_cents", "currency_code"),
                ("order_line", "order_line_id", "SELECT l.*, o.customer_id, o.currency_code, NULL event_at FROM order_line l JOIN commerce_order o USING(order_id)", "line_amount_cents", "currency_code"),
                ("fulfillment_event", "fulfillment_event_id", "SELECT f.*, l.order_id, l.sku, o.customer_id, o.currency_code FROM fulfillment_event f JOIN order_line l USING(order_line_id) JOIN commerce_order o USING(order_id)", "amount_cents", "currency_code"),
                ("payment", "payment_id", "SELECT p.*, NULL event_at FROM payment p", None, None),
                ("payment_event", "event_id", "SELECT e.*, p.customer_id, p.order_id FROM payment_event e JOIN payment p USING(payment_id)", "amount_cents", "currency_code"),
                ("receipt", "receipt_id", "SELECT r.*, r.transacted_at event_at FROM pos_receipt r", "receipt_total_cents", "currency_code"),
                ("receipt_item", "receipt_item_id", "SELECT i.*, r.customer_id, r.currency_code, r.transacted_at event_at FROM receipt_item_occurrence i JOIN pos_receipt r USING(receipt_id)", "item_amount_cents", "currency_code"),
                ("tender_leg", "tender_leg_id", "SELECT t.*, r.customer_id, r.currency_code, r.transacted_at event_at FROM tender_leg t JOIN pos_receipt r USING(receipt_id)", "amount_cents", "currency_code"),
                ("return", "return_id", "SELECT m.*, m.returned_at event_at FROM merchandise_return m", "merchandise_value_cents", "currency_code"),
            ]
            for kind, id_key, sql, amount_key, currency_key in queries:
                for row in db.execute(sql):
                    source = _dict(row)
                    record = {"record_type": kind, "record_id": source[id_key], **source}
                    if amount_key:
                        record["money"] = money(record.pop(amount_key), record[currency_key])
                    records.append(record)
        return sorted(records, key=lambda r: (r["record_type"], r["record_id"]))


def initialize_database(database: str | Path, schema: str | Path, seed: str | Path) -> None:
    target = Path(database)
    if target.exists():
        raise FileExistsError(f"refusing to overwrite existing database: {target}")
    connection = sqlite3.connect(target)
    try:
        connection.executescript(Path(schema).read_text(encoding="utf-8"))
        connection.executescript(Path(seed).read_text(encoding="utf-8"))
    finally:
        connection.close()
