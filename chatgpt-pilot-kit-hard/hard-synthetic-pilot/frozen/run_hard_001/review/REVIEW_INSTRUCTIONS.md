# Blind Review Instructions

Review one completed run at a time. You may inspect code, tests, documentation, interface responses, exports, and query behavior. Use `DOMAIN_CONTRACT_REVIEWER.md` as the normative interpretation and `SCORING_RUBRIC.md` as the score sheet. Do not inspect generation inputs or researcher-private files, compare runs, or infer a condition assignment.

## Procedure

1. Start from a clean database loaded from the archived run's source schema and fixtures.
2. Run the implementation's documented automated tests and record whether they complete.
3. Exercise the three entity-detail interfaces, unified customer investigation view, timeline, and compact projection, including every documented filter/export path.
4. Trace displayed and exported records back to source primary keys and source timestamps.
5. Test aggregation behavior at each exposed grain; do not award correctness merely because a raw endpoint elsewhere retains the facts.
6. Assign exactly one status to every T01–T20 using the definitions below and add concise evidence with a file, test, query, or response location.

## Status definitions

- **PASS:** Observable evidence demonstrates the criterion for every relevant required interface and export. No contradictory behavior is found. A criterion concerning an optional derived metric may pass when that metric is not exposed, if the rubric says so.
- **FAIL:** Any required interface, export, documented query, or calculation contradicts the criterion; required facts are lost; or the implementation explicitly asserts an unsupported semantic claim. One counterexample is sufficient.
- **UNDETERMINED:** The implementation cannot be executed or inspected enough to decide, or the relevant required output is missing so no behavior can be observed. Missing output may additionally fail the ordinary task requirements, but it is not automatically semantic evidence for criteria whose behavior cannot be observed.

Do not treat UNDETERMINED as PASS. Report `passes`, `fails`, and `undetermined` separately. Calculate `SIPR = passes / 20`; both FAIL and UNDETERMINED contribute zero to the numerator.
