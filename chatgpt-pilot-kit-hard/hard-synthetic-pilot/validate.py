"""Validate benchmark fixtures and packaging without running generation conditions."""
from __future__ import annotations

import hashlib
import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RUNS = [ROOT / "generation" / "run_hard_001", ROOT / "generation" / "run_hard_002"]
SHARED = ["PROMPT.md", "TEST_REQUIREMENTS.md", "schema.sql", "seed.sql"]


def scalar(db: sqlite3.Connection, sql: str) -> int:
    return db.execute(sql).fetchone()[0]


def main() -> None:
    for name in SHARED:
        # Ignore terminal newline convention; all meaningful input bytes must match.
        normalized = [(run / name).read_text(encoding="utf-8").rstrip("\r\n").encode() for run in RUNS]
        digests = [hashlib.sha256(value).hexdigest() for value in normalized]
        assert digests[0] == digests[1], f"shared input differs: {name}"

    for run in RUNS:
        db = sqlite3.connect(":memory:")
        db.executescript((run / "schema.sql").read_text(encoding="utf-8"))
        db.executescript((run / "seed.sql").read_text(encoding="utf-8"))
        expected = {
            "duplicate order_number": ("SELECT COUNT(*) FROM commerce_order WHERE order_number='ORD-7788'", 2),
            "distinct order_id": ("SELECT COUNT(DISTINCT order_id) FROM commerce_order WHERE order_number='ORD-7788'", 2),
            "same-SKU lines": ("SELECT COUNT(*) FROM order_line WHERE order_id='O1001' AND sku='SKU-A'", 2),
            "L2 fulfillments": ("SELECT COUNT(*) FROM fulfillment_event WHERE order_line_id='L2'", 2),
            "P1 events": ("SELECT COUNT(*) FROM payment_event WHERE payment_id='P1'", 5),
            "AUTH cents": ("SELECT SUM(amount_cents) FROM payment_event WHERE payment_id='P1' AND event_type='AUTH'", 24000),
            "CAPTURE cents": ("SELECT SUM(amount_cents) FROM payment_event WHERE payment_id='P1' AND event_type='CAPTURE'", 12000),
            "REFUND cents": ("SELECT SUM(amount_cents) FROM payment_event WHERE payment_id='P1' AND event_type='REFUND'", 3000),
            "R1 items": ("SELECT COUNT(*) FROM receipt_item_occurrence WHERE receipt_id='R1'", 3),
            "R1 tenders": ("SELECT COUNT(*) FROM tender_leg WHERE receipt_id='R1'", 3),
            "repeated SKU": ("SELECT COUNT(*) FROM receipt_item_occurrence WHERE receipt_id='R1' AND sku='SKU-A'", 2),
            "repeated VISA": ("SELECT COUNT(*) FROM tender_leg WHERE receipt_id='R1' AND tender_type='VISA'", 2),
        }
        for label, (sql, value) in expected.items():
            assert scalar(db, sql) == value, f"{run.name}: {label}"
        tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert not any("return" in t and "refund" in t for t in tables), "return-refund bridge exists"

    rubric = (ROOT / "review" / "SCORING_RUBRIC.md").read_text(encoding="utf-8")
    ids = re.findall(r"^\| (T\d{2}) \|", rubric, re.MULTILINE)
    assert ids == [f"T{i:02d}" for i in range(1, 21)], "rubric IDs must be T01-T20 exactly once"
    contracts = list((ROOT / "generation").glob("*/DOMAIN_CONTRACT.md"))
    assert len(contracts) == 1, "exactly one generation run must contain DOMAIN_CONTRACT.md"
    public = "\n".join(p.read_text(encoding="utf-8") for base in (ROOT / "generation", ROOT / "review") for p in base.rglob("*") if p.is_file())
    assert "condition_a_implementation_first" not in public
    assert "condition_b_semantic_contract" not in public
    assert "condition_mapping.json" not in public
    print("PASS: SQLite fixtures, shared inputs, rubric, contract count, and mapping isolation")


if __name__ == "__main__":
    main()
