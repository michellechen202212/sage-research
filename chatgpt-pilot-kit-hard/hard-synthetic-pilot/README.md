# Hard Synthetic Pilot

This publication-safe benchmark studies semantic correctness in AI-assisted data engineering. It uses wholly synthetic names, identifiers, amounts, and schemas.

## Study package

- `generation/run_hard_001/` and `generation/run_hard_002/` are neutral generation inputs.
- Each run contains the same `PROMPT.md`, `schema.sql`, `seed.sql`, and `TEST_REQUIREMENTS.md`.
- Exactly one run also contains an additional input document. Run-to-condition assignment is intentionally unavailable here.
- `review/` contains blind-review instructions, the reviewer-facing domain contract, and the 20-item scoring rubric.
- `researcher_private/` is restricted to study administrators and must not be supplied to generation or review agents.

## Execution protocol

1. Copy each run directory into a separate clean implementation workspace.
2. Give the implementation agent every file in that run directory and no files from `review/` or `researcher_private/`.
3. Do not identify conditions to implementation agents.
4. Archive the produced implementation and test output under its neutral run ID.
5. Give blind reviewers the implementation, its run ID, and all files in `review/`; do not give them `generation/` or `researcher_private/`.
6. Score each run independently. Compute SIPR as passes divided by 20.

The package itself does not execute either generation condition.
