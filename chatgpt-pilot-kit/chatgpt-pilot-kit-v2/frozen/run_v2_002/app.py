"""Deterministic, dependency-free commerce investigation API."""

from __future__ import annotations

import argparse
import json
import sqlite3
from dataclasses import dataclass
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent


class NotFoundError(LookupError):
    pass


def amount(value: Any, semantic: str, source_type: str, source_id: str, field: str) -> dict[str, str]:
    """Represent money without binary floating point and with source lineage."""
    return {
        "value": format(Decimal(str(value)), ".2f"),
        "currency": "UNKNOWN",
        "semantic": semantic,
        "source_type": source_type,
        "source_id": source_id,
        "source_field": field,
    }


def quantity(value: Any) -> str:
    return format(Decimal(str(value)), ".3f")


def timestamp(value: Any, semantic: str) -> dict[str, str]:
    return {"value": str(value), "semantic": semantic}


def one(conn: sqlite3.Connection, sql: str, args: tuple[Any, ...]) -> sqlite3.Row:
    row = conn.execute(sql, args).fetchone()
    if row is None:
        raise NotFoundError(args[0])
    return row


@dataclass
class CommerceRepository:
    conn: sqlite3.Connection

    @classmethod
    def from_fixtures(cls) -> "CommerceRepository":
        conn = sqlite3.connect(":memory:", check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.executescript((ROOT / "schema.sql").read_text(encoding="utf-8"))
        conn.executescript((ROOT / "seed.sql").read_text(encoding="utf-8"))
        return cls(conn)

    def customer(self, customer_id: str) -> dict[str, Any]:
        c = one(self.conn, "SELECT * FROM customer_reference WHERE customer_ref_id=?", (customer_id,))
        orders = self.conn.execute("SELECT order_id FROM orders WHERE customer_ref_id=? ORDER BY ordered_at, order_id", (customer_id,))
        receipts = self.conn.execute("SELECT receipt_id FROM pos_receipt WHERE customer_ref_id=? ORDER BY business_date, receipt_id", (customer_id,))
        returns = self.conn.execute("SELECT return_id FROM merchandise_return WHERE customer_ref_id=? ORDER BY returned_at, return_id", (customer_id,))
        return {
            "grain": "one customer_reference row",
            "customer_ref_id": c["customer_ref_id"],
            "display_name": c["display_name"],
            "order_ids": [r[0] for r in orders],
            "receipt_ids": [r[0] for r in receipts],
            "return_ids": [r[0] for r in returns],
        }

    def order(self, order_id: str) -> dict[str, Any]:
        o = one(self.conn, "SELECT * FROM orders WHERE order_id=?", (order_id,))
        lines = []
        for r in self.conn.execute("SELECT * FROM order_line WHERE order_id=? ORDER BY order_line_id", (order_id,)):
            events = [{
                "grain": "one fulfillment_event row", "fulfillment_event_id": e["fulfillment_event_id"],
                "fulfilled_quantity": quantity(e["fulfilled_quantity"]),
                "occurred_at": timestamp(e["occurred_at"], "fulfillment occurred_at"),
                "order_line_id": r["order_line_id"],
            } for e in self.conn.execute("SELECT * FROM fulfillment_event WHERE order_line_id=? ORDER BY occurred_at, fulfillment_event_id", (r["order_line_id"],))]
            lines.append({
                "grain": "one order_line row", "order_line_id": r["order_line_id"], "order_id": order_id,
                "sku": r["sku"], "ordered_quantity": quantity(r["ordered_quantity"]),
                "merchandise_amount": amount(r["line_merchandise_amount"], "order-line merchandise", "order_line", r["order_line_id"], "line_merchandise_amount"),
                "tax_amount": amount(r["line_tax_amount"], "order-line tax", "order_line", r["order_line_id"], "line_tax_amount"),
                "fulfillment_events": events,
            })
        payments = [self.payment(r[0]) for r in self.conn.execute("SELECT payment_id FROM payment WHERE order_id=? ORDER BY payment_id", (order_id,))]
        return {
            "grain": "one orders row with bounded independent child collections", "order_id": o["order_id"],
            "order_number": o["order_number"], "customer_ref_id": o["customer_ref_id"],
            "ordered_total": amount(o["ordered_total"], "order total", "orders", order_id, "ordered_total"),
            "ordered_at": timestamp(o["ordered_at"], "order ordered_at"),
            "created_at": timestamp(o["created_at"], "order created_at"),
            "lines": lines, "payments": payments,
        }

    def payment(self, payment_id: str) -> dict[str, Any]:
        p = one(self.conn, "SELECT * FROM payment WHERE payment_id=?", (payment_id,))
        auths = [{
            "grain": "one payment_authorization row", "authorization_id": r["authorization_id"],
            "payment_id": payment_id, "status": r["authorization_status"],
            "authorization_amount": amount(r["authorization_amount"], "authorization attempt", "payment_authorization", r["authorization_id"], "authorization_amount"),
            "authorized_at": timestamp(r["authorized_at"], "authorization authorized_at"),
        } for r in self.conn.execute("SELECT * FROM payment_authorization WHERE payment_id=? ORDER BY authorized_at, authorization_id", (payment_id,))]
        settlements = [{
            "grain": "one payment_settlement row", "settlement_id": r["settlement_id"],
            "payment_id": payment_id, "settlement_type": r["settlement_type"],
            "settlement_amount": amount(r["settlement_amount"], "payment settlement", "payment_settlement", r["settlement_id"], "settlement_amount"),
            "settled_at": timestamp(r["settled_at"], "settlement settled_at"),
        } for r in self.conn.execute("SELECT * FROM payment_settlement WHERE payment_id=? ORDER BY settled_at, settlement_id", (payment_id,))]
        return {
            "grain": "one payment row with bounded event collections", "payment_id": payment_id, "order_id": p["order_id"],
            "payment_amount": amount(p["payment_amount"], "payment stated amount", "payment", payment_id, "payment_amount"),
            "authorizations": auths, "settlements": settlements,
        }

    def receipt(self, receipt_id: str) -> dict[str, Any]:
        r = one(self.conn, "SELECT * FROM pos_receipt WHERE receipt_id=?", (receipt_id,))
        items = [{
            "grain": "one pos_item_occurrence row", "receipt_item_id": i["receipt_item_id"], "receipt_id": receipt_id,
            "sku": i["sku"], "quantity": quantity(i["quantity"]),
            "item_amount": amount(i["item_amount"], "POS item occurrence", "pos_item_occurrence", i["receipt_item_id"], "item_amount"),
        } for i in self.conn.execute("SELECT * FROM pos_item_occurrence WHERE receipt_id=? ORDER BY receipt_item_id", (receipt_id,))]
        tenders = [{
            "grain": "one pos_tender_leg row", "tender_leg_id": t["tender_leg_id"], "receipt_id": receipt_id,
            "tender_type": t["tender_type"],
            "tender_amount": amount(t["tender_amount"], "POS tender leg", "pos_tender_leg", t["tender_leg_id"], "tender_amount"),
        } for t in self.conn.execute("SELECT * FROM pos_tender_leg WHERE receipt_id=? ORDER BY tender_leg_id", (receipt_id,))]
        return {
            "grain": "one pos_receipt row with bounded independent child collections", "receipt_id": receipt_id,
            "customer_ref_id": r["customer_ref_id"], "business_date": {"value": r["business_date"], "semantic": "POS business_date"},
            "location_id": r["location_id"], "register_id": r["register_id"], "transaction_number": r["transaction_number"],
            "receipt_total": amount(r["receipt_total"], "POS receipt total", "pos_receipt", receipt_id, "receipt_total"),
            "items": items, "tenders": tenders,
        }

    def receipts(self, customer_id: str | None = None, sku: str | None = None, tender_type: str | None = None) -> list[dict[str, Any]]:
        sql = "SELECT DISTINCT r.receipt_id FROM pos_receipt r"
        args: list[str] = []
        where = []
        if sku:
            sql += " JOIN pos_item_occurrence i ON i.receipt_id=r.receipt_id"
            where.append("i.sku=?"); args.append(sku)
        if tender_type:
            sql += " JOIN pos_tender_leg t ON t.receipt_id=r.receipt_id"
            where.append("t.tender_type=?"); args.append(tender_type)
        if customer_id:
            where.append("r.customer_ref_id=?"); args.append(customer_id)
        if where: sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY r.receipt_id"
        return [self.receipt(row[0]) for row in self.conn.execute(sql, args)]

    def returns_for_customer(self, customer_id: str) -> list[dict[str, Any]]:
        one(self.conn, "SELECT * FROM customer_reference WHERE customer_ref_id=?", (customer_id,))
        result = []
        for r in self.conn.execute("SELECT * FROM merchandise_return WHERE customer_ref_id=? ORDER BY returned_at, return_id", (customer_id,)):
            refunds = [{
                "grain": "one refund row", "refund_id": f["refund_id"], "return_id": r["return_id"],
                "refund_amount": amount(f["refund_amount"], "refund event", "refund", f["refund_id"], "refund_amount"),
                "refunded_at": timestamp(f["refunded_at"], "refund refunded_at"),
            } for f in self.conn.execute("SELECT * FROM refund WHERE return_id=? ORDER BY refunded_at, refund_id", (r["return_id"],))]
            result.append({
                "grain": "one merchandise_return row with bounded refund collection", "return_id": r["return_id"],
                "customer_ref_id": r["customer_ref_id"], "original_order_id": r["original_order_id"],
                "original_receipt_id": r["original_receipt_id"],
                "return_merchandise_value": amount(r["return_merchandise_value"], "returned merchandise value", "merchandise_return", r["return_id"], "return_merchandise_value"),
                "returned_at": timestamp(r["returned_at"], "return returned_at"), "refunds": refunds,
            })
        return result

    def timeline(self, customer_id: str) -> list[dict[str, Any]]:
        self.customer(customer_id)
        events: list[dict[str, Any]] = []
        def add(kind: str, source_type: str, source_id: str, at: Any, semantic: str, monetary: dict[str, str] | None = None, **refs: Any) -> None:
            event = {"grain": "one typed timeline event", "event_type": kind, "source_type": source_type,
                     "source_id": source_id, "occurred_at": timestamp(at, semantic), **refs}
            if monetary: event["amount"] = monetary
            events.append(event)
        for o in self.conn.execute("SELECT * FROM orders WHERE customer_ref_id=?", (customer_id,)):
            add("ORDER_PLACED", "orders", o["order_id"], o["ordered_at"], "order ordered_at", amount(o["ordered_total"], "order total", "orders", o["order_id"], "ordered_total"), order_id=o["order_id"])
            for a in self.conn.execute("SELECT a.* FROM payment_authorization a JOIN payment p ON p.payment_id=a.payment_id WHERE p.order_id=?", (o["order_id"],)):
                add("PAYMENT_AUTHORIZATION", "payment_authorization", a["authorization_id"], a["authorized_at"], "authorization authorized_at", amount(a["authorization_amount"], "authorization attempt", "payment_authorization", a["authorization_id"], "authorization_amount"), payment_id=a["payment_id"], status=a["authorization_status"])
            for s in self.conn.execute("SELECT s.* FROM payment_settlement s JOIN payment p ON p.payment_id=s.payment_id WHERE p.order_id=?", (o["order_id"],)):
                add("PAYMENT_SETTLEMENT", "payment_settlement", s["settlement_id"], s["settled_at"], "settlement settled_at", amount(s["settlement_amount"], "payment settlement", "payment_settlement", s["settlement_id"], "settlement_amount"), payment_id=s["payment_id"], settlement_type=s["settlement_type"])
            for f in self.conn.execute("SELECT f.*, l.order_line_id FROM fulfillment_event f JOIN order_line l ON l.order_line_id=f.order_line_id WHERE l.order_id=?", (o["order_id"],)):
                add("FULFILLMENT", "fulfillment_event", f["fulfillment_event_id"], f["occurred_at"], "fulfillment occurred_at", order_line_id=f["order_line_id"], fulfilled_quantity=quantity(f["fulfilled_quantity"]))
        for r in self.conn.execute("SELECT * FROM merchandise_return WHERE customer_ref_id=?", (customer_id,)):
            add("MERCHANDISE_RETURN", "merchandise_return", r["return_id"], r["returned_at"], "return returned_at", amount(r["return_merchandise_value"], "returned merchandise value", "merchandise_return", r["return_id"], "return_merchandise_value"), original_order_id=r["original_order_id"], original_receipt_id=r["original_receipt_id"])
            for f in self.conn.execute("SELECT * FROM refund WHERE return_id=?", (r["return_id"],)):
                add("REFUND", "refund", f["refund_id"], f["refunded_at"], "refund refunded_at", amount(f["refund_amount"], "refund event", "refund", f["refund_id"], "refund_amount"), return_id=r["return_id"])
        return sorted(events, key=lambda e: (e["occurred_at"]["value"], e["source_type"], e["source_id"]))


class ApiHandler(BaseHTTPRequestHandler):
    repository: CommerceRepository

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        parts = [p for p in parsed.path.split("/") if p]
        query = parse_qs(parsed.query)
        try:
            if parts == ["health"]:
                body: Any = {"status": "ok"}
            elif len(parts) == 2 and parts[0] == "customers": body = self.repository.customer(parts[1])
            elif len(parts) == 3 and parts[0] == "customers" and parts[2] == "timeline": body = self.repository.timeline(parts[1])
            elif len(parts) == 3 and parts[0] == "customers" and parts[2] == "returns": body = self.repository.returns_for_customer(parts[1])
            elif len(parts) == 2 and parts[0] == "orders": body = self.repository.order(parts[1])
            elif len(parts) == 2 and parts[0] == "payments": body = self.repository.payment(parts[1])
            elif len(parts) == 2 and parts[0] == "receipts": body = self.repository.receipt(parts[1])
            elif parts == ["receipts"]:
                body = self.repository.receipts(*(query.get(k, [None])[0] for k in ("customer_id", "sku", "tender_type")))
            else: raise NotFoundError(parsed.path)
            self._send(200, body)
        except NotFoundError as exc: self._send(404, {"error": "not found", "identifier": str(exc)})

    def _send(self, status: int, body: Any) -> None:
        data = json.dumps(body, separators=(",", ":")).encode()
        self.send_response(status); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)

    def log_message(self, format: str, *args: Any) -> None:
        return


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1"); parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(); ApiHandler.repository = CommerceRepository.from_fixtures()
    print(f"Serving on http://{args.host}:{args.port}")
    ThreadingHTTPServer((args.host, args.port), ApiHandler).serve_forever()


if __name__ == "__main__":
    main()
