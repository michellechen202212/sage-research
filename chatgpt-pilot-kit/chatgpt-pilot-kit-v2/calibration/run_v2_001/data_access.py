"""SQLite data-access and investigation projections."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent


def create_database() -> sqlite3.Connection:
    """Create a deterministic database from the supplied, unmodified SQL files."""
    connection = sqlite3.connect(":memory:", check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript((ROOT / "schema.sql").read_text(encoding="utf-8"))
    connection.executescript((ROOT / "seed.sql").read_text(encoding="utf-8"))
    return connection


def _money(value: Any) -> str:
    return f"{float(value):.2f}"


def _quantity(value: Any) -> str:
    return f"{float(value):.3f}"


class NotFoundError(LookupError):
    pass


class InvestigationRepository:
    def __init__(self, connection: sqlite3.Connection):
        self.db = connection

    def _one(self, sql: str, parameters: tuple[Any, ...], kind: str, key: str) -> sqlite3.Row:
        row = self.db.execute(sql, parameters).fetchone()
        if row is None:
            raise NotFoundError(f"{kind} '{key}' was not found")
        return row

    def customer_activity(self, customer_id: str) -> dict[str, Any]:
        customer = self._one(
            "SELECT customer_ref_id, display_name FROM customer_reference WHERE customer_ref_id = ?",
            (customer_id,), "customer", customer_id,
        )
        orders = self.db.execute(
            "SELECT order_id FROM orders WHERE customer_ref_id = ? ORDER BY ordered_at, order_id",
            (customer_id,),
        ).fetchall()
        returns = self.db.execute(
            """SELECT return_id, original_order_id, original_receipt_id,
                      return_merchandise_value, returned_at
               FROM merchandise_return WHERE customer_ref_id = ?
               ORDER BY returned_at, return_id""",
            (customer_id,),
        ).fetchall()
        return {
            "customer": dict(customer),
            "orders": [self.order_detail(row["order_id"]) for row in orders],
            "receipts": self.receipt_projection(customer_id=customer_id),
            "returns": [self._return_object(row) for row in returns],
            "timeline": self.timeline(customer_id),
        }

    def order_detail(self, order_id: str) -> dict[str, Any]:
        order = self._one(
            """SELECT order_id, customer_ref_id, order_number, ordered_total,
                      ordered_at, created_at FROM orders WHERE order_id = ?""",
            (order_id,), "order", order_id,
        )
        lines = self.db.execute(
            """SELECT order_line_id, sku, ordered_quantity,
                      line_merchandise_amount, line_tax_amount
               FROM order_line WHERE order_id = ? ORDER BY order_line_id""",
            (order_id,),
        ).fetchall()
        payments = self.db.execute(
            "SELECT payment_id FROM payment WHERE order_id = ? ORDER BY payment_id", (order_id,)
        ).fetchall()
        result = dict(order)
        result["ordered_total"] = _money(result["ordered_total"])
        result["lines"] = []
        for line in lines:
            item = dict(line)
            item["ordered_quantity"] = _quantity(item["ordered_quantity"])
            item["line_merchandise_amount"] = _money(item["line_merchandise_amount"])
            item["line_tax_amount"] = _money(item["line_tax_amount"])
            events = self.db.execute(
                """SELECT fulfillment_event_id, fulfilled_quantity, occurred_at
                   FROM fulfillment_event WHERE order_line_id = ?
                   ORDER BY occurred_at, fulfillment_event_id""",
                (item["order_line_id"],),
            ).fetchall()
            item["fulfillment_events"] = [
                {**dict(event), "fulfilled_quantity": _quantity(event["fulfilled_quantity"])}
                for event in events
            ]
            result["lines"].append(item)
        result["payments"] = [self.payment_activity(row["payment_id"]) for row in payments]
        return result

    def payment_activity(self, payment_id: str) -> dict[str, Any]:
        payment = self._one(
            "SELECT payment_id, order_id, payment_amount FROM payment WHERE payment_id = ?",
            (payment_id,), "payment", payment_id,
        )
        authorizations = self.db.execute(
            """SELECT authorization_id, authorization_amount, authorization_status, authorized_at
               FROM payment_authorization WHERE payment_id = ?
               ORDER BY authorized_at, authorization_id""", (payment_id,),
        ).fetchall()
        settlements = self.db.execute(
            """SELECT settlement_id, settlement_amount, settlement_type, settled_at
               FROM payment_settlement WHERE payment_id = ?
               ORDER BY settled_at, settlement_id""", (payment_id,),
        ).fetchall()
        return {
            **dict(payment),
            "payment_amount": _money(payment["payment_amount"]),
            "authorizations": [
                {**dict(row), "authorization_amount": _money(row["authorization_amount"])}
                for row in authorizations
            ],
            "settlements": [
                {**dict(row), "settlement_amount": _money(row["settlement_amount"])}
                for row in settlements
            ],
            "settled_total": _money(sum(float(row["settlement_amount"]) for row in settlements)),
        }

    def receipt_detail(self, receipt_id: str) -> dict[str, Any]:
        receipt = self._one(
            """SELECT receipt_id, customer_ref_id, business_date, location_id,
                      register_id, transaction_number, receipt_total
               FROM pos_receipt WHERE receipt_id = ?""",
            (receipt_id,), "receipt", receipt_id,
        )
        return self._receipt_object(receipt)

    def receipt_projection(
        self, *, customer_id: str | None = None, location_id: str | None = None,
        business_date: str | None = None, sku: str | None = None,
        tender_type: str | None = None,
    ) -> list[dict[str, Any]]:
        clauses, values = [], []
        if customer_id:
            clauses.append("r.customer_ref_id = ?"); values.append(customer_id)
        if location_id:
            clauses.append("r.location_id = ?"); values.append(location_id)
        if business_date:
            clauses.append("r.business_date = ?"); values.append(business_date)
        if sku:
            clauses.append("EXISTS (SELECT 1 FROM pos_item_occurrence i WHERE i.receipt_id=r.receipt_id AND i.sku=?)")
            values.append(sku)
        if tender_type:
            clauses.append("EXISTS (SELECT 1 FROM pos_tender_leg t WHERE t.receipt_id=r.receipt_id AND t.tender_type=?)")
            values.append(tender_type)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        rows = self.db.execute(
            """SELECT r.receipt_id, r.customer_ref_id, r.business_date, r.location_id,
                      r.register_id, r.transaction_number, r.receipt_total
               FROM pos_receipt r""" + where + " ORDER BY r.business_date, r.receipt_id",
            tuple(values),
        ).fetchall()
        return [self._receipt_object(row) for row in rows]

    def _receipt_object(self, receipt: sqlite3.Row) -> dict[str, Any]:
        items = self.db.execute(
            """SELECT receipt_item_id, sku, quantity, item_amount FROM pos_item_occurrence
               WHERE receipt_id = ? ORDER BY receipt_item_id""", (receipt["receipt_id"],),
        ).fetchall()
        tenders = self.db.execute(
            """SELECT tender_leg_id, tender_type, tender_amount FROM pos_tender_leg
               WHERE receipt_id = ? ORDER BY tender_leg_id""", (receipt["receipt_id"],),
        ).fetchall()
        result = dict(receipt)
        result["receipt_total"] = _money(result["receipt_total"])
        result["items"] = [
            {**dict(row), "quantity": _quantity(row["quantity"]), "item_amount": _money(row["item_amount"])}
            for row in items
        ]
        result["tender_legs"] = [
            {**dict(row), "tender_amount": _money(row["tender_amount"])} for row in tenders
        ]
        result["item_total"] = _money(sum(float(row["item_amount"]) for row in items))
        result["tender_total"] = _money(sum(float(row["tender_amount"]) for row in tenders))
        return result

    def _return_object(self, row: sqlite3.Row) -> dict[str, Any]:
        refunds = self.db.execute(
            "SELECT refund_id, refund_amount, refunded_at FROM refund WHERE return_id = ? ORDER BY refunded_at, refund_id",
            (row["return_id"],),
        ).fetchall()
        return {
            **dict(row),
            "return_merchandise_value": _money(row["return_merchandise_value"]),
            "refunds": [{**dict(item), "refund_amount": _money(item["refund_amount"])} for item in refunds],
            "refunded_total": _money(sum(float(item["refund_amount"]) for item in refunds)),
        }

    def timeline(self, customer_id: str) -> list[dict[str, Any]]:
        self._one("SELECT customer_ref_id FROM customer_reference WHERE customer_ref_id=?", (customer_id,), "customer", customer_id)
        rows = self.db.execute(
            """SELECT occurred_at, event_type, source_id, related_id, amount, status FROM (
                SELECT o.ordered_at occurred_at, 'ORDER_PLACED' event_type, o.order_id source_id,
                       NULL related_id, o.ordered_total amount, NULL status
                  FROM orders o WHERE o.customer_ref_id = ?
                UNION ALL SELECT pa.authorized_at, 'PAYMENT_AUTHORIZATION', pa.authorization_id,
                       p.payment_id, pa.authorization_amount, pa.authorization_status
                  FROM payment_authorization pa JOIN payment p USING(payment_id)
                  JOIN orders o USING(order_id) WHERE o.customer_ref_id = ?
                UNION ALL SELECT ps.settled_at, 'PAYMENT_SETTLEMENT', ps.settlement_id,
                       p.payment_id, ps.settlement_amount, ps.settlement_type
                  FROM payment_settlement ps JOIN payment p USING(payment_id)
                  JOIN orders o USING(order_id) WHERE o.customer_ref_id = ?
                UNION ALL SELECT fe.occurred_at, 'FULFILLMENT', fe.fulfillment_event_id,
                       ol.order_line_id, NULL, NULL FROM fulfillment_event fe
                  JOIN order_line ol USING(order_line_id) JOIN orders o USING(order_id)
                  WHERE o.customer_ref_id = ?
                UNION ALL SELECT r.business_date || ' 00:00:00', 'POS_RECEIPT', r.receipt_id,
                       NULL, r.receipt_total, NULL FROM pos_receipt r WHERE r.customer_ref_id = ?
                UNION ALL SELECT mr.returned_at, 'RETURN', mr.return_id,
                       COALESCE(mr.original_order_id, mr.original_receipt_id), mr.return_merchandise_value, NULL
                  FROM merchandise_return mr WHERE mr.customer_ref_id = ?
                UNION ALL SELECT rf.refunded_at, 'REFUND', rf.refund_id, rf.return_id,
                       rf.refund_amount, NULL FROM refund rf JOIN merchandise_return mr USING(return_id)
                  WHERE mr.customer_ref_id = ?
            ) ORDER BY occurred_at, event_type, source_id""",
            (customer_id,) * 7,
        ).fetchall()
        return [
            {**dict(row), "amount": _money(row["amount"]) if row["amount"] is not None else None}
            for row in rows
        ]
