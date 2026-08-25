# Semantic Integrity Preservation Rubric

Score each criterion once. Apply the global PASS/FAIL/UNDETERMINED definitions in `REVIEW_INSTRUCTIONS.md`. The criterion-specific evidence rules below refine them.

| ID | Criterion | PASS evidence | FAIL evidence |
|---|---|---|---|
| T01 | order_id identity preserved | Order lookup, customer view, and projection key orders by `order_id`; O1001 and O1002 remain addressable. | An order is keyed, joined, overwritten, or deduplicated by another field. |
| T02 | duplicate order_number not treated as identity | Both O1001/WEB and O1002/STORE appear independently despite `ORD-7788`. | The orders merge, collide, overwrite, or one disappears because the reference repeats. |
| T03 | same-SKU order lines remain distinct | L1 and L2 retain separate IDs, amounts 40.00 and 50.00, and occurrence records. | SKU grouping merges them or loses either line's identity/value. |
| T04 | split fulfillment does not duplicate line value | F2 and F3 remain separate 25.00 events linked to one 50.00 L2, and aggregating exposed line value yields 50.00 once. | L2's 50.00 is repeated as additive value per fulfillment or fulfillment amount is used as line identity. |
| T05 | all authorization attempts preserved | E1 declined and E2 approved are both visible with IDs, statuses, amounts, and event times. | Either attempt is filtered, merged, or overwritten. |
| T06 | AUTH not treated as paid value | Paid/settled/captured totals exclude AUTH; AUTH values are labeled attempts. | AUTH contributes to paid, captured, settled, net-sales, or equivalent economic value. |
| T07 | multiple CAPTURE events preserved | E3/70.00 and E4/50.00 remain separately traceable. | Captures merge without lineage, overwrite, or one disappears. |
| T08 | gross capture reconciles to 120.00 | Any gross-capture view totals posted E3+E4 to 120.00 with both source IDs recoverable. | Gross capture has another value or includes non-CAPTURE events. |
| T09 | refund remains a distinct 30.00 fact | E5 is visible as a posted REFUND for 30.00 with its own identity/time. | It is lost, relabeled as capture/return value, or absorbed without lineage. |
| T10 | any exposed net metric is 90.00 and semantically typed | No net metric is exposed, or it is 90.00 and explicitly defined as gross posted captures less posted refunds with currency/grouping. | An exposed net metric differs, lacks semantic typing, or uses AUTH/return value. |
| T11 | receipt items remain three source occurrences | I1, I2, and I3 each appear once at item grain and remain traceable. | An item is merged, omitted, or multiplied in serving semantics. |
| T12 | tender legs remain three source occurrences | T1, T2, and T3 each appear once at tender-leg grain and remain traceable. | A leg is merged, omitted, or multiplied in serving semantics. |
| T13 | repeated VISA legs remain distinct | T1/60.00 and T2/20.00 retain separate occurrence IDs. | VISA legs are grouped into an untraceable single fact or one is lost. |
| T14 | no item x tender fanout reaches serving semantics | Item and tender siblings are bounded separately, or any flat output declares a single grain without a 3-by-3 cross-product/additive distortion. | Serving output emits or semantically relies on the unsupported nine item-tender combinations. |
| T15 | receipt total remains non-additive below receipt grain | R1 total 120.00 occurs once at receipt grain or repeats only as explicitly non-additive context. | Repeated receipt total is offered/summed as item- or tender-grain additive measure. |
| T16 | timestamps retain event meaning | Order placement uses `ordered_at`, payment timeline uses `event_at`, and persistence timestamps are separately named. | `created_at`, `updated_at`, or `ingested_at` substitutes for the relevant business event. |
| T17 | compact projection has one coherent grain | Projection/export declares and consistently implements one row grain, or exposes explicitly separated bounded sections each with a coherent grain. | A row mixes independent grains or its identity/cardinality cannot be stated consistently. |
| T18 | visible monetary values retain semantic type | Each amount is labeled or structurally contextualized as order total, line, fulfillment, AUTH attempt, CAPTURE, REFUND, item, tender, or return value. | A generic/ambiguous amount obscures event or fact semantics, or types are mislabeled. |
| T19 | derived amounts retain source identity and aggregation lineage | Every derived amount identifies contributing source IDs or a reproducible source selection plus operation, grouping, and currency rule. | A derived amount lacks reproducible lineage or combines currencies/semantic types opaquely. |
| T20 | no unsupported allocations or relationships are invented | No line-payment, auth-capture, item-tender, or RET1-E5 causal/allocation link is asserted; absent links remain unknown. | Any such unsupported mapping, causality, or allocation is materialized or stated. |

## Score

Record one status per ID. `SIPR = number of PASS statuses / 20` (range 0.00–1.00). Report the raw counts and retain evidence notes for audit.
