import unittest

from investigation_service import InvestigationService, fixture_connection


class InvestigationServiceTests(unittest.TestCase):
    def setUp(self):
        self.db = fixture_connection(); self.service = InvestigationService(self.db)

    def tearDown(self): self.db.close()

    def test_entity_details_and_missing(self):
        self.assertEqual(self.service.order_detail("O1001")["order"]["order_total"]["decimal"], "120.00")
        self.assertEqual(len(self.service.payment_detail("P1")["payment"]["events"]), 5)
        self.assertEqual(len(self.service.receipt_detail("R1")["receipt"]["tender_legs"]), 3)
        for method in (self.service.order_detail, self.service.payment_detail, self.service.receipt_detail):
            self.assertEqual(method("missing")["error"], "not_found")

    def test_customer_sections_timeline_and_missing(self):
        view = self.service.customer_view("C1")
        for section in ("customer", "orders", "payments", "receipts", "returns", "payment_refund_facts", "timeline"):
            self.assertIn(section, view)
        keys = [(x["timestamp"], x["type"], x["id"]) for x in view["timeline"]]
        self.assertEqual(keys, sorted(keys)); self.assertTrue(all(x["type"] and x["timestamp"] for x in view["timeline"]))
        self.assertEqual(self.service.customer_view("missing")["error"], "not_found")

    def test_every_projection_filter_and_determinism(self):
        all_records = self.service.compact_projection()["records"]
        self.assertEqual(all_records, self.service.compact_projection()["records"])
        cases = {"customer_id": "C1", "record_type": "payment_event", "order_id": "O1001", "receipt_id": "R1",
                 "sku": "SKU-A", "from_timestamp": "2026-01-13T00:00:00Z", "to_timestamp": "2026-01-11T00:00:00Z"}
        for key, value in cases.items():
            records = self.service.compact_projection(**{key: value})["records"]
            self.assertTrue(records, key)
            if key not in ("from_timestamp", "to_timestamp"):
                self.assertTrue(all(r[key] == value for r in records), key)
            elif key == "from_timestamp": self.assertTrue(all(r["timestamp"] >= value for r in records))
            else: self.assertTrue(all(r["timestamp"] <= value for r in records))

    def test_fixture_reconciliation_counts_and_money(self):
        expected = {"order_line": 4, "fulfillment_event": 4, "payment_event": 5, "receipt_item": 3, "tender_leg": 3, "return": 1}
        records = self.service.compact_projection()["records"]
        for record_type, count in expected.items():
            self.assertEqual(sum(r["record_type"] == record_type for r in records), count)
        view = self.service.customer_view("C1")
        self.assertEqual(sum(o["order_total"]["cents"] for o in view["orders"]), 14000)
        self.assertEqual(view["payment_refund_facts"]["posted_capture"]["cents"], 12000)
        self.assertEqual(view["payment_refund_facts"]["posted_refund"]["cents"], 3000)
        self.assertEqual(sum(r["receipt_total"]["cents"] for r in view["receipts"]), 12000)
        self.assertEqual(sum(r["merchandise_value"]["cents"] for r in view["returns"]), 5000)


if __name__ == "__main__": unittest.main()
