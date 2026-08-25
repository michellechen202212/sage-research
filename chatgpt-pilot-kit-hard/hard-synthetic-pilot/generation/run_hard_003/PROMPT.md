# Implementation Task

Build a small, testable investigation service over the supplied SQLite schema and fixtures. Choose a conventional implementation stack that can be run locally and document the commands needed to install, start, and test it.

## Required outputs

### Entity details

Provide endpoints or equivalent callable interfaces that return details for an order, a payment, and a POS receipt.

### Unified customer investigation view

Provide an interface keyed by customer that exposes orders, payments, receipts, returns, payment/refund facts, and a chronological typed timeline.

### Compact investigation projection

Provide a compact, filterable projection suitable for investigator review and export. It must expose enough information to investigate order and line facts, fulfillment events, payment events, receipt items, tender legs, and return/refund facts. The response structure and supported filters are design choices; document both.

## General requirements

- Treat the supplied schema and seed data as immutable source inputs.
- Make all seeded records accessible through at least one required output.
- Use deterministic ordering and stable, documented response shapes.
- Represent decimal money without binary floating-point errors.
- Include automated tests for entity lookup, the customer view, timeline ordering, filtering, and fixture reconciliation.
- Return a clear not-found result for unknown identifiers.
- Document setup, design decisions, API/interface examples, and test commands.
- Do not invent source records. If an association is not supported by supplied data, omit it or represent it as unknown.


