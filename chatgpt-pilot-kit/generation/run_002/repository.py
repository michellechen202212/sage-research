"""Data access and contract-preserving projections for the investigation API."""
from __future__ import annotations

import sqlite3
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parent


def connect(database: str | Path = ":memory:") -> sqlite3.Connection:
    # ThreadingHTTPServer handles requests on worker threads; repository access is read-only.
    connection = sqlite3.connect(str(database), check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize(connection: sqlite3.Connection) -> None:
    """Load the supplied, unmodified DDL and fixtures into an empty database."""
    connection.executescript((ROOT / "schema.sql").read_text(encoding="utf-8"))
    connection.executescript((ROOT / "seed.sql").read_text(encoding="utf-8"))
    connection.commit()


def _decimal(value: Any) -> str:
    return format(Decimal(str(value)).quantize(Decimal("0.01")), "f")


def money(value: Any, semantic: str, source_ids: Iterable[str], aggregation: str = "source_value") -> dict:
    """A typed monetary value. Currency is UNKNOWN because the source has none."""
    return {
        "grain": "monetary_value",
        "amount": _decimal(value),
        "currency": "UNKNOWN",
        "semantic": semantic,
        "source_ids": list(source_ids),
        "aggregation": aggregation,
    }


class NotFound(LookupError):
    pass


class InvestigationRepository:
    def __init__(self, connection: sqlite3.Connection):
        self.db = connection

    def _one(self, sql: str, args: tuple, entity: str) -> sqlite3.Row:
        row = self.db.execute(sql, args).fetchone()
        if row is None:
            raise NotFound(entity)
        return row

    def customers(self) -> list[dict]:
        rows = self.db.execute("SELECT * FROM customer_reference ORDER BY customer_ref_id").fetchall()
        return [{"grain": "customer", "customer_ref_id": r["customer_ref_id"], "display_name": r["display_name"]} for r in rows]

    def customer(self, customer_id: str) -> dict:
        r = self._one("SELECT * FROM customer_reference WHERE customer_ref_id = ?", (customer_id,), "customer")
        return {"grain": "customer", "customer_ref_id": r["customer_ref_id"], "display_name": r["display_name"]}

    def orders(self, customer_id: str) -> list[dict]:
        self.customer(customer_id)
        rows = self.db.execute("SELECT * FROM orders WHERE customer_ref_id = ? ORDER BY ordered_at, order_id", (customer_id,)).fetchall()
        return [self._order_summary(r) for r in rows]

    def _order_summary(self, r: sqlite3.Row) -> dict:
        return {
            "grain": "order",
            "order_id": r["order_id"],
            "order_number": r["order_number"],
            "customer_ref_id": r["customer_ref_id"],
            "ordered_total": money(r["ordered_total"], "order_ordered_total", [r["order_id"]]),
            "ordered_at": r["ordered_at"],
            "created_at": r["created_at"],
        }

    def order(self, order_id: str) -> dict:
        r = self._one("SELECT * FROM orders WHERE order_id = ?", (order_id,), "order")
        result = self._order_summary(r)
        lines = self.db.execute("SELECT * FROM order_line WHERE order_id = ? ORDER BY order_line_id", (order_id,)).fetchall()
        payments = self.db.execute("SELECT * FROM payment WHERE order_id = ? ORDER BY payment_id", (order_id,)).fetchall()
        result["lines"] = [{
            "grain": "order_line", "order_line_id": x["order_line_id"], "order_id": x["order_id"],
            "sku": x["sku"], "ordered_quantity": str(x["ordered_quantity"]),
            "line_merchandise_amount": money(x["line_merchandise_amount"], "order_line_merchandise_amount", [x["order_line_id"]]),
            "line_tax_amount": money(x["line_tax_amount"], "order_line_tax_amount", [x["order_line_id"]]),
            "fulfillment_events": self._fulfillments(x["order_line_id"]),
        } for x in lines]
        result["payments"] = [self.payment(x["payment_id"]) for x in payments]
        result["collection_relationships"] = {
            "grain": "projection_metadata", "lines_and_payments": "independent_order_children_no_allocation"
        }
        return result

    def _fulfillments(self, line_id: str) -> list[dict]:
        rows = self.db.execute("SELECT * FROM fulfillment_event WHERE order_line_id = ? ORDER BY occurred_at, fulfillment_event_id", (line_id,)).fetchall()
        return [{"grain": "fulfillment_event", "fulfillment_event_id": r["fulfillment_event_id"],
                 "order_line_id": r["order_line_id"], "fulfilled_quantity": str(r["fulfilled_quantity"]),
                 "occurred_at": r["occurred_at"]} for r in rows]

    def payment(self, payment_id: str) -> dict:
        p = self._one("SELECT * FROM payment WHERE payment_id = ?", (payment_id,), "payment")
        auths = self.db.execute("SELECT * FROM payment_authorization WHERE payment_id = ? ORDER BY authorized_at, authorization_id", (payment_id,)).fetchall()
        settlements = self.db.execute("SELECT * FROM payment_settlement WHERE payment_id = ? ORDER BY settled_at, settlement_id", (payment_id,)).fetchall()
        return {
            "grain": "payment", "payment_id": p["payment_id"], "order_id": p["order_id"],
            "payment_amount": money(p["payment_amount"], "payment_declared_amount", [p["payment_id"]]),
            "authorization_attempts": [{
                "grain": "payment_authorization", "authorization_id": a["authorization_id"], "payment_id": a["payment_id"],
                "authorization_amount": money(a["authorization_amount"], "authorization_attempt_amount", [a["authorization_id"]]),
                "authorization_status": a["authorization_status"], "authorized_at": a["authorized_at"]
            } for a in auths],
            "settlement_events": [{
                "grain": "payment_settlement", "settlement_id": s["settlement_id"], "payment_id": s["payment_id"],
                "settlement_amount": money(s["settlement_amount"], "payment_settlement_amount", [s["settlement_id"]]),
                "settlement_type": s["settlement_type"], "settled_at": s["settled_at"]
            } for s in settlements],
            "collection_relationships": {"grain": "projection_metadata", "authorizations_and_settlements": "distinct_payment_facts"},
        }

    def receipts(self, customer_id: str) -> list[dict]:
        self.customer(customer_id)
        rows = self.db.execute("SELECT receipt_id FROM pos_receipt WHERE customer_ref_id = ? ORDER BY business_date, receipt_id", (customer_id,)).fetchall()
        return [self.receipt(r["receipt_id"]) for r in rows]

    def receipt(self, receipt_id: str) -> dict:
        r = self._one("SELECT * FROM pos_receipt WHERE receipt_id = ?", (receipt_id,), "receipt")
        items = self.db.execute("SELECT * FROM pos_item_occurrence WHERE receipt_id = ? ORDER BY receipt_item_id", (receipt_id,)).fetchall()
        tenders = self.db.execute("SELECT * FROM pos_tender_leg WHERE receipt_id = ? ORDER BY tender_leg_id", (receipt_id,)).fetchall()
        return {
            "grain": "pos_receipt", "receipt_id": r["receipt_id"], "customer_ref_id": r["customer_ref_id"],
            "business_date": r["business_date"], "location_id": r["location_id"], "register_id": r["register_id"],
            "transaction_number": r["transaction_number"],
            "receipt_total": money(r["receipt_total"], "pos_receipt_total", [r["receipt_id"]]),
            "items": [{"grain": "pos_item_occurrence", "receipt_item_id": x["receipt_item_id"], "receipt_id": x["receipt_id"],
                       "sku": x["sku"], "quantity": str(x["quantity"]),
                       "item_amount": money(x["item_amount"], "pos_item_occurrence_amount", [x["receipt_item_id"]])} for x in items],
            "tender_legs": [{"grain": "pos_tender_leg", "tender_leg_id": x["tender_leg_id"], "receipt_id": x["receipt_id"],
                             "tender_type": x["tender_type"],
                             "tender_amount": money(x["tender_amount"], "pos_tender_leg_amount", [x["tender_leg_id"]])} for x in tenders],
            "collection_relationships": {"grain": "projection_metadata", "items_and_tenders": "independent_receipt_children_no_allocation"},
        }

    def returns(self, customer_id: str) -> list[dict]:
        self.customer(customer_id)
        rows = self.db.execute("SELECT * FROM merchandise_return WHERE customer_ref_id = ? ORDER BY returned_at, return_id", (customer_id,)).fetchall()
        result = []
        for r in rows:
            refunds = self.db.execute("SELECT * FROM refund WHERE return_id = ? ORDER BY refunded_at, refund_id", (r["return_id"],)).fetchall()
            result.append({
                "grain": "merchandise_return", "return_id": r["return_id"], "customer_ref_id": r["customer_ref_id"],
                "original_order_id": r["original_order_id"], "original_receipt_id": r["original_receipt_id"],
                "return_merchandise_value": money(r["return_merchandise_value"], "returned_merchandise_value", [r["return_id"]]),
                "returned_at": r["returned_at"],
                "refunds": [{"grain": "refund", "refund_id": x["refund_id"], "return_id": x["return_id"],
                             "refund_amount": money(x["refund_amount"], "refund_issued_amount", [x["refund_id"]]),
                             "refunded_at": x["refunded_at"]} for x in refunds],
            })
        return result

    def timeline(self, customer_id: str) -> list[dict]:
        """Typed events only; UNION ALL avoids cross-products and preserves identity."""
        self.customer(customer_id)
        sql = """
        SELECT o.ordered_at ts, 'order_placed' type, o.order_id id, o.ordered_total amount, 'order_ordered_total' semantic FROM orders o WHERE o.customer_ref_id=?
        UNION ALL SELECT o.created_at, 'order_created', o.order_id, NULL, NULL FROM orders o WHERE o.customer_ref_id=?
        UNION ALL SELECT a.authorized_at, 'payment_authorization', a.authorization_id, a.authorization_amount, 'authorization_attempt_amount' FROM payment_authorization a JOIN payment p ON p.payment_id=a.payment_id JOIN orders o ON o.order_id=p.order_id WHERE o.customer_ref_id=?
        UNION ALL SELECT s.settled_at, 'payment_settlement', s.settlement_id, s.settlement_amount, 'payment_settlement_amount' FROM payment_settlement s JOIN payment p ON p.payment_id=s.payment_id JOIN orders o ON o.order_id=p.order_id WHERE o.customer_ref_id=?
        UNION ALL SELECT f.occurred_at, 'fulfillment', f.fulfillment_event_id, NULL, NULL FROM fulfillment_event f JOIN order_line l ON l.order_line_id=f.order_line_id JOIN orders o ON o.order_id=l.order_id WHERE o.customer_ref_id=?
        UNION ALL SELECT r.business_date || ' 00:00:00', 'pos_receipt_business_date', r.receipt_id, r.receipt_total, 'pos_receipt_total' FROM pos_receipt r WHERE r.customer_ref_id=?
        UNION ALL SELECT r.returned_at, 'merchandise_return', r.return_id, r.return_merchandise_value, 'returned_merchandise_value' FROM merchandise_return r WHERE r.customer_ref_id=?
        UNION ALL SELECT x.refunded_at, 'refund', x.refund_id, x.refund_amount, 'refund_issued_amount' FROM refund x JOIN merchandise_return r ON r.return_id=x.return_id WHERE r.customer_ref_id=?
        ORDER BY ts, type, id
        """
        rows = self.db.execute(sql, (customer_id,) * 8).fetchall()
        return [{"grain": "timeline_event", "event_type": r["type"], "source_id": r["id"],
                 "event_at": r["ts"], "timestamp_semantic": r["type"],
                 **({"monetary_value": money(r["amount"], r["semantic"], [r["id"]])} if r["amount"] is not None else {})}
                for r in rows]

    def activity(self, customer_id: str) -> dict:
        return {"grain": "customer_activity", "customer": self.customer(customer_id),
                "orders": self.orders(customer_id), "receipts": self.receipts(customer_id),
                "returns": self.returns(customer_id), "timeline": self.timeline(customer_id),
                "projection_note": "Bounded independent collections; no inferred allocations."}
