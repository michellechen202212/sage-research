\# SAGE Replication Package



Replication materials for:



\*\*Code Generation Is Not Model Generation: Semantic Contracts for Reliable AI-Assisted Data Engineering\*\*



\## Overview



This repository contains a fully synthetic benchmark and frozen experimental artifacts used to evaluate SAGE (Semantic Assurance for Generated Engineering).



The study compares two AI-assisted software-generation conditions:



\- \*\*Implementation-first:\*\* schema, fixtures, application task, and ordinary testing requirements.

\- \*\*Semantic-first:\*\* the same materials plus an explicit semantic contract.



No proprietary source code, production data, employer-specific schemas, internal identifiers, tickets, screenshots, or organizational information are included.



\## Research question



Can AI-generated data-intensive software pass its own functional tests while violating independently specified semantic requirements?



\## Benchmark



The synthetic commerce-investigation benchmark contains interacting ambiguities involving:



\- identity versus human-facing reference;

\- repeated same-SKU source occurrences;

\- split fulfillment;

\- heterogeneous payment events;

\- repeated tender types;

\- independent sibling collections;

\- non-additive parent totals;

\- business-event versus persistence timestamps;

\- derived monetary lineage;

\- unsupported relationships.



Twenty frozen semantic invariants are scored independently.



The primary metric is:



\*\*SIPR = semantic invariants passed / 20\*\*



\## Hard benchmark results



| Condition | Run | Generated tests | SIPR |

|---|---|---:|---:|

| Implementation-first | run\_01 | 4/4 | 18/20 (90%) |

| Implementation-first | run\_02 | 4/4 | 18/20 (90%) |

| Semantic-first | run\_01 | 5/5 | 20/20 (100%) |

| Semantic-first | run\_02 | 5/5 | 20/20 (100%) |



Both implementation-first implementations passed all of their generated tests but independently failed the same two semantic criteria:



\- \*\*T10:\*\* derived monetary semantics / currency grouping

\- \*\*T19:\*\* aggregation and source lineage



Both semantic-first implementations passed all 20 semantic invariants.



These results are exploratory and should not be interpreted as population-level effect estimates.



\## Repository structure



\- `benchmark/` — frozen synthetic schema, fixtures, test requirements, and semantic contract

\- `generation/implementation\_first/` — frozen first-pass implementations without the semantic contract

\- `generation/semantic\_first/` — frozen first-pass implementations generated with the semantic contract

\- `review/` — independent reviewer contract, instructions, and T01-T20 rubric

\- `results/` — summarized experimental results

\- `scripts/` — benchmark validation utilities



\## Experimental controls



Each generation run used a fresh isolated workspace.



First-pass implementations were frozen before correction or iterative feedback.



Semantic reviews were performed in separate fresh sessions using the same frozen T01-T20 rubric.



\## Reproduction



The generated implementations use Python and SQLite with no runtime network dependency.



Consult the README contained in each frozen run for its exact test command.



\## License



Add the appropriate repository license before public release.

