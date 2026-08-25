"""Read-only, contract-preserving access to the investigation database."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Iterable


class NotFoundError(LookupError):
    pass


def _money(value: Any, semantic_type: str, source_table: str, source_id: str) -> dict[str, Any]:
    return {
        "amount": f"{float(value):.2f}",
        "currency": "UNKNOWN",
        "semantic_type": semantic_type,
        "lineage": {"source_table": source_table, "source_ids": [source_id], "aggregation": "none"},
    }


def _row(row: sqlite3.Row) -> dict[str, Any]:
    return dict(row)


class InvestigationRepository:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")

    def _one(self, sql: str, params: Iterable[Any], entity: str, identity: str) -> sqlite3.Row:
        result = self.connection.execute(sql, tuple(params)).fetchone()
        if result is None:
            raise NotFoundError(f"{entity} {identity!r} was not found")
        return result

    def list_customers(self) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT customer_ref_id, display_name FROM customer_reference ORDER BY customer_ref_id"
        ).fetchall()
        return [{"grain": "customer_reference", **_row(r)} for r in rows]

    def get_customer(self, customer_ref_id: str) -> dict[str, Any]:
        customer = self._one(
            "SELECT customer_ref_id, display_name FROM customer_reference WHERE customer_ref_id = ?",
            [customer_ref_id], "customer", customer_ref_id,
        )
        orders = self.connection.execute(
            "SELECT order_id FROM orders WHERE customer_ref_id = ? ORDER BY ordered_at, order_id",
            [customer_ref_id],
        ).fetchall()
        receipts = self.connection.execute(
            "SELECT receipt_id FROM pos_receipt WHERE customer_ref_id = ? ORDER BY business_date, receipt_id",
            [customer_ref_id],
        ).fetchall()
        returns = self.connection.execute(
            "SELECT return_id FROM merchandise_return WHERE customer_ref_id = ? ORDER BY returned_at, return_id",
            [customer_ref_id],
        ).fetchall()
        return {
            "grain": "customer_reference",
            **_row(customer),
            "orders": [self.get_order(r["order_id"]) for r in orders],
            "receipts": [self.get_receipt(r["receipt_id"]) for r in receipts],
            "returns": [self.get_return(r["return_id"]) for r in returns],
        }

    def get_order(self, order_id: str) -> dict[str, Any]:
        order = self._one("SELECT * FROM orders WHERE order_id = ?", [order_id], "order", order_id)
        lines = self.connection.execute(
            "SELECT * FROM order_line WHERE order_id = ? ORDER BY order_line_id", [order_id]
        ).fetchall()
        payments = self.connection.execute(
            "SELECT payment_id FROM payment WHERE order_id = ? ORDER BY payment_id", [order_id]
        ).fetchall()
        return {
            "grain": "order",
            "order_id": order["order_id"],
            "customer_ref_id": order["customer_ref_id"],
            "order_number": order["order_number"],
            "ordered_total": _money(order["ordered_total"], "ordered_total", "orders", order_id),
            "ordered_at": {"value": order["ordered_at"], "meaning": "order_placed_at"},
            "created_at": {"value": order["created_at"], "meaning": "order_record_created_at"},
            "lines": [self._line(r) for r in lines],
            "payments": [self.get_payment(r["payment_id"]) for r in payments],
            "collection_semantics": "lines and payments are independent order children; no allocation is implied",
        }

    def _line(self, line: sqlite3.Row) -> dict[str, Any]:
        line_id = line["order_line_id"]
        events = self.connection.execute(
            "SELECT * FROM fulfillment_event WHERE order_line_id = ? ORDER BY occurred_at, fulfillment_event_id",
            [line_id],
        ).fetchall()
        return {
            "grain": "order_line",
            "order_line_id": line_id,
            "order_id": line["order_id"],
            "sku": line["sku"],
            "ordered_quantity": str(line["ordered_quantity"]),
            "line_merchandise_amount": _money(line["line_merchandise_amount"], "line_merchandise_amount", "order_line", line_id),
            "line_tax_amount": _money(line["line_tax_amount"], "line_tax_amount", "order_line", line_id),
            "fulfillment_events": [{
                "grain": "fulfillment_event",
                "fulfillment_event_id": e["fulfillment_event_id"],
                "order_line_id": e["order_line_id"],
                "fulfilled_quantity": str(e["fulfilled_quantity"]),
                "occurred_at": {"value": e["occurred_at"], "meaning": "fulfillment_occurred_at"},
            } for e in events],
        }

    def get_payment(self, payment_id: str) -> dict[str, Any]:
        payment = self._one("SELECT * FROM payment WHERE payment_id = ?", [payment_id], "payment", payment_id)
        auths = self.connection.execute(
            "SELECT * FROM payment_authorization WHERE payment_id = ? ORDER BY authorized_at, authorization_id", [payment_id]
        ).fetchall()
        settlements = self.connection.execute(
            "SELECT * FROM payment_settlement WHERE payment_id = ? ORDER BY settled_at, settlement_id", [payment_id]
        ).fetchall()
        return {
            "grain": "payment",
            "payment_id": payment_id,
            "order_id": payment["order_id"],
            "payment_amount": _money(payment["payment_amount"], "payment_amount", "payment", payment_id),
            "authorizations": [{
                "grain": "payment_authorization",
                "authorization_id": a["authorization_id"], "payment_id": payment_id,
                "authorization_amount": _money(a["authorization_amount"], "authorization_attempt_amount", "payment_authorization", a["authorization_id"]),
                "authorization_status": a["authorization_status"],
                "authorized_at": {"value": a["authorized_at"], "meaning": "authorization_attempted_at"},
            } for a in auths],
            "settlements": [{
                "grain": "payment_settlement",
                "settlement_id": s["settlement_id"], "payment_id": payment_id,
                "settlement_amount": _money(s["settlement_amount"], "settlement_event_amount", "payment_settlement", s["settlement_id"]),
                "settlement_type": s["settlement_type"],
                "settled_at": {"value": s["settled_at"], "meaning": "settlement_occurred_at"},
            } for s in settlements],
            "collection_semantics": "authorizations and settlements are distinct payment facts",
        }

    def get_receipt(self, receipt_id: str) -> dict[str, Any]:
        receipt = self._one("SELECT * FROM pos_receipt WHERE receipt_id = ?", [receipt_id], "receipt", receipt_id)
        items = self.connection.execute(
            "SELECT * FROM pos_item_occurrence WHERE receipt_id = ? ORDER BY receipt_item_id", [receipt_id]
        ).fetchall()
        tenders = self.connection.execute(
            "SELECT * FROM pos_tender_leg WHERE receipt_id = ? ORDER BY tender_leg_id", [receipt_id]
        ).fetchall()
        return {
            "grain": "pos_receipt", "receipt_id": receipt_id,
            "customer_ref_id": receipt["customer_ref_id"], "business_date": receipt["business_date"],
            "location_id": receipt["location_id"], "register_id": receipt["register_id"],
            "transaction_number": receipt["transaction_number"],
            "receipt_total": _money(receipt["receipt_total"], "receipt_total", "pos_receipt", receipt_id),
            "items": [{
                "grain": "pos_item_occurrence", "receipt_item_id": i["receipt_item_id"],
                "receipt_id": receipt_id, "sku": i["sku"], "quantity": str(i["quantity"]),
                "item_amount": _money(i["item_amount"], "pos_item_occurrence_amount", "pos_item_occurrence", i["receipt_item_id"]),
            } for i in items],
            "tenders": [{
                "grain": "pos_tender_leg", "tender_leg_id": t["tender_leg_id"],
                "receipt_id": receipt_id, "tender_type": t["tender_type"],
                "tender_amount": _money(t["tender_amount"], "tender_leg_amount", "pos_tender_leg", t["tender_leg_id"]),
            } for t in tenders],
            "collection_semantics": "items and tenders are independent receipt children; no allocation is implied",
        }

    def get_return(self, return_id: str) -> dict[str, Any]:
        ret = self._one("SELECT * FROM merchandise_return WHERE return_id = ?", [return_id], "return", return_id)
        refunds = self.connection.execute(
            "SELECT * FROM refund WHERE return_id = ? ORDER BY refunded_at, refund_id", [return_id]
        ).fetchall()
        return {
            "grain": "merchandise_return", "return_id": return_id,
            "customer_ref_id": ret["customer_ref_id"], "original_order_id": ret["original_order_id"],
            "original_receipt_id": ret["original_receipt_id"],
            "return_merchandise_value": _money(ret["return_merchandise_value"], "return_merchandise_value", "merchandise_return", return_id),
            "returned_at": {"value": ret["returned_at"], "meaning": "merchandise_returned_at"},
            "refunds": [{
                "grain": "refund", "refund_id": r["refund_id"], "return_id": return_id,
                "refund_amount": _money(r["refund_amount"], "refund_amount", "refund", r["refund_id"]),
                "refunded_at": {"value": r["refunded_at"], "meaning": "refund_issued_at"},
            } for r in refunds],
        }

    def timeline(self, customer_ref_id: str) -> dict[str, Any]:
        self._one("SELECT 1 FROM customer_reference WHERE customer_ref_id = ?", [customer_ref_id], "customer", customer_ref_id)
        sql = """
        SELECT 'order_placed' event_type, o.ordered_at event_at, 'order_placed_at' timestamp_meaning,
               'orders' source_table, o.order_id source_id, o.ordered_total amount, 'ordered_total' amount_semantic
          FROM orders o WHERE o.customer_ref_id = ?
        UNION ALL SELECT 'authorization_attempt', a.authorized_at, 'authorization_attempted_at',
               'payment_authorization', a.authorization_id, a.authorization_amount, 'authorization_attempt_amount'
          FROM payment_authorization a JOIN payment p ON p.payment_id=a.payment_id JOIN orders o ON o.order_id=p.order_id WHERE o.customer_ref_id = ?
        UNION ALL SELECT 'settlement', s.settled_at, 'settlement_occurred_at',
               'payment_settlement', s.settlement_id, s.settlement_amount, 'settlement_event_amount'
          FROM payment_settlement s JOIN payment p ON p.payment_id=s.payment_id JOIN orders o ON o.order_id=p.order_id WHERE o.customer_ref_id = ?
        UNION ALL SELECT 'fulfillment', f.occurred_at, 'fulfillment_occurred_at',
               'fulfillment_event', f.fulfillment_event_id, NULL, NULL
          FROM fulfillment_event f JOIN order_line l ON l.order_line_id=f.order_line_id JOIN orders o ON o.order_id=l.order_id WHERE o.customer_ref_id = ?
        UNION ALL SELECT 'pos_receipt', r.business_date || ' 00:00:00', 'receipt_business_date',
               'pos_receipt', r.receipt_id, r.receipt_total, 'receipt_total'
          FROM pos_receipt r WHERE r.customer_ref_id = ?
        UNION ALL SELECT 'merchandise_return', m.returned_at, 'merchandise_returned_at',
               'merchandise_return', m.return_id, m.return_merchandise_value, 'return_merchandise_value'
          FROM merchandise_return m WHERE m.customer_ref_id = ?
        UNION ALL SELECT 'refund', r.refunded_at, 'refund_issued_at',
               'refund', r.refund_id, r.refund_amount, 'refund_amount'
          FROM refund r JOIN merchandise_return m ON m.return_id=r.return_id WHERE m.customer_ref_id = ?
        ORDER BY event_at, event_type, source_id
        """
        rows = self.connection.execute(sql, [customer_ref_id] * 7).fetchall()
        events = []
        for r in rows:
            event = {
                "grain": "timeline_event", "event_type": r["event_type"],
                "event_at": {"value": r["event_at"], "meaning": r["timestamp_meaning"]},
                "source": {"table": r["source_table"], "id": r["source_id"]},
            }
            if r["amount"] is not None:
                event["money"] = _money(r["amount"], r["amount_semantic"], r["source_table"], r["source_id"])
            events.append(event)
        return {
            "grain": "customer_timeline", "customer_ref_id": customer_ref_id,
            "events": events,
            "projection_note": "Derived chronological composition of typed source facts; receipt business dates sort at midnight because source time is unknown.",
        }


def initialize_database(database_path: str | Path, schema_path: str | Path, seed_path: str | Path) -> None:
    """Create a fresh local database from the unmodified supplied SQL files."""
    connection = sqlite3.connect(database_path)
    try:
        connection.executescript(Path(schema_path).read_text(encoding="utf-8"))
        connection.executescript(Path(seed_path).read_text(encoding="utf-8"))
        connection.commit()
    finally:
        connection.close()
