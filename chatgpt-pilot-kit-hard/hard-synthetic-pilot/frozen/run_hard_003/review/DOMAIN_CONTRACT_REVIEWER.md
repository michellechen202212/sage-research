# Reviewer Domain Contract

Use this document only to interpret and score completed implementations. It does not disclose run conditions.

## Identity and cardinality

`order_id`, `order_line_id`, `receipt_item_id`, `tender_leg_id`, and payment-event `event_id` are occurrence identities at their respective grains. `order_number`, SKU, and tender type are descriptive or business-reference values and need not be unique. Lines, fulfillment events, payment events, receipt items, and tender legs are distinct fact grains. Receipt items and tender legs are sibling collections.

## Monetary meaning

AUTH is an authorization attempt, CAPTURE is gross settled/captured value, and REFUND is refund-event value. Authorization attempts do not constitute paid value. Parent order and receipt totals are non-additive when repeated below parent grain. A derived monetary value is interpretable only when its semantic label, source event identities/types/statuses, operation/sign convention, grouping, and currency handling are available.

For the fixture, the two AUTH attempts total 240.00 as attempts, the two posted CAPTURE facts total 120.00 gross captured, and the posted REFUND fact is 30.00. A net value, if exposed, is 90.00 and must be labeled as derived net capture less refund. Summing every payment event amount to 390.00 is not a valid economic total.

## Time, relationships, and unknowns

Order placement time is `ordered_at`; payment business-event time is `event_at`. Persistence times retain their own meanings. No line-to-payment, authorization-to-capture, item-to-tender, or return-to-refund allocation may be inferred without an explicit source bridge. Missing relationships and missing currencies remain unknown.

## Serving

Every independently consumable projection must have one coherent, identifiable grain. Nested or otherwise bounded heterogeneous collections are acceptable. Flattening must not introduce a sibling cross-product, duplicate additive values, or imply unsupported relationships.
