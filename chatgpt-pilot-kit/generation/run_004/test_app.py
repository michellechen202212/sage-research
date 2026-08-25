import json
import threading
import unittest
from decimal import Decimal
from urllib.error import HTTPError
from urllib.request import urlopen
from http.server import ThreadingHTTPServer

from app import create_handler
from repository import InvestigationRepository


class RepositoryTests(unittest.TestCase):
    def setUp(self):
        self.repository = InvestigationRepository.from_fixtures()

    def tearDown(self):
        self.repository.connection.close()

    def test_order_preserves_occurrences_and_payment_event_grain(self):
        order = self.repository.order("O1")
        self.assertEqual(["L1", "L2"], [line["order_line_id"] for line in order["lines"]])
        self.assertEqual(["DECLINED", "APPROVED"], [a["authorization_status"] for a in order["payments"][0]["authorizations"]])
        self.assertEqual("100.00", order["ordered_total"])
        settled = sum(
            (Decimal(s["settlement_amount"]) for p in order["payments"] for s in p["settlements"]),
            Decimal(),
        )
        self.assertEqual(Decimal("100.00"), settled)

    def test_receipt_keeps_multiple_same_type_tender_legs(self):
        receipt = self.repository.receipt("R2")
        self.assertEqual(["20.00", "30.00"], [t["tender_amount"] for t in receipt["tenders"]])

    def test_timeline_is_chronological_and_includes_key_activity(self):
        events = self.repository.timeline("C1")
        self.assertEqual(sorted(e["occurred_at"] for e in events), [e["occurred_at"] for e in events])
        self.assertTrue({"order_placed", "payment_authorization", "payment_settlement", "fulfillment", "pos_receipt", "merchandise_return", "refund"}.issubset({e["event_type"] for e in events}))
        self.assertEqual("80.00", events[-1]["amount"])


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repository = InvestigationRepository.from_fixtures()
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), create_handler(cls.repository))
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()
        cls.repository.connection.close()

    def get(self, path):
        with urlopen(self.base + path) as response:
            return response.status, json.load(response)

    def test_customer_activity_endpoint(self):
        status, body = self.get("/customers/C1/activity")
        self.assertEqual(200, status)
        self.assertEqual(1, len(body["orders"]))
        self.assertEqual(2, len(body["receipts"]))
        self.assertEqual("80.00", body["returns"][0]["refunds"][0]["refund_amount"])

    def test_missing_entity_and_route_are_404(self):
        for path in ("/customers/missing", "/not-a-route"):
            with self.assertRaises(HTTPError) as error:
                urlopen(self.base + path)
            self.assertEqual(404, error.exception.code)


if __name__ == "__main__":
    unittest.main()
