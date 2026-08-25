import json
import sqlite3
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

from app import Handler
from investigation_service import InvestigationService, NotFoundError, initialize_database


ROOT = Path(__file__).parent


class ServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.database = Path(cls.temp.name) / "fixture.db"
        initialize_database(cls.database, ROOT / "schema.sql", ROOT / "seed.sql")
        cls.service = InvestigationService(cls.database)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_entity_details_and_missing(self):
        order = self.service.order("O1001")
        self.assertEqual(["L1", "L2", "L3"], [line["order_line_id"] for line in order["lines"]])
        self.assertEqual(2, len(order["lines"][1]["fulfillment_events"]))
        self.assertEqual("120.00", order["order_total"]["decimal"])
        self.assertEqual(["E1", "E2", "E3", "E4", "E5"], [e["event_id"] for e in self.service.payment("P1")["events"]])
        receipt = self.service.receipt("R1")
        self.assertEqual(["I1", "I2", "I3"], [i["receipt_item_id"] for i in receipt["items"]])
        self.assertEqual(["T1", "T2", "T3"], [t["tender_leg_id"] for t in receipt["tender_legs"]])
        for function, value in ((self.service.order, "missing"), (self.service.payment, "missing"), (self.service.receipt, "missing"), (self.service.customer, "missing")):
            with self.assertRaises(NotFoundError):
                function(value)

    def test_customer_sections_timeline_and_metrics(self):
        view = self.service.customer("C1")
        self.assertTrue({"customer", "orders", "payments", "receipts", "returns", "payment_refund_facts", "timeline"} <= set(view))
        times = [entry["timestamp"] for entry in view["timeline"]]
        self.assertEqual(sorted(times), times)
        self.assertTrue(all(entry.get("type") and entry.get("timestamp") for entry in view["timeline"]))
        facts = view["payment_refund_facts"][0]
        self.assertEqual(12000, facts["gross_captured"]["cents"])
        self.assertEqual(3000, facts["posted_refunds"]["cents"])
        self.assertEqual(9000, facts["net_captured_after_refunds"]["cents"])
        self.assertFalse(facts["lineage"]["auth_events_included"])

    def test_every_compact_filter_and_determinism(self):
        self.assertEqual(24, self.service.compact(customer_id="C1")["count"])
        self.assertEqual(5, self.service.compact(record_type="payment_event")["count"])
        self.assertEqual(14, self.service.compact(order_id="O1001")["count"])
        self.assertEqual(7, self.service.compact(sku="SKU-A")["count"])
        ranged = self.service.compact(from_at="2026-01-13T00:00:00Z", to_at="2026-01-15T11:00:00Z")
        self.assertEqual(["receipt:R1", "receipt_item:I1", "receipt_item:I2", "receipt_item:I3", "return:RET1", "tender_leg:T1", "tender_leg:T2", "tender_leg:T3"],
                         [f'{r["record_type"]}:{r["record_id"]}' for r in ranged["records"]])
        first = json.dumps(self.service.compact(), sort_keys=True)
        second = json.dumps(self.service.compact(), sort_keys=True)
        self.assertEqual(first, second)
        with self.assertRaises(ValueError):
            self.service.compact(record_type="bogus")

    def test_fixture_reconciliation(self):
        expected_counts = {
            "customer": 1, "commerce_order": 2, "order_line": 4, "fulfillment_event": 4,
            "payment": 1, "payment_event": 5, "pos_receipt": 1,
            "receipt_item_occurrence": 3, "tender_leg": 3, "merchandise_return": 1,
        }
        db = sqlite3.connect(self.database)
        try:
            for table, count in expected_counts.items():
                self.assertEqual(count, db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        finally:
            db.close()
        compact = self.service.compact()["records"]
        self.assertEqual(sum(expected_counts.values()) - expected_counts["customer"], len(compact))
        by_type = {}
        for record in compact:
            by_type.setdefault(record["record_type"], []).append(record)
        expected_money = {
            "order": 14000, "order_line": 14000, "fulfillment_event": 12000,
            "payment_event": 39000, "receipt": 12000, "receipt_item": 12000,
            "tender_leg": 12000, "return": 5000,
        }
        for kind, total in expected_money.items():
            self.assertEqual(total, sum(row["money"]["cents"] for row in by_type[kind]))


class HttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        database = Path(cls.temp.name) / "http.db"
        initialize_database(database, ROOT / "schema.sql", ROOT / "seed.sql")
        Handler.service = InvestigationService(database)
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()
        cls.temp.cleanup()

    def test_http_success_filter_and_not_found(self):
        with urllib.request.urlopen(self.base + "/v1/orders/O1001") as response:
            self.assertEqual("O1001", json.load(response)["order_id"])
        with urllib.request.urlopen(self.base + "/v1/compact?record_type=tender_leg") as response:
            self.assertEqual(3, json.load(response)["count"])
        with self.assertRaises(urllib.error.HTTPError) as context:
            urllib.request.urlopen(self.base + "/v1/orders/nope")
        self.assertEqual(404, context.exception.code)
        self.assertEqual("not_found", json.load(context.exception)["error"])


if __name__ == "__main__":
    unittest.main()
