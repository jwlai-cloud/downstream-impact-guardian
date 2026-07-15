# dbt_demo_project/

The one-time data prep pipeline. See docs/SPEC.md section 9 and CLAUDE.md
"Open questions" for dataset choice (nyc-taxi vs fiction-retail).

Needs, once dataset is chosen:
- BigQuery sandbox connection profile
- 3-4 models (bronze/silver/gold pattern)
- One deliberate schema change and one deliberate logic change staged
  across two ingestion runs, so DataHub's history isn't empty when the
  demo runs
- `datahub ingest` recipe (dbt source) to push manifest.json + catalog.json
  into DataHub

This is prep, not something that runs live during judging — see
docs/SPEC.md section 9 and the prep-phase / runtime-phase distinction
discussed during design.
