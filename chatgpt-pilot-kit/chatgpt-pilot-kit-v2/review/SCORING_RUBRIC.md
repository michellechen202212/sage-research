# Blind Scoring Rubric

T01 Same-SKU order-line preservation: O1 must retain 2 distinct lines.
T02 Order merchandise reconciliation: O1 line merchandise = 100.
T03 Same-payment authorization preservation: P1 has exactly 2 distinct authorization attempts, A1 and A2.
T04 Authorization non-additivity: A1 and A2 remain attempt facts and must not become 200 paid.
T05 Same-payment settlement preservation: P1 has exactly 2 distinct settlement events, S1 and S2.
T06 Settlement reconciliation without sibling duplication: S1 + S2 = 100 for P1, and authorization × settlement duplication must not inflate counts or amounts.
T07 Same-SKU POS occurrence preservation: R1 has exactly 2 distinct item occurrences, I1 and I2, both SKU-X.
T08 POS tender preservation: R1 has exactly 2 distinct tender legs, T1 and T2.
T09 Receipt-grain total preservation: R1 receipt_total remains 100 at receipt grain and is not treated as additive on child rows.
T10 POS item reconciliation: R1 item occurrences remain 40 + 60 = 100 without collapsing the same-SKU occurrences.
T11 POS tender reconciliation: R1 tender legs remain 30 + 70 = 100.
T12 No item × tender multiplication: serving or aggregate logic must not multiply R1 receipt, item, or tender values by joining its two child collections.
T13 Same-type tender preservation: R2 has 2 distinct CASH tender legs.
T14 Return/refund distinction: RET1 value 100, RF1 refund 80.
T15 Order event time uses ordered_at, not created_at.
T16 Settlement chronology uses settled_at, not authorized_at.
T17 Semantic grain: every independently consumable serving projection, collection, or row/fact type has exactly one unambiguous grain. The grain may be documented once at the projection or schema level for homogeneous rows, or established by stable identity and structure without contradictory cardinality; a literal `grain` field is optional. Heterogeneous collections must each have an unambiguous grain. Nested value objects inherit the grain of their containing fact unless they are independently iterable or independently identified facts. FAIL only for actual semantic ambiguity, mixed grain, contradictory identity/cardinality, unsupported multiplicity, or an independently consumable fact whose grain cannot be determined.
T18 Every investigator-visible amount, including compact-projection amounts, exposes or documents its monetary semantic type.
T19 Visible monetary values retain stable source identity and aggregation lineage, including within projections, exports, summaries, and timelines.
T20 No invented line-to-payment or item-to-tender allocation; the compact projection must not imply an item-to-tender relationship absent from the source.

Primary score (SIPR) = passed applicable tests / applicable tests. The denominator remains the count of applicable items among T01-T20.

