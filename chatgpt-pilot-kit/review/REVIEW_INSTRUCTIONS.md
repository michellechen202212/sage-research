# Reviewer workflow

For each first-pass output:

1. Start a fresh ChatGPT conversation.
2. Upload the generated output plus the three reviewer files in this directory.
3. Paste `PROMPT.md`.
4. Use only an opaque run ID (run_001, etc.). Do not reveal A/B condition.
5. Save the completed review as `blind_review_<run_id>.md`.
6. Do not repair anything until all four first-pass reviews are complete.
7. Only then consult `researcher_private/condition_mapping.json`.
