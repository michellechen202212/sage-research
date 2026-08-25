"""Investigation read service over the supplied immutable SQLite inputs."""

from __future__ import annotations

import json
import sqlite3
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parent


def build_database(path: str | Path = ":memory:") -> sqlite3.Connection:
    """Create a clean database from the supplied schema and fixtures."""
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.executescript((ROOT / "schema.sql").read_text(encoding="utf-8"))
    connection.executescript((ROOT / "seed.sql").read_text(encoding="utf-8"))
    return connection


def _money(cents: int, currency_code: str | None) -> dict[str, Any]:
    return {
        "amount_cents": cents,
        "amount": format(Decimal(cents) / Decimal(100), ".2f"),
        "currency_code": currency_code,
    }


def _rows(connection: sqlite3.Connection, sql: str, parameters: Iterable[Any] = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in connection.execute(sql, tuple(parameters))]


def _one(connection: sqlite3.Connection, sql: str, parameters: Iterable[Any]) -> dict[str, Any] | None:
    row = connection.execute(sql, tuple(parameters)).fetchone()
    return dict(row) if row else None


def _not_found(entity: str, identifier: str) -> dict[str, Any]:
    return {"error": "not_found", "entity": entity, "identifier": identifier}


class InvestigationService:
    def __init__(self, connection: sqlite3.Connection):
        self.db = connection
        self.db.row_factory = sqlite3.Row

    def order(self, order_id: str) -> dict[str, Any]:
        order = _one(self.db, "SELECT * FROM commerce_order WHERE order_id = ?", (order_id,))
        if not order:
            return _not_found("order", order_id)
        order["total"] = _money(order.pop("order_total_cents"), order["currency_code"])
        lines = _rows(self.db, "SELECT * FROM order_line WHERE order_id = ? ORDER BY order_line_id", (order_id,))
        for line in lines:
            line["amount"] = _money(line.pop("line_amount_cents"), order["currency_code"])
            events = _rows(self.db, "SELECT * FROM fulfillment_event WHERE order_line_id = ? ORDER BY event_at, fulfillment_event_id", (line["order_line_id"],))
            for event in events:
                event["amount"] = _money(event.pop("amount_cents"), order["currency_code"])
            line["fulfillment_events"] = events
        order["lines"] = lines
        order["payments"] = [self.payment(row["payment_id"]) for row in _rows(self.db, "SELECT payment_id FROM payment WHERE order_id = ? ORDER BY payment_id", (order_id,))]
        return order

    def payment(self, payment_id: str) -> dict[str, Any]:
        payment = _one(self.db, "SELECT * FROM payment WHERE payment_id = ?", (payment_id,))
        if not payment:
            return _not_found("payment", payment_id)
        events = _rows(self.db, "SELECT * FROM payment_event WHERE payment_id = ? ORDER BY event_at, event_id", (payment_id,))
        for event in events:
            event["amount"] = _money(event.pop("amount_cents"), event.pop("currency_code"))
        payment["events"] = events
        return payment

    def receipt(self, receipt_id: str) -> dict[str, Any]:
        receipt = _one(self.db, "SELECT * FROM pos_receipt WHERE receipt_id = ?", (receipt_id,))
        if not receipt:
            return _not_found("receipt", receipt_id)
        currency = receipt["currency_code"]
        receipt["total"] = _money(receipt.pop("receipt_total_cents"), currency)
        receipt["items"] = _rows(self.db, "SELECT * FROM receipt_item_occurrence WHERE receipt_id = ? ORDER BY receipt_item_id", (receipt_id,))
        receipt["tender_legs"] = _rows(self.db, "SELECT * FROM tender_leg WHERE receipt_id = ? ORDER BY tender_leg_id", (receipt_id,))
        for item in receipt["items"]:
            item["amount"] = _money(item.pop("item_amount_cents"), currency)
        for leg in receipt["tender_legs"]:
            leg["amount"] = _money(leg.pop("amount_cents"), currency)
        return receipt

    def customer(self, customer_id: str) -> dict[str, Any]:
        customer = _one(self.db, "SELECT * FROM customer WHERE customer_id = ?", (customer_id,))
        if not customer:
            return _not_found("customer", customer_id)
        customer["orders"] = [self.order(r["order_id"]) for r in _rows(self.db, "SELECT order_id FROM commerce_order WHERE customer_id = ? ORDER BY ordered_at, order_id", (customer_id,))]
        customer["payments"] = [self.payment(r["payment_id"]) for r in _rows(self.db, "SELECT payment_id FROM payment WHERE customer_id = ? ORDER BY payment_id", (customer_id,))]
        customer["receipts"] = [self.receipt(r["receipt_id"]) for r in _rows(self.db, "SELECT receipt_id FROM pos_receipt WHERE customer_id = ? ORDER BY transacted_at, receipt_id", (customer_id,))]
        returns = _rows(self.db, "SELECT * FROM merchandise_return WHERE customer_id = ? ORDER BY returned_at, return_id", (customer_id,))
        for returned in returns:
            returned["value"] = _money(returned.pop("merchandise_value_cents"), returned.pop("currency_code"))
        customer["returns"] = returns
        customer["payment_refund_facts"] = self._payment_refund_facts(customer_id)
        customer["timeline"] = self._timeline(customer_id)
        return customer

    def _payment_refund_facts(self, customer_id: str) -> dict[str, Any]:
        facts = _rows(self.db, """SELECT pe.event_id, pe.payment_id, pe.event_type, pe.status,
            pe.amount_cents, pe.currency_code, pe.event_at
            FROM payment_event pe JOIN payment p ON p.payment_id = pe.payment_id
            WHERE p.customer_id = ? ORDER BY pe.event_at, pe.event_id""", (customer_id,))
        for fact in facts:
            fact["amount"] = _money(fact.pop("amount_cents"), fact.pop("currency_code"))
        totals: list[dict[str, Any]] = []
        sql = """SELECT pe.event_type, pe.status, pe.currency_code, SUM(pe.amount_cents) amount_cents
            FROM payment_event pe JOIN payment p ON p.payment_id = pe.payment_id
            WHERE p.customer_id = ? AND pe.event_type IN ('CAPTURE','REFUND')
            GROUP BY pe.event_type, pe.status, pe.currency_code
            ORDER BY pe.event_type, pe.status, pe.currency_code"""
        for row in _rows(self.db, sql, (customer_id,)):
            row["amount"] = _money(row.pop("amount_cents"), row.pop("currency_code"))
            totals.append(row)
        return {
            "events": facts,
            "derived_totals": totals,
            "metric_semantics": "Sum amount_cents by customer, event_type, status, and source currency. Includes CAPTURE and REFUND events only; both are unsigned gross values and are not netted. AUTH is excluded.",
        }

    def _timeline(self, customer_id: str) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        sources = [
            ("order", "SELECT order_id id, ordered_at timestamp FROM commerce_order WHERE customer_id = ?"),
            ("payment_event", "SELECT pe.event_id id, pe.event_at timestamp FROM payment_event pe JOIN payment p ON p.payment_id=pe.payment_id WHERE p.customer_id = ?"),
            ("receipt", "SELECT receipt_id id, transacted_at timestamp FROM pos_receipt WHERE customer_id = ?"),
            ("return", "SELECT return_id id, returned_at timestamp FROM merchandise_return WHERE customer_id = ?"),
            ("fulfillment_event", "SELECT fe.fulfillment_event_id id, fe.event_at timestamp FROM fulfillment_event fe JOIN order_line ol ON ol.order_line_id=fe.order_line_id JOIN commerce_order o ON o.order_id=ol.order_id WHERE o.customer_id = ?"),
        ]
        for event_type, sql in sources:
            for row in _rows(self.db, sql, (customer_id,)):
                events.append({"type": event_type, **row})
        return sorted(events, key=lambda event: (event["timestamp"], event["type"], event["id"]))

    def compact(self, **filters: str) -> dict[str, Any]:
        allowed = {"customer_id", "fact_type", "order_id", "sku", "from_at", "to_at"}
        unknown = sorted(set(filters) - allowed)
        if unknown:
            return {"error": "invalid_filter", "filters": unknown}
        rows = self._compact_rows()
        def keep(row: dict[str, Any]) -> bool:
            if filters.get("customer_id") and row.get("customer_id") != filters["customer_id"]: return False
            if filters.get("fact_type") and row["fact_type"] != filters["fact_type"]: return False
            if filters.get("order_id") and row.get("order_id") != filters["order_id"]: return False
            if filters.get("sku") and row.get("sku") != filters["sku"]: return False
            if filters.get("from_at") and (not row.get("timestamp") or row["timestamp"] < filters["from_at"]): return False
            if filters.get("to_at") and (not row.get("timestamp") or row["timestamp"] > filters["to_at"]): return False
            return True
        selected = [row for row in rows if keep(row)]
        return {"grain": "one source fact occurrence per row; fact_type declares its grain", "filters": filters, "count": len(selected), "rows": selected}

    def _compact_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        specs = [
            ("order", "order_id", """SELECT o.order_id source_id,o.customer_id,o.order_id,NULL sku,o.ordered_at timestamp,o.order_total_cents amount_cents,o.currency_code,json_object('order_number',o.order_number,'channel',o.channel) attributes FROM commerce_order o"""),
            ("order_line", "order_line_id", """SELECT l.order_line_id source_id,o.customer_id,l.order_id,l.sku,NULL timestamp,l.line_amount_cents amount_cents,o.currency_code,json_object('quantity',l.quantity) attributes FROM order_line l JOIN commerce_order o ON o.order_id=l.order_id"""),
            ("fulfillment_event", "fulfillment_event_id", """SELECT f.fulfillment_event_id source_id,o.customer_id,l.order_id,l.sku,f.event_at timestamp,f.amount_cents,o.currency_code,json_object('order_line_id',l.order_line_id,'event_type',f.event_type) attributes FROM fulfillment_event f JOIN order_line l ON l.order_line_id=f.order_line_id JOIN commerce_order o ON o.order_id=l.order_id"""),
            ("payment_event", "event_id", """SELECT e.event_id source_id,p.customer_id,p.order_id,NULL sku,e.event_at timestamp,e.amount_cents,e.currency_code,json_object('payment_id',p.payment_id,'event_type',e.event_type,'status',e.status,'ingested_at',e.ingested_at) attributes FROM payment_event e JOIN payment p ON p.payment_id=e.payment_id"""),
            ("receipt", "receipt_id", """SELECT r.receipt_id source_id,r.customer_id,NULL order_id,NULL sku,r.transacted_at timestamp,r.receipt_total_cents amount_cents,r.currency_code,json_object('receipt_number',r.receipt_number,'store_code',r.store_code) attributes FROM pos_receipt r"""),
            ("receipt_item", "receipt_item_id", """SELECT i.receipt_item_id source_id,r.customer_id,NULL order_id,i.sku,r.transacted_at timestamp,i.item_amount_cents amount_cents,r.currency_code,json_object('receipt_id',r.receipt_id,'quantity',i.quantity) attributes FROM receipt_item_occurrence i JOIN pos_receipt r ON r.receipt_id=i.receipt_id"""),
            ("tender_leg", "tender_leg_id", """SELECT t.tender_leg_id source_id,r.customer_id,NULL order_id,NULL sku,r.transacted_at timestamp,t.amount_cents,r.currency_code,json_object('receipt_id',r.receipt_id,'tender_type',t.tender_type) attributes FROM tender_leg t JOIN pos_receipt r ON r.receipt_id=t.receipt_id"""),
            ("return", "return_id", """SELECT m.return_id source_id,m.customer_id,m.original_order_id order_id,NULL sku,m.returned_at timestamp,m.merchandise_value_cents amount_cents,m.currency_code,json_object() attributes FROM merchandise_return m"""),
        ]
        for fact_type, _identity, sql in specs:
            for row in _rows(self.db, sql):
                row["fact_type"] = fact_type
                row["attributes"] = json.loads(row["attributes"])
                row["amount"] = _money(row.pop("amount_cents"), row.pop("currency_code"))
                rows.append(row)
        return sorted(rows, key=lambda r: (r["fact_type"], r["source_id"]))
