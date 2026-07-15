# agent/

The core loop. Invoked by the GitHub Action as
`python agent/main.py --pr-number N` (see
`.github/workflows/downstream-impact-guardian-check.yml`).

## Pipeline (CLAUDE.md steps 1–6)

| Step | Module | Notes |
|---|---|---|
| 1. Schema+logic detection | `dbt_state.py` | prod manifest (committed, ADR-0006) vs PR manifest (`dbt parse` in CI); column diff + rename heuristic + normalized-SQL logic diff |
| 2. Semantic drift | `dbt_state.diff_glossary` | PR's `business_glossary.yml` vs the term definition live in DataHub |
| 3. Blast radius | `datahub_client.py` + `blast_radius.py` | lineage + observed queries from DataHub; deterministic, inspectable scoring |
| 4. Writeback 1 | `contract.py` | Data Contract: `upsertDataContract`, SDK-emission fallback, PROPOSED status (ADR-0003) |
| 5. Codegen | `codegen.py` | deterministic, mergeable `*_compat` / `*_legacy` views + schema.yml (ADR-0002) |
| 6. Writeback 2 | `pr_comment.py` | idempotent PR comment + `$GITHUB_STEP_SUMMARY` mirror |

`adk_agent.py` (live mode only): a Google ADK `Agent` with read-only DataHub
tools rewrites the impact narrative; scoring and code generation never
depend on the LLM.

## Modes (ADR-0007)

- **live** — `DATAHUB_GMS_URL` + `DATAHUB_GMS_TOKEN` present.
- **offline** — no secrets (e.g. fork PRs): committed `fixtures/*.json`
  stand in for DataHub; the full comment still renders and lands in the
  step summary. Fixtures ARE the offline product surface, not test doubles.

## Run locally

```bash
pip install -r agent/requirements.txt
python -m pytest agent/tests/ -q          # 21 tests, no network
python agent/main.py --pr-number 1 --mode offline --no-post \
  --pr-manifest dbt_demo_project/prod_state/manifest.json
```
