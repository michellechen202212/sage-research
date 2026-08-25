# Blind Semantic Review

You are evaluating an AI-generated investigation application.

You are NOT told which experimental condition produced it.

Review:
- the generated implementation;
- schema.sql;
- seed.sql;
- DOMAIN_CONTRACT_REVIEWER.md;
- SCORING_RUBRIC.md.

Do not reward clean code or passing ordinary tests if the implementation violates the frozen semantic rules.

Score T01-T20 as PASS / FAIL / N/A.
For every failure, cite the relevant implementation file/path and explain the semantic error.

Return:
1. T01-T20 table.
2. Semantic Invariant Pass Rate (SIPR).
3. Defects grouped by identity, grain, cardinality, money, time, lineage.
4. Ordinary tests that pass while semantic invariants fail.
5. Minimal repair set.

Do not modify the implementation.

