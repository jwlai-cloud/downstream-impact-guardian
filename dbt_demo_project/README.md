# dbt_demo_project/ — fiction-retail on BigQuery

The one-time data prep pipeline (see ADR-0001 for the dataset choice).
Lineage: seeds → `stg_customers`/`stg_orders` → `fct_orders` → `revenue_daily`.

## Layout

- `seeds/` — deterministic fiction-retail CSVs (regenerate with
  `python scripts/generate_seed_data.py`; fixed RNG seed, identical output)
- `models/staging/`, `models/marts/` — 4 models, tests + column docs;
  glossary terms attached via column `config.meta.business_glossary_term`
- `profiles.yml` — env-var driven BigQuery profile, no credentials; `dbt
  parse`/`ls` work with defaults (no connection opened)
- `prod_state/manifest.json` — committed last-known-production manifest;
  the PR check diffs against this (ADR-0006). Refresh on every master
  merge: `scripts/refresh_prod_state.sh`
- `datahub/` — ingestion recipes: `dbt_ingest.yml` (models + tests →
  assertions), `glossary_ingest.yml` (`business_glossary.yml` → glossary
  terms, versioned on re-ingest)

## One-time prep sequence (against a real BigQuery sandbox + DataHub)

```bash
export GCP_PROJECT=... BQ_DATASET=fiction_retail
export DATAHUB_GMS_URL=... DATAHUB_GMS_TOKEN=...
cd dbt_demo_project
dbt seed && dbt build && dbt docs generate && dbt test
# ^ `docs generate` OVERWRITES run_results.json with a non-build entry the
#   DataHub source skips — run `dbt test` (or build) LAST so assertions ingest
datahub ingest -c datahub/glossary_ingest.yml     # glossary terms (v1)
datahub ingest -c datahub/dbt_ingest.yml          # models, lineage, assertions
```

Run the ingest twice across two states if you want non-empty Timeline
history (stage a small change on master between runs).

NEVER ingest from a PR branch — DataHub only ever reflects reality
(CLAUDE.md).
