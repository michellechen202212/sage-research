import unittest

from app import build_repository, dispatch


class InvestigationTests(unittest.TestCase):
    def setUp(self):
        self.repo = build_repository()

    def test_same_sku_lines_keep_source_identity(self):
        order = self.repo.order("O1")
        self.assertEqual(["L1", "L2"], [x["order_line_id"] for x in order["lines"]])
        self.assertEqual(["SKU-A", "SKU-A"], [x["sku"] for x in order["lines"]])
        self.assertEqual("order", order["grain"])

    def test_payments_are_not_joined_or_allocated_to_lines(self):
        order = self.repo.order("O1")
        self.assertEqual(2, len(order["lines"]))
        self.assertEqual(2, len(order["payments"]))
        self.assertEqual("independent_order_children_no_allocation", order["collection_relationships"]["lines_and_payments"])
        self.assertFalse(any("payment" in line for line in order["lines"]))

    def test_authorization_attempts_and_settlements_remain_distinct(self):
        p1 = self.repo.payment("P1")
        self.assertEqual(["A1", "A2"], [a["authorization_id"] for a in p1["authorization_attempts"]])
        self.assertEqual(["DECLINED", "APPROVED"], [a["authorization_status"] for a in p1["authorization_attempts"]])
        self.assertEqual([], p1["settlement_events"])
        p2 = self.repo.payment("P2")
        self.assertEqual(["S1", "S2"], [s["settlement_id"] for s in p2["settlement_events"]])

    def test_receipt_items_and_tenders_are_independent(self):
        receipt = self.repo.receipt("R1")
        self.assertEqual(["I1", "I2"], [x["receipt_item_id"] for x in receipt["items"]])
        self.assertEqual(["T1", "T2"], [x["tender_leg_id"] for x in receipt["tender_legs"]])
        self.assertEqual("100.00", receipt["receipt_total"]["amount"])
        self.assertEqual(["R1"], receipt["receipt_total"]["source_ids"])
        self.assertFalse(any("tender" in item for item in receipt["items"]))

    def test_same_tender_class_does_not_collapse_identity(self):
        receipt = self.repo.receipt("R2")
        self.assertEqual(["T3", "T4"], [x["tender_leg_id"] for x in receipt["tender_legs"]])
        self.assertEqual(["CASH", "CASH"], [x["tender_type"] for x in receipt["tender_legs"]])

    def test_timeline_is_chronological_typed_and_not_cross_product(self):
        timeline = self.repo.timeline("C1")
        self.assertEqual(sorted(x["event_at"] for x in timeline), [x["event_at"] for x in timeline])
        self.assertEqual(12, len(timeline))
        self.assertEqual(2, sum(x["event_type"] == "payment_authorization" for x in timeline))
        self.assertEqual(2, sum(x["event_type"] == "payment_settlement" for x in timeline))
        self.assertTrue(all(x["grain"] == "timeline_event" for x in timeline))

    def test_return_and_refund_values_have_distinct_semantics(self):
        ret = self.repo.returns("C1")[0]
        self.assertEqual("returned_merchandise_value", ret["return_merchandise_value"]["semantic"])
        self.assertEqual("refund_issued_amount", ret["refunds"][0]["refund_amount"]["semantic"])
        self.assertEqual("80.00", ret["refunds"][0]["refund_amount"]["amount"])

    def test_currency_stays_unknown_and_routes_work(self):
        order = dispatch(self.repo, "/api/orders/O1")
        self.assertEqual("UNKNOWN", order["ordered_total"]["currency"])
        activity = dispatch(self.repo, "/api/customers/C1/activity")
        self.assertEqual("customer_activity", activity["grain"])


if __name__ == "__main__":
    unittest.main()
