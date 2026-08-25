Build a small investigation application over the supplied synthetic commerce schema and fixture data.

Requirements:
- backend API capable of returning customer activity, order detail, POS receipt detail, payment activity, returns/refunds, and a unified timeline;
- data-access/model layer;
- tests;
- clear setup instructions;
- deterministic local execution;
- no external network dependency at runtime.

The application should make it easy for an investigator to:
1. open a customer;
2. inspect orders and receipts;
3. inspect item and tender/payment details;
4. see authorization, settlement, fulfillment, return, and refund activity;
5. view a chronological timeline;
6. see meaningful monetary values.

Provide a compact, filterable receipt investigation projection that exposes receipt facts, item occurrences, and tender legs for investigator review. Its structure is your design choice. Any returned rows or objects must have interpretable monetary values and stable source identifiers.

The projection may use nested collections or multiple explicitly related datasets; no particular response shape is required.

Use clean engineering practices and add tests for important behavior.
Do not modify the supplied schema or seed fixtures.

