import sqlite3
import unittest

from investigation_service import InvestigationService, NotFoundError, build_connection


class InvestigationServiceTests(unittest.TestCase):
    def setUp(self):
        self.db = build_connection()
        self.service = InvestigationService(self.db)

    def tearDown(self):
        self.db.close()

    def test_entity_details_and_missing(self):
        self.assertEqual(self.service.get_order("O1001")["order_total"]["decimal"], "120.00")
        self.assertEqual(len(self.service.get_payment("P1")["events"]), 5)
        self.assertEqual(len(self.service.get_receipt("R1")["tender_legs"]), 3)
        for getter in (self.service.get_order, self.service.get_payment, self.service.get_receipt):
            with self.assertRaises(NotFoundError):
                getter("missing")

    def test_customer_sections_and_timeline(self):
        view = self.service.get_customer("C1")
        self.assertEqual(set(view), {"customer", "orders", "payments", "receipts", "returns", "payment_refund_facts", "timeline"})
        self.assertTrue(all(view[name] for name in ("orders", "payments", "receipts", "returns", "timeline")))
        timestamps = [entry["timestamp"] for entry in view["timeline"]]
        self.assertEqual(timestamps, sorted(timestamps))
        self.assertTrue(all(entry.get("type") and entry.get("timestamp") for entry in view["timeline"]))
        with self.assertRaises(NotFoundError):
            self.service.get_customer("missing")

    def test_every_projection_filter_and_ordering(self):
        cases = {
            "customer_id": "C1", "record_type": "return", "order_id": "O1002",
            "sku": "SKU-C", "from_at": "2026-01-15T00:00:00Z", "to_at": "2026-01-10T09:03:00Z",
        }
        for name, value in cases.items():
            with self.subTest(name=name):
                result = self.service.compact_projection(**{name: value})
                self.assertGreater(result["count"], 0)
        first = self.service.compact_projection()
        second = self.service.compact_projection()
        self.assertEqual(first, second)
        keys = [(r["timestamp"], r["record_type"], r["record_id"]) for r in first["records"]]
        self.assertEqual(keys, sorted(keys))
        with self.assertRaises(ValueError):
            self.service.compact_projection(nope="x")

    def test_fixture_reconciliation(self):
        expected = {
            "commerce_order": 2, "order_line": 4, "fulfillment_event": 4, "payment": 1,
            "payment_event": 5, "pos_receipt": 1, "receipt_item_occurrence": 3,
            "tender_leg": 3, "merchandise_return": 1,
        }
        for table, count in expected.items():
            self.assertEqual(self.db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0], count)
        records = self.service.compact_projection()["records"]
        projected_counts = {
            kind: sum(r["record_type"] == kind for r in records)
            for kind in ("order", "order_line", "fulfillment_event", "payment_event", "receipt_item", "tender_leg", "return")
        }
        self.assertEqual(projected_counts, {"order": 2, "order_line": 4, "fulfillment_event": 4, "payment_event": 5, "receipt_item": 3, "tender_leg": 3, "return": 1})
        for kind, table, column in (
            ("order", "commerce_order", "order_total_cents"),
            ("order_line", "order_line", "line_amount_cents"),
            ("fulfillment_event", "fulfillment_event", "amount_cents"),
            ("payment_event", "payment_event", "amount_cents"),
            ("receipt_item", "receipt_item_occurrence", "item_amount_cents"),
            ("tender_leg", "tender_leg", "amount_cents"),
            ("return", "merchandise_return", "merchandise_value_cents"),
        ):
            source = self.db.execute(f"SELECT SUM({column}) FROM {table}").fetchone()[0]
            projected = sum(r["amount"]["cents"] for r in records if r["record_type"] == kind)
            self.assertEqual(projected, source, kind)
        payment = self.service.get_payment("P1")
        self.assertEqual(payment["facts"]["posted_capture"]["cents"], 12000)
        self.assertEqual(payment["facts"]["posted_refund"]["cents"], 3000)


if __name__ == "__main__":
    unittest.main()
