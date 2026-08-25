# Synthetic Commerce Investigation Benchmark — V2

This package is a minimal second version of the frozen controlled pilot. It preserves the research question, domain, 20 semantic invariants, SIPR metric, and implementation-first versus semantic-first comparison while strengthening the fixtures against ceiling effects.

## Package use

- `generation/` contains the shared, condition-neutral source materials.
- `calibration_A/run_v2_001/` and `calibration_B/run_v2_002/` are the two upload-ready run packages. Give a generation agent only the files inside its assigned neutral run folder; do not expose parent folder names or any other package directory.
- `review/` contains the blind review prompt, reviewer contract, rubric, and review procedure.
- `researcher_private/` contains the only run-to-condition mapping and the run registry. Never provide it to generation agents or blind reviewers.

The `calibration_A` and `calibration_B` directory names are package-side storage labels only; experimental condition assignments are defined solely by `researcher_private/condition_mapping.json`.

Do not modify `schema.sql`, `seed.sql`, `TASK.md`, or (where present) `DOMAIN_CONTRACT.md` during generation. Do not run the experiment or score outputs as part of package preparation.

