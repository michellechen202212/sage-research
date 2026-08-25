# Reviewer workflow

For each first-pass output:

1. Start a fresh ChatGPT conversation.
2. Upload the generated output plus the four reviewer files in this directory.
3. Paste `PROMPT.md`.
4. Use only the opaque run ID (`run_v2_001` or `run_v2_002`). Do not reveal a condition or calibration folder.
5. Inspect every serving projection, export, summary, and timeline query—not only entity-detail endpoints.
6. If a query joins two one-to-many children, inspect its row grain and every downstream aggregation or serialization that consumes those rows.
7. Treat passing generated tests as ordinary implementation evidence only; it is not evidence of semantic correctness.
8. Save the completed review as `blind_review_<run_id>.md`.
9. Do not repair anything until both first-pass reviews are complete.
10. Only then consult `researcher_private/condition_mapping.json`.
## T17 semantic-grain guidance

- Judge semantic grain, not serialization style or metadata verbosity.
- Do not fail an output solely because a literal `grain` property is absent.
- When unambiguous, infer grain from stable IDs, structure, and cardinality; a projection-level or schema-level declaration may govern homogeneous rows.
- Treat nested amount, timestamp, and lineage wrappers as inheriting the containing fact's grain unless they form independently iterable collections or independently identified facts.
- Fail when one serving structure mixes incompatible grains, has contradictory identity/cardinality, implies unsupported multiplicity, or exposes an independently consumable fact whose grain cannot be determined.
