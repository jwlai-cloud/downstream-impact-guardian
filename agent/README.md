# agent/

ADK (or LangChain, see CLAUDE.md) agent code goes here.

Core logic to build, in order:
1. Parse dbt `state:modified` output → what changed (schema and/or logic)
2. Query DataHub (read-only) for lineage + query history on the affected
   table(s) → who's actually downstream, right now
3. Query DataHub for glossary term version diffs if a semantic definition
   changed
4. Propose a Data Contract back to DataHub (writeback #1) — see
   docs/SPEC.md section 5-6 for the exact mutation and why it's proposed
   rather than upserted directly
5. Generate the compatibility artifact (SQL view / dbt macro + tests)
6. Post the PR comment (writeback #2), referencing the contract from step 4

Entry point should be invocable as: `python agent/main.py --pr-number N`
so the GitHub Action can call it directly (see
`.github/workflows/downstream-impact-guardian-check.yml`).
