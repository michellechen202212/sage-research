import unittest

from app import CommerceRepository, NotFoundError


class InvestigationSemanticsTests(unittest.TestCase):
    def setUp(self):
        self.repo = CommerceRepository.from_fixtures()

    def tearDown(self):
        self.repo.conn.close()

    def test_same_sku_order_lines_keep_source_identity(self):
        order = self.repo.order("O1")
        self.assertEqual(["L1", "L2"], [x["order_line_id"] for x in order["lines"]])
        self.assertEqual(["SKU-A", "SKU-A"], [x["sku"] for x in order["lines"]])
        self.assertEqual("O1", order["ordered_total"]["source_id"])
        self.assertEqual("100.00", order["ordered_total"]["value"])

    def test_authorizations_and_settlements_are_distinct_events(self):
        payment = self.repo.payment("P1")
        self.assertEqual(["A1", "A2"], [x["authorization_id"] for x in payment["authorizations"]])
        self.assertEqual(["DECLINED", "APPROVED"], [x["status"] for x in payment["authorizations"]])
        self.assertEqual(["S1", "S2"], [x["settlement_id"] for x in payment["settlements"]])
        self.assertEqual(["60.00", "40.00"], [x["settlement_amount"]["value"] for x in payment["settlements"]])

    def test_receipt_children_are_independent_and_occurrences_preserved(self):
        receipt = self.repo.receipt("R1")
        self.assertEqual(2, len(receipt["items"]))
        self.assertEqual(2, len(receipt["tenders"]))
        self.assertEqual(["I1", "I2"], [x["receipt_item_id"] for x in receipt["items"]])
        self.assertNotIn("tender_leg_id", receipt["items"][0])
        self.assertEqual("R1", receipt["receipt_total"]["source_id"])

    def test_receipt_filter_does_not_multiply_children(self):
        result = self.repo.receipts(customer_id="C1", sku="SKU-X", tender_type="CASH")
        self.assertEqual(["R1"], [x["receipt_id"] for x in result])
        self.assertEqual(2, len(result[0]["items"]))
        self.assertEqual(2, len(result[0]["tenders"]))
        self.assertEqual(["T1", "T2"], [x["tender_leg_id"] for x in result[0]["tenders"]])

    def test_timeline_is_chronological_typed_and_lineaged(self):
        timeline = self.repo.timeline("C1")
        dates = [x["occurred_at"]["value"] for x in timeline]
        self.assertEqual(dates, sorted(dates))
        self.assertEqual(2, sum(x["event_type"] == "PAYMENT_AUTHORIZATION" for x in timeline))
        refund = next(x for x in timeline if x["event_type"] == "REFUND")
        self.assertEqual("RF1", refund["source_id"])
        self.assertEqual("refund refunded_at", refund["occurred_at"]["semantic"])
        self.assertEqual("refund", refund["amount"]["source_type"])

    def test_return_does_not_invent_missing_receipt_relationship(self):
        result = self.repo.returns_for_customer("C1")[0]
        self.assertIsNone(result["original_receipt_id"])
        self.assertEqual("80.00", result["refunds"][0]["refund_amount"]["value"])

    def test_unknown_source_is_not_found(self):
        with self.assertRaises(NotFoundError):
            self.repo.customer("UNKNOWN")


if __name__ == "__main__":
    unittest.main()
