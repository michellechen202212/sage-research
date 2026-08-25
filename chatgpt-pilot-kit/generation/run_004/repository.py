"""SQLite data-access layer for the commerce investigation application."""

from __future__ import annotations

import sqlite3
from decimal import Decimal
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent


def money(value: Any) -> str:
    """Return a stable JSON-safe representation of a monetary value."""
    return format(Decimal(str(value)).quantize(Decimal("0.01")), "f")


class NotFoundError(LookupError):
    pass


class InvestigationRepository:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")

    @classmethod
    def from_fixtures(cls) -> "InvestigationRepository":
        connection = sqlite3.connect(":memory:", check_same_thread=False)
        connection.executescript((ROOT / "schema.sql").read_text(encoding="utf-8"))
        connection.executescript((ROOT / "seed.sql").read_text(encoding="utf-8"))
        return cls(connection)

    def _one(self, sql: str, values: tuple[Any, ...]) -> dict[str, Any]:
        row = self.connection.execute(sql, values).fetchone()
        if row is None:
            raise NotFoundError(values[0])
        return dict(row)

    def _all(self, sql: str, values: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        return [dict(row) for row in self.connection.execute(sql, values)]

    def list_customers(self) -> list[dict[str, Any]]:
        rows = self._all("""
            SELECT c.customer_ref_id, c.display_name,
                   COUNT(DISTINCT o.order_id) AS order_count,
                   COUNT(DISTINCT r.receipt_id) AS receipt_count
            FROM customer_reference c
            LEFT JOIN orders o ON o.customer_ref_id = c.customer_ref_id
            LEFT JOIN pos_receipt r ON r.customer_ref_id = c.customer_ref_id
            GROUP BY c.customer_ref_id, c.display_name
            ORDER BY c.customer_ref_id
        """)
        return rows

    def customer(self, customer_id: str) -> dict[str, Any]:
        customer = self._one(
            "SELECT customer_ref_id, display_name FROM customer_reference WHERE customer_ref_id = ?",
            (customer_id,),
        )
        orders = self._all("""
            SELECT order_id, order_number, ordered_total, ordered_at, created_at
            FROM orders WHERE customer_ref_id = ? ORDER BY ordered_at, order_id
        """, (customer_id,))
        receipts = self._all("""
            SELECT receipt_id, business_date, location_id, register_id,
                   transaction_number, receipt_total
            FROM pos_receipt WHERE customer_ref_id = ? ORDER BY business_date, receipt_id
        """, (customer_id,))
        returns = self._all("""
            SELECT return_id, original_order_id, original_receipt_id,
                   return_merchandise_value, returned_at
            FROM merchandise_return WHERE customer_ref_id = ? ORDER BY returned_at, return_id
        """, (customer_id,))
        for row in orders:
            row["ordered_total"] = money(row["ordered_total"])
        for row in receipts:
            row["receipt_total"] = money(row["receipt_total"])
        for row in returns:
            row["return_merchandise_value"] = money(row["return_merchandise_value"])
        customer.update(orders=orders, receipts=receipts, returns=returns)
        return customer

    def order(self, order_id: str) -> dict[str, Any]:
        order = self._one("""
            SELECT order_id, customer_ref_id, order_number, ordered_total, ordered_at, created_at
            FROM orders WHERE order_id = ?
        """, (order_id,))
        order["ordered_total"] = money(order["ordered_total"])
        order["lines"] = self._all("""
            SELECT order_line_id, sku, ordered_quantity, line_merchandise_amount, line_tax_amount
            FROM order_line WHERE order_id = ? ORDER BY order_line_id
        """, (order_id,))
        for line in order["lines"]:
            line["ordered_quantity"] = str(line["ordered_quantity"])
            line["line_merchandise_amount"] = money(line["line_merchandise_amount"])
            line["line_tax_amount"] = money(line["line_tax_amount"])
            line["fulfillment_events"] = self._all("""
                SELECT fulfillment_event_id, fulfilled_quantity, occurred_at
                FROM fulfillment_event WHERE order_line_id = ? ORDER BY occurred_at, fulfillment_event_id
            """, (line["order_line_id"],))
            for event in line["fulfillment_events"]:
                event["fulfilled_quantity"] = str(event["fulfilled_quantity"])
        order["payments"] = self._all(
            "SELECT payment_id, payment_amount FROM payment WHERE order_id = ? ORDER BY payment_id",
            (order_id,),
        )
        for payment in order["payments"]:
            payment["payment_amount"] = money(payment["payment_amount"])
            payment["authorizations"] = self._all("""
                SELECT authorization_id, authorization_amount, authorization_status, authorized_at
                FROM payment_authorization WHERE payment_id = ? ORDER BY authorized_at, authorization_id
            """, (payment["payment_id"],))
            payment["settlements"] = self._all("""
                SELECT settlement_id, settlement_amount, settlement_type, settled_at
                FROM payment_settlement WHERE payment_id = ? ORDER BY settled_at, settlement_id
            """, (payment["payment_id"],))
            for authorization in payment["authorizations"]:
                authorization["authorization_amount"] = money(authorization["authorization_amount"])
            for settlement in payment["settlements"]:
                settlement["settlement_amount"] = money(settlement["settlement_amount"])
        return order

    def receipt(self, receipt_id: str) -> dict[str, Any]:
        receipt = self._one("""
            SELECT receipt_id, customer_ref_id, business_date, location_id, register_id,
                   transaction_number, receipt_total FROM pos_receipt WHERE receipt_id = ?
        """, (receipt_id,))
        receipt["receipt_total"] = money(receipt["receipt_total"])
        receipt["items"] = self._all("""
            SELECT receipt_item_id, sku, quantity, item_amount
            FROM pos_item_occurrence WHERE receipt_id = ? ORDER BY receipt_item_id
        """, (receipt_id,))
        receipt["tenders"] = self._all("""
            SELECT tender_leg_id, tender_type, tender_amount
            FROM pos_tender_leg WHERE receipt_id = ? ORDER BY tender_leg_id
        """, (receipt_id,))
        for item in receipt["items"]:
            item["quantity"] = str(item["quantity"])
            item["item_amount"] = money(item["item_amount"])
        for tender in receipt["tenders"]:
            tender["tender_amount"] = money(tender["tender_amount"])
        return receipt

    def returns(self, customer_id: str) -> list[dict[str, Any]]:
        self._one("SELECT customer_ref_id FROM customer_reference WHERE customer_ref_id = ?", (customer_id,))
        rows = self._all("""
            SELECT return_id, original_order_id, original_receipt_id,
                   return_merchandise_value, returned_at
            FROM merchandise_return WHERE customer_ref_id = ? ORDER BY returned_at, return_id
        """, (customer_id,))
        for row in rows:
            row["return_merchandise_value"] = money(row["return_merchandise_value"])
            row["refunds"] = self._all("""
                SELECT refund_id, refund_amount, refunded_at
                FROM refund WHERE return_id = ? ORDER BY refunded_at, refund_id
            """, (row["return_id"],))
            for refund in row["refunds"]:
                refund["refund_amount"] = money(refund["refund_amount"])
        return rows

    def timeline(self, customer_id: str) -> list[dict[str, Any]]:
        self._one("SELECT customer_ref_id FROM customer_reference WHERE customer_ref_id = ?", (customer_id,))
        rows = self._all("""
            SELECT occurred_at, event_type, entity_id, amount, detail FROM (
              SELECT o.ordered_at occurred_at, 'order_placed' event_type, o.order_id entity_id,
                     o.ordered_total amount, o.order_number detail
              FROM orders o WHERE o.customer_ref_id = ?
              UNION ALL
              SELECT a.authorized_at, 'payment_authorization', a.authorization_id,
                     a.authorization_amount, a.authorization_status
              FROM payment_authorization a JOIN payment p ON p.payment_id=a.payment_id
              JOIN orders o ON o.order_id=p.order_id WHERE o.customer_ref_id = ?
              UNION ALL
              SELECT s.settled_at, 'payment_settlement', s.settlement_id,
                     s.settlement_amount, s.settlement_type
              FROM payment_settlement s JOIN payment p ON p.payment_id=s.payment_id
              JOIN orders o ON o.order_id=p.order_id WHERE o.customer_ref_id = ?
              UNION ALL
              SELECT f.occurred_at, 'fulfillment', f.fulfillment_event_id, NULL,
                     ol.sku || ' quantity ' || f.fulfilled_quantity
              FROM fulfillment_event f JOIN order_line ol ON ol.order_line_id=f.order_line_id
              JOIN orders o ON o.order_id=ol.order_id WHERE o.customer_ref_id = ?
              UNION ALL
              SELECT r.business_date || ' 00:00:00', 'pos_receipt', r.receipt_id,
                     r.receipt_total, r.location_id || '/' || r.register_id || '/' || r.transaction_number
              FROM pos_receipt r WHERE r.customer_ref_id = ?
              UNION ALL
              SELECT mr.returned_at, 'merchandise_return', mr.return_id,
                     mr.return_merchandise_value, COALESCE(mr.original_order_id, mr.original_receipt_id)
              FROM merchandise_return mr WHERE mr.customer_ref_id = ?
              UNION ALL
              SELECT rf.refunded_at, 'refund', rf.refund_id, rf.refund_amount, rf.return_id
              FROM refund rf JOIN merchandise_return mr ON mr.return_id=rf.return_id
              WHERE mr.customer_ref_id = ?
            ) ORDER BY occurred_at, event_type, entity_id
        """, (customer_id,) * 7)
        for row in rows:
            if row["amount"] is not None:
                row["amount"] = money(row["amount"])
        return rows

    def activity(self, customer_id: str) -> dict[str, Any]:
        result = self.customer(customer_id)
        result["orders"] = [self.order(row["order_id"]) for row in result["orders"]]
        result["receipts"] = [self.receipt(row["receipt_id"]) for row in result["receipts"]]
        result["returns"] = self.returns(customer_id)
        result["timeline"] = self.timeline(customer_id)
        return result
