#!/usr/bin/env bash
# Refresh the committed last-known-production manifest (ADR-0006).
# Run from repo root on master after every merge that touches dbt_demo_project/.
set -euo pipefail
cd "$(dirname "$0")/../dbt_demo_project"
DBT_PROFILES_DIR=. dbt parse --no-partial-parse
cp target/manifest.json prod_state/manifest.json
echo "prod_state/manifest.json refreshed — commit it."
