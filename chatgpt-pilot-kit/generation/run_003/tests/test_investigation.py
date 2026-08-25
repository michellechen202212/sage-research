import json
import sqlite3
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

from app import create_handler
from repository import InvestigationRepository, initialize_database


BASE = Path(__file__).resolve().parents[1]


class RepositoryContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp.name) / "test.db"
        initialize_database(self.db_path, BASE / "schema.sql", BASE / "seed.sql")
        self.connection = sqlite3.connect(self.db_path)
        self.repo = InvestigationRepository(self.connection)

    def tearDown(self):
        self.connection.close()
        self.temp.cleanup()

    def test_same_sku_order_lines_retain_source_identity(self):
        order = self.repo.get_order("O1")
        self.assertEqual("order", order["grain"])
        self.assertEqual(["L1", "L2"], [line["order_line_id"] for line in order["lines"]])
        self.assertEqual(["SKU-A", "SKU-A"], [line["sku"] for line in order["lines"]])
        self.assertEqual("100.00", order["ordered_total"]["amount"])
        self.assertEqual(["O1"], order["ordered_total"]["lineage"]["source_ids"])

    def test_order_children_are_independent_and_authorization_is_not_payment(self):
        order = self.repo.get_order("O1")
        self.assertEqual(2, len(order["lines"]))
        self.assertEqual(2, len(order["payments"]))
        p1, p2 = order["payments"]
        self.assertEqual(["A1", "A2"], [a["authorization_id"] for a in p1["authorizations"]])
        self.assertEqual([], p1["settlements"])
        self.assertEqual([], p2["authorizations"])
        self.assertEqual(["S1", "S2"], [s["settlement_id"] for s in p2["settlements"]])
        self.assertEqual("authorization_attempt_amount", p1["authorizations"][0]["authorization_amount"]["semantic_type"])
        self.assertEqual("settlement_event_amount", p2["settlements"][0]["settlement_amount"]["semantic_type"])

    def test_receipt_items_and_tenders_remain_independent_occurrences(self):
        receipt = self.repo.get_receipt("R2")
        self.assertEqual(["I3"], [item["receipt_item_id"] for item in receipt["items"]])
        self.assertEqual(["T3", "T4"], [t["tender_leg_id"] for t in receipt["tenders"]])
        self.assertEqual(["CASH", "CASH"], [t["tender_type"] for t in receipt["tenders"]])
        self.assertNotIn("item_id", receipt["tenders"][0])
        self.assertEqual("50.00", receipt["receipt_total"]["amount"])

    def test_return_and_refund_are_distinct_facts_with_meaningful_money(self):
        ret = self.repo.get_return("RET1")
        self.assertEqual("100.00", ret["return_merchandise_value"]["amount"])
        self.assertEqual("80.00", ret["refunds"][0]["refund_amount"]["amount"])
        self.assertEqual("refund_issued_at", ret["refunds"][0]["refunded_at"]["meaning"])
        self.assertIsNone(ret["original_receipt_id"])

    def test_timeline_is_chronological_and_typed_without_cross_products(self):
        timeline = self.repo.timeline("C1")
        events = timeline["events"]
        timestamps = [e["event_at"]["value"] for e in events]
        self.assertEqual(timestamps, sorted(timestamps))
        source_pairs = [(e["source"]["table"], e["source"]["id"]) for e in events]
        self.assertEqual(len(source_pairs), len(set(source_pairs)))
        self.assertIn(("payment_authorization", "A1"), source_pairs)
        self.assertIn(("payment_settlement", "S2"), source_pairs)
        self.assertIn(("refund", "RF1"), source_pairs)
        self.assertTrue(all(e["grain"] == "timeline_event" for e in events))


class HttpApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.db_path = Path(cls.temp.name) / "http.db"
        initialize_database(cls.db_path, BASE / "schema.sql", BASE / "seed.sql")
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), create_handler(cls.db_path))
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()
        cls.temp.cleanup()

    def get(self, path):
        with urllib.request.urlopen(self.base_url + path) as response:
            return response.status, json.load(response)

    def test_customer_activity_endpoint(self):
        status, customer = self.get("/api/customers/C1")
        self.assertEqual(200, status)
        self.assertEqual("C1", customer["customer_ref_id"])
        self.assertEqual(["O1"], [o["order_id"] for o in customer["orders"]])
        self.assertEqual(["R1", "R2"], [r["receipt_id"] for r in customer["receipts"]])

    def test_detail_and_timeline_endpoints(self):
        self.assertEqual("order", self.get("/api/orders/O1")[1]["grain"])
        self.assertEqual("pos_receipt", self.get("/api/receipts/R1")[1]["grain"])
        self.assertEqual("payment", self.get("/api/payments/P1")[1]["grain"])
        self.assertEqual("merchandise_return", self.get("/api/returns/RET1")[1]["grain"])
        self.assertEqual("customer_timeline", self.get("/api/customers/C1/timeline")[1]["grain"])

    def test_unknown_entity_returns_404(self):
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(self.base_url + "/api/orders/missing")
        self.assertEqual(404, caught.exception.code)


if __name__ == "__main__":
    unittest.main()
