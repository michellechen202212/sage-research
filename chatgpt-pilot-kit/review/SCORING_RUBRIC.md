# Blind Scoring Rubric

T01 Same-SKU order-line preservation: O1 must retain 2 distinct lines.
T02 Order merchandise reconciliation: O1 line merchandise = 100.
T03 Authorization attempt count: P1 has 2 attempts.
T04 Authorization non-additivity: A1+A2 must not become 200 paid.
T05 Settlement event count: P2 has 2 settlement events.
T06 Settlement reconciliation: S1+S2 = 100 for the fixture.
T07 POS item count: R1 has 2 item occurrences.
T08 POS tender count: R1 has 2 tender legs.
T09 Receipt total preservation: R1 total = 100.
T10 POS item sum: R1 items sum to 100.
T11 POS tender sum: R1 tenders sum to 100.
T12 No cross-product inflation: no valid aggregate may turn R1 into 400 receipt value.
T13 Same-type tender preservation: R2 has 2 CASH tender legs.
T14 Return/refund distinction: RET1 value 100, RF1 refund 80.
T15 Order event time uses ordered_at, not created_at.
T16 Settlement chronology uses settled_at, not authorized_at.
T17 Every serving object has exactly one declared grain.
T18 Every investigator-visible amount exposes/documents semantic type.
T19 Visible monetary values retain source identity + aggregation lineage.
T20 No invented line-payment or item-tender allocation.

Primary score = passed applicable tests / applicable tests.
