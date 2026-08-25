import json
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import urlopen

from app import make_server
from data_access import InvestigationRepository, NotFoundError, create_database


class RepositoryTests(unittest.TestCase):
    def setUp(self):
        self.db = create_database()
        self.repo = InvestigationRepository(self.db)

    def tearDown(self):
        self.db.close()

    def test_order_keeps_duplicate_sku_occurrences_and_fulfillment(self):
        order = self.repo.order_detail("O1")
        self.assertEqual(["L1", "L2"], [line["order_line_id"] for line in order["lines"]])
        self.assertEqual("100.00", order["ordered_total"])
        self.assertEqual(["0.400", "0.600"], [event["fulfilled_quantity"] for event in order["lines"][0]["fulfillment_events"]])

    def test_payment_activity_preserves_attempts_and_settlement_legs(self):
        payment = self.repo.payment_activity("P1")
        self.assertEqual(["DECLINED", "APPROVED"], [a["authorization_status"] for a in payment["authorizations"]])
        self.assertEqual(["S1", "S2"], [s["settlement_id"] for s in payment["settlements"]])
        self.assertEqual("100.00", payment["settled_total"])

    def test_receipt_projection_is_filterable_and_occurrence_safe(self):
        receipts = self.repo.receipt_projection(sku="SKU-X", tender_type="VISA")
        self.assertEqual(["R1"], [receipt["receipt_id"] for receipt in receipts])
        self.assertEqual(["I1", "I2"], [item["receipt_item_id"] for item in receipts[0]["items"]])
        self.assertEqual("100.00", receipts[0]["item_total"])
        self.assertEqual("100.00", receipts[0]["tender_total"])

    def test_timeline_is_chronological_and_has_stable_ids(self):
        timeline = self.repo.timeline("C1")
        self.assertEqual(timeline, sorted(timeline, key=lambda event: (event["occurred_at"], event["event_type"], event["source_id"])))
        self.assertIn("RF1", [event["source_id"] for event in timeline])
        self.assertEqual("80.00", next(event["amount"] for event in timeline if event["source_id"] == "RF1"))

    def test_unknown_entity_raises_not_found(self):
        with self.assertRaises(NotFoundError):
            self.repo.order_detail("missing")


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = make_server(port=0)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def get(self, path):
        with urlopen(self.base + path) as response:
            return response.status, json.load(response)

    def test_customer_endpoint_contains_all_investigation_views(self):
        status, body = self.get("/customers/C1")
        self.assertEqual(200, status)
        self.assertEqual({"customer", "orders", "receipts", "returns", "timeline"}, set(body))
        self.assertEqual("80.00", body["returns"][0]["refunded_total"])

    def test_receipt_api_filter(self):
        status, body = self.get("/receipts?tender_type=VISA")
        self.assertEqual(200, status)
        self.assertEqual(["R1"], [row["receipt_id"] for row in body])

    def test_not_found_is_json_404(self):
        with self.assertRaises(HTTPError) as caught:
            self.get("/orders/nope")
        self.assertEqual(404, caught.exception.code)
        self.assertIn("not found", json.load(caught.exception)["error"])


if __name__ == "__main__":
    unittest.main()
