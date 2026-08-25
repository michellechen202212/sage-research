# Domain Contract

This document is normative. When a convenient representation conflicts with these rules, preserve these rules.

## Identity

- `order_id` is order identity. `order_number` is a human-facing reference only and is not unique.
- `order_line_id` is order-line identity. SKU is an attribute and is not identity.
- `receipt_item_id` and `tender_leg_id` identify source occurrences. Equal SKU or tender type does not merge occurrences.

## Cardinality

- Order lines, fulfillment events, and payments have distinct grains. A fulfillment is an event for a line, not another copy of the line.
- Payment events are independent event facts and must retain event identity.
- Receipt items and tender legs are independent sibling collections under a receipt.

## Money and event semantics

- `AUTH` amount is attempted authorization value, whether approved or declined.
- `CAPTURE` amount is settled, gross captured value.
- `REFUND` amount is a refund event value.
- Authorization attempts are not additive paid value.
- Order and receipt parent totals are non-additive below their parent grain and must not be repeated then summed as child facts.
- Every derived monetary metric must state its semantic type and aggregation lineage: included source event types/statuses, operation/sign convention, grouping keys, and currency handling.

## Time

- Order placement uses `ordered_at`.
- Payment facts use `payment_event.event_at`.
- `ingested_at`, `created_at`, and `updated_at` retain their own meanings and are not substitutes for a different business event.

## Relationships

- Do not infer a line-to-payment allocation.
- Do not infer an authorization-to-capture allocation.
- Do not infer an item-to-tender allocation.
- Do not infer a return-to-refund relationship without an explicit source bridge.

## Unknowns

- An absent relationship remains unknown; temporal proximity, customer equality, equal values, or plausibility does not create it.
- Unknown currency remains unknown. Do not default or copy currency from a nearby fact without a stated source relationship.

## Serving model

- Every independently consumable projection has one coherent declared grain.
- Bounded heterogeneous collections are allowed when their member grains remain explicit.
- Flattening must not create unsupported cross-products or change additive meaning.
