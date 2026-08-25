"""SQLite data-access layer for the commerce investigation API."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


PACKAGE_DIR = Path(__file__).resolve().parent


def money(value: Any) -> str | None:
    """Return a database monetary value in an API-safe, fixed precision form."""
    return None if value is None else f"{float(value):.2f}"


def quantity(value: Any) -> str | None:
    return None if value is None else f"{float(value):.3f}"


class NotFoundError(LookupError):
    pass


class CommerceRepository:
    """Queries the supplied relational model without changing its schema or data."""

    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection
        self.connection.row_factory = sqlite3.Row

    @classmethod
    def from_fixtures(cls) -> "CommerceRepository":
        connection = sqlite3.connect(":memory:", check_same_thread=False)
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript((PACKAGE_DIR / "schema.sql").read_text(encoding="utf-8"))
        connection.executescript((PACKAGE_DIR / "seed.sql").read_text(encoding="utf-8"))
        return cls(connection)

    def _one(self, sql: str, params: tuple[Any, ...]) -> dict[str, Any] | None:
        row = self.connection.execute(sql, params).fetchone()
        return dict(row) if row else None

    def _all(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        return [dict(row) for row in self.connection.execute(sql, params).fetchall()]

    def list_customers(self) -> list[dict[str, Any]]:
        return self._all(
            """SELECT c.customer_ref_id, c.display_name,
                      COUNT(DISTINCT o.order_id) AS order_count,
                      COUNT(DISTINCT r.receipt_id) AS receipt_count
                 FROM customer_reference c
                 LEFT JOIN orders o ON o.customer_ref_id = c.customer_ref_id
                 LEFT JOIN pos_receipt r ON r.customer_ref_id = c.customer_ref_id
                GROUP BY c.customer_ref_id, c.display_name
                ORDER BY c.customer_ref_id"""
        )

    def customer(self, customer_id: str) -> dict[str, Any]:
        customer = self._one(
            "SELECT customer_ref_id, display_name FROM customer_reference WHERE customer_ref_id = ?",
            (customer_id,),
        )
        if not customer:
            raise NotFoundError(f"customer {customer_id!r} not found")
        customer["orders"] = self._all(
            """SELECT order_id, order_number, ordered_total, ordered_at, created_at
                 FROM orders WHERE customer_ref_id = ? ORDER BY ordered_at, order_id""",
            (customer_id,),
        )
        for order in customer["orders"]:
            order["ordered_total"] = money(order["ordered_total"])
        customer["receipts"] = self._all(
            """SELECT receipt_id, business_date, location_id, register_id,
                      transaction_number, receipt_total
                 FROM pos_receipt WHERE customer_ref_id = ?
                ORDER BY business_date, receipt_id""",
            (customer_id,),
        )
        for receipt in customer["receipts"]:
            receipt["receipt_total"] = money(receipt["receipt_total"])
        customer["returns"] = self._returns(customer_id)
        return customer

    def order(self, order_id: str) -> dict[str, Any]:
        order = self._one("SELECT * FROM orders WHERE order_id = ?", (order_id,))
        if not order:
            raise NotFoundError(f"order {order_id!r} not found")
        order["ordered_total"] = money(order["ordered_total"])
        order["lines"] = self._all(
            "SELECT * FROM order_line WHERE order_id = ? ORDER BY order_line_id", (order_id,)
        )
        for line in order["lines"]:
            line["ordered_quantity"] = quantity(line["ordered_quantity"])
            line["line_merchandise_amount"] = money(line["line_merchandise_amount"])
            line["line_tax_amount"] = money(line["line_tax_amount"])
            line["fulfillment_events"] = self._all(
                """SELECT fulfillment_event_id, fulfilled_quantity, occurred_at
                     FROM fulfillment_event WHERE order_line_id = ?
                     ORDER BY occurred_at, fulfillment_event_id""",
                (line["order_line_id"],),
            )
            for event in line["fulfillment_events"]:
                event["fulfilled_quantity"] = quantity(event["fulfilled_quantity"])
        order["payments"] = self._all(
            "SELECT payment_id, payment_amount FROM payment WHERE order_id = ? ORDER BY payment_id",
            (order_id,),
        )
        for payment in order["payments"]:
            payment["payment_amount"] = money(payment["payment_amount"])
            payment["authorizations"] = self._all(
                """SELECT authorization_id, authorization_amount, authorization_status, authorized_at
                     FROM payment_authorization WHERE payment_id = ?
                     ORDER BY authorized_at, authorization_id""",
                (payment["payment_id"],),
            )
            for auth in payment["authorizations"]:
                auth["authorization_amount"] = money(auth["authorization_amount"])
            payment["settlements"] = self._all(
                """SELECT settlement_id, settlement_amount, settlement_type, settled_at
                     FROM payment_settlement WHERE payment_id = ?
                     ORDER BY settled_at, settlement_id""",
                (payment["payment_id"],),
            )
            for settlement in payment["settlements"]:
                settlement["settlement_amount"] = money(settlement["settlement_amount"])
        order["returns"] = self._returns_for_order(order_id)
        return order

    def receipt(self, receipt_id: str) -> dict[str, Any]:
        receipt = self._one("SELECT * FROM pos_receipt WHERE receipt_id = ?", (receipt_id,))
        if not receipt:
            raise NotFoundError(f"receipt {receipt_id!r} not found")
        receipt["receipt_total"] = money(receipt["receipt_total"])
        receipt["items"] = self._all(
            "SELECT * FROM pos_item_occurrence WHERE receipt_id = ? ORDER BY receipt_item_id",
            (receipt_id,),
        )
        for item in receipt["items"]:
            item["quantity"] = quantity(item["quantity"])
            item["item_amount"] = money(item["item_amount"])
        receipt["tenders"] = self._all(
            "SELECT * FROM pos_tender_leg WHERE receipt_id = ? ORDER BY tender_leg_id", (receipt_id,)
        )
        for tender in receipt["tenders"]:
            tender["tender_amount"] = money(tender["tender_amount"])
        receipt["returns"] = self._returns_for_receipt(receipt_id)
        return receipt

    def _returns(self, customer_id: str) -> list[dict[str, Any]]:
        rows = self._all(
            "SELECT * FROM merchandise_return WHERE customer_ref_id = ? ORDER BY returned_at, return_id",
            (customer_id,),
        )
        return self._attach_refunds(rows)

    def _returns_for_order(self, order_id: str) -> list[dict[str, Any]]:
        return self._attach_refunds(self._all(
            "SELECT * FROM merchandise_return WHERE original_order_id = ? ORDER BY returned_at, return_id",
            (order_id,),
        ))

    def _returns_for_receipt(self, receipt_id: str) -> list[dict[str, Any]]:
        return self._attach_refunds(self._all(
            "SELECT * FROM merchandise_return WHERE original_receipt_id = ? ORDER BY returned_at, return_id",
            (receipt_id,),
        ))

    def _attach_refunds(self, returns: list[dict[str, Any]]) -> list[dict[str, Any]]:
        for returned in returns:
            returned["return_merchandise_value"] = money(returned["return_merchandise_value"])
            returned["refunds"] = self._all(
                "SELECT * FROM refund WHERE return_id = ? ORDER BY refunded_at, refund_id",
                (returned["return_id"],),
            )
            for refund in returned["refunds"]:
                refund["refund_amount"] = money(refund["refund_amount"])
        return returns

    def timeline(self, customer_id: str) -> list[dict[str, Any]]:
        # Validate first so an empty timeline cannot masquerade as an unknown customer.
        self.customer(customer_id)
        rows = self._all(
            """SELECT occurred_at, event_type, entity_id, related_id, amount, status, description
                 FROM (
                   SELECT o.ordered_at AS occurred_at, 'ORDER_PLACED' AS event_type,
                          o.order_id AS entity_id, NULL AS related_id, o.ordered_total AS amount,
                          NULL AS status, 'Order ' || o.order_number AS description
                     FROM orders o WHERE o.customer_ref_id = ?
                   UNION ALL
                   SELECT pr.business_date || ' 00:00:00', 'POS_RECEIPT', pr.receipt_id, NULL,
                          pr.receipt_total, NULL, 'POS transaction ' || pr.transaction_number
                     FROM pos_receipt pr WHERE pr.customer_ref_id = ?
                   UNION ALL
                   SELECT pa.authorized_at, 'PAYMENT_AUTHORIZATION', pa.authorization_id, p.payment_id,
                          pa.authorization_amount, pa.authorization_status, 'Payment authorization'
                     FROM payment_authorization pa JOIN payment p ON p.payment_id = pa.payment_id
                     JOIN orders o ON o.order_id = p.order_id WHERE o.customer_ref_id = ?
                   UNION ALL
                   SELECT ps.settled_at, 'PAYMENT_SETTLEMENT', ps.settlement_id, p.payment_id,
                          ps.settlement_amount, ps.settlement_type, 'Payment settlement'
                     FROM payment_settlement ps JOIN payment p ON p.payment_id = ps.payment_id
                     JOIN orders o ON o.order_id = p.order_id WHERE o.customer_ref_id = ?
                   UNION ALL
                   SELECT fe.occurred_at, 'FULFILLMENT', fe.fulfillment_event_id, ol.order_line_id,
                          NULL, NULL, 'Fulfilled quantity ' || printf('%.3f', fe.fulfilled_quantity)
                     FROM fulfillment_event fe JOIN order_line ol ON ol.order_line_id = fe.order_line_id
                     JOIN orders o ON o.order_id = ol.order_id WHERE o.customer_ref_id = ?
                   UNION ALL
                   SELECT mr.returned_at, 'RETURN', mr.return_id,
                          COALESCE(mr.original_order_id, mr.original_receipt_id),
                          mr.return_merchandise_value, NULL, 'Merchandise return'
                     FROM merchandise_return mr WHERE mr.customer_ref_id = ?
                   UNION ALL
                   SELECT rf.refunded_at, 'REFUND', rf.refund_id, rf.return_id,
                          rf.refund_amount, NULL, 'Refund issued'
                     FROM refund rf JOIN merchandise_return mr ON mr.return_id = rf.return_id
                    WHERE mr.customer_ref_id = ?
                 ) events ORDER BY occurred_at, event_type, entity_id""",
            (customer_id,) * 7,
        )
        for row in rows:
            row["amount"] = money(row["amount"])
        return rows
