import sqlite3
import unittest

from investigation_service import InvestigationService, build_database


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.db = build_database()
        self.service = InvestigationService(self.db)

    def tearDown(self): self.db.close()

    def test_entity_success_and_missing(self):
        self.assertEqual(self.service.order("O1001")["order_id"], "O1001")
        self.assertEqual(self.service.payment("P1")["payment_id"], "P1")
        self.assertEqual(self.service.receipt("R1")["receipt_id"], "R1")
        for method in (self.service.order, self.service.payment, self.service.receipt):
            self.assertEqual(method("missing")["error"], "not_found")

    def test_customer_sections_and_timeline(self):
        result = self.service.customer("C1")
        for key in ("orders", "payments", "receipts", "returns", "payment_refund_facts", "timeline"):
            self.assertIn(key, result)
        timeline = result["timeline"]
        self.assertEqual(timeline, sorted(timeline, key=lambda x: (x["timestamp"], x["type"], x["id"])))
        self.assertTrue(all(entry.get("type") and entry.get("timestamp") for entry in timeline))

    def test_all_compact_filters(self):
        cases = {
            "customer_id": "C1", "fact_type": "receipt_item", "order_id": "O1001",
            "sku": "SKU-A", "from_at": "2026-01-13T00:00:00Z", "to_at": "2026-01-11T00:00:00Z",
        }
        for name, value in cases.items():
            with self.subTest(name=name):
                result = self.service.compact(**{name: value})
                self.assertGreater(result["count"], 0)
        self.assertEqual(self.service.compact(bogus="x")["error"], "invalid_filter")

    def test_deterministic_ordering(self):
        first = self.service.compact()["rows"]
        second = self.service.compact()["rows"]
        self.assertEqual(first, second)
        self.assertEqual(first, sorted(first, key=lambda x: (x["fact_type"], x["source_id"])))

    def test_fixture_reconciliation(self):
        expected = {"order": 2, "order_line": 4, "fulfillment_event": 4, "payment_event": 5, "receipt": 1, "receipt_item": 3, "tender_leg": 3, "return": 1}
        rows = self.service.compact()["rows"]
        for fact_type, count in expected.items():
            selected = [r for r in rows if r["fact_type"] == fact_type]
            self.assertEqual(len(selected), count)
        source_tables = {
            "order": ("commerce_order", "order_total_cents"), "order_line": ("order_line", "line_amount_cents"),
            "fulfillment_event": ("fulfillment_event", "amount_cents"), "payment_event": ("payment_event", "amount_cents"),
            "receipt": ("pos_receipt", "receipt_total_cents"), "receipt_item": ("receipt_item_occurrence", "item_amount_cents"),
            "tender_leg": ("tender_leg", "amount_cents"), "return": ("merchandise_return", "merchandise_value_cents"),
        }
        for fact_type, (table, column) in source_tables.items():
            expected_sum = self.db.execute(f"SELECT SUM({column}) FROM {table}").fetchone()[0]
            actual_sum = sum(r["amount"]["amount_cents"] for r in rows if r["fact_type"] == fact_type)
            self.assertEqual(actual_sum, expected_sum)
        view = self.service.customer("C1")
        self.assertEqual(len(view["orders"]), 2); self.assertEqual(len(view["payments"]), 1)
        self.assertEqual(len(view["receipts"]), 1); self.assertEqual(len(view["returns"]), 1)
        self.assertEqual(len(view["payment_refund_facts"]["events"]), 5)


if __name__ == "__main__": unittest.main()
