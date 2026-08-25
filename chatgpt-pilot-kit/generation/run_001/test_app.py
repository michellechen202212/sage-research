import unittest

from app import InvestigationAPI
from data_access import CommerceRepository


class InvestigationAPITests(unittest.TestCase):
    def setUp(self):
        self.repository = CommerceRepository.from_fixtures()
        self.api = InvestigationAPI(self.repository)

    def tearDown(self):
        self.repository.connection.close()

    def test_customer_activity_summary(self):
        status, customer = self.api.route("GET", "/customers/C1")
        self.assertEqual(status, 200)
        self.assertEqual(customer["display_name"], "Synthetic Customer 1")
        self.assertEqual(customer["orders"][0]["ordered_total"], "100.00")
        self.assertEqual(len(customer["receipts"]), 2)
        self.assertEqual(customer["returns"][0]["refunds"][0]["refund_amount"], "80.00")

    def test_order_exposes_distinct_lines_payments_and_events(self):
        status, order = self.api.route("GET", "/orders/O1")
        self.assertEqual(status, 200)
        self.assertEqual([line["line_merchandise_amount"] for line in order["lines"]], ["40.00", "60.00"])
        self.assertEqual(order["lines"][0]["fulfillment_events"][1]["fulfilled_quantity"], "0.600")
        self.assertEqual(len(order["payments"]), 2)
        self.assertEqual([a["authorization_status"] for a in order["payments"][0]["authorizations"]],
                         ["DECLINED", "APPROVED"])
        self.assertEqual(sum(float(s["settlement_amount"]) for s in order["payments"][1]["settlements"]), 100.0)

    def test_receipt_preserves_repeated_tender_legs(self):
        status, receipt = self.api.route("GET", "/receipts/R2")
        self.assertEqual(status, 200)
        self.assertEqual([t["tender_amount"] for t in receipt["tenders"]], ["20.00", "30.00"])
        self.assertEqual(receipt["receipt_total"], "50.00")

    def test_timeline_is_chronological_and_complete(self):
        status, timeline = self.api.route("GET", "/customers/C1/timeline")
        self.assertEqual(status, 200)
        timestamps = [event["occurred_at"] for event in timeline]
        self.assertEqual(timestamps, sorted(timestamps))
        types = [event["event_type"] for event in timeline]
        for expected in ("ORDER_PLACED", "POS_RECEIPT", "PAYMENT_AUTHORIZATION",
                         "PAYMENT_SETTLEMENT", "FULFILLMENT", "RETURN", "REFUND"):
            self.assertIn(expected, types)
        self.assertEqual(len(timeline), 11)

    def test_errors_are_explicit(self):
        self.assertEqual(self.api.route("GET", "/orders/missing")[0], 404)
        self.assertEqual(self.api.route("POST", "/customers")[0], 405)
        self.assertEqual(self.api.route("GET", "/unknown")[0], 404)


if __name__ == "__main__":
    unittest.main()
