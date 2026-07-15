#!/usr/bin/env bash
# One-shot data prep: build the dbt project in BigQuery and ingest
# everything into DataHub. Instance-agnostic — the same script populated
# the local quickstart and populates the judge-facing instance.
#
# Required env:
#   DATAHUB_GMS_URL      e.g. http://localhost:8080 or http://<vm-ip>:8080
# Optional env:
#   DATAHUB_GMS_TOKEN    required once METADATA_SERVICE_AUTH_ENABLED=true
#   GCP_PROJECT          default agent-era
#   BQ_DATASET           default fiction_retail
#   BQ_ACCOUNT           gcloud account to mint a BigQuery token for
#                        (default: the active gcloud account); uses the dbt
#                        'token' target so your ADC stays untouched
#
# Prereqs on the machine running this: dbt-bigquery + acryl-datahub[dbt]
# installed, gcloud authenticated for $BQ_ACCOUNT.
set -euo pipefail
cd "$(dirname "$0")/.."

: "${DATAHUB_GMS_URL:?set DATAHUB_GMS_URL first}"
export DATAHUB_GMS_TOKEN="${DATAHUB_GMS_TOKEN:-}"
export GCP_PROJECT="${GCP_PROJECT:-agent-era}"
export BQ_DATASET="${BQ_DATASET:-fiction_retail}"
BQ_ACCOUNT="${BQ_ACCOUNT:-$(gcloud config get-value account 2>/dev/null)}"

echo "==> BigQuery build in ${GCP_PROJECT}.${BQ_DATASET} (as ${BQ_ACCOUNT})"
export BQ_ACCESS_TOKEN
BQ_ACCESS_TOKEN=$(gcloud auth print-access-token --account="${BQ_ACCOUNT}")
pushd dbt_demo_project >/dev/null
export DBT_PROFILES_DIR=.
dbt seed --target token -q
dbt build --target token -q
dbt docs generate --target token -q
# dbt test LAST: docs generate overwrites run_results.json with an entry
# the DataHub source skips — without this, no assertions ingest.
dbt test --target token -q
popd >/dev/null

echo "==> Ingest glossary (versioned on re-run) -> ${DATAHUB_GMS_URL}"
datahub ingest -c dbt_demo_project/datahub/glossary_ingest.yml

echo "==> Ingest dbt project (models, lineage, tests->assertions)"
datahub ingest -c dbt_demo_project/datahub/dbt_ingest.yml

echo "==> Refresh committed prod manifest (commit if changed)"
cp dbt_demo_project/target/manifest.json dbt_demo_project/prod_state/manifest.json

echo "Done. Check ${DATAHUB_GMS_URL%:8080}:9002 -> lineage on fct_orders."
