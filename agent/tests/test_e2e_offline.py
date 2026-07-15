"""End-to-end offline run with the REAL committed prod manifest: simulates
the demo PR (rename + logic change + glossary drift) exactly as the GitHub
Action would see it, without any network access."""
import copy
import json

from agent import main as guardian
from conftest import REPO_ROOT

PROD_MANIFEST = REPO_ROOT / "dbt_demo_project" / "prod_state" / "manifest.json"


def _staged_pr_manifest():
    prod = json.loads(PROD_MANIFEST.read_text())
    pr = copy.deepcopy(prod)
    fct = pr["nodes"]["model.fiction_retail.fct_orders"]
    fct["columns"]["order_amount_usd"] = fct["columns"].pop("order_total")
    fct["raw_code"] = fct["raw_code"].replace(
        "o.order_total,", "o.order_total as order_amount_usd,")
    rev = pr["nodes"]["model.fiction_retail.revenue_daily"]
    rev["raw_code"] = rev["raw_code"].replace(
        "order_status != 'cancelled'",
        "order_status in ('completed', 'shipped')")
    return pr


def test_full_offline_run(tmp_path, monkeypatch):
    for var in ("DATAHUB_GMS_URL", "DATAHUB_GMS_TOKEN", "GITHUB_TOKEN",
                "GOOGLE_API_KEY", "GEMINI_API_KEY", "GITHUB_STEP_SUMMARY"):
        monkeypatch.delenv(var, raising=False)

    pr_manifest = tmp_path / "pr_manifest.json"
    pr_manifest.write_text(json.dumps(_staged_pr_manifest()))

    glossary = tmp_path / "business_glossary.yml"
    glossary.write_text("""
version: "1"
nodes:
  - name: Commerce Metrics
    terms:
      - name: Gross Revenue
        description: Sum of order_total over completed and shipped orders, refunds excluded.
""")

    out = tmp_path / "out"
    rc = guardian.run(guardian.parse_args([
        "--pr-number", "1",
        "--prod-manifest", str(PROD_MANIFEST),
        "--pr-manifest", str(pr_manifest),
        "--glossary", str(glossary),
        "--output-dir", str(out),
        "--no-post",
    ]))
    assert rc == 0

    comment = (out / "comment.md").read_text()
    assert "`order_total` → `order_amount_usd`" in comment
    assert "Finance KPIs" in comment                 # lineage blast radius
    assert "Queries that WILL break" in comment      # query usage cross-ref
    assert "Gross Revenue" in comment                # semantic drift
    assert "CRITICAL" in comment or "HIGH" in comment

    compat = (out / "fct_orders_compat.sql").read_text()
    assert "order_amount_usd as order_total" in compat
    legacy = (out / "revenue_daily_legacy.sql").read_text()
    assert "ref('fct_orders_compat')" in legacy

    payload = json.loads((out / "contract_payload.json").read_text())
    assert payload["entityUrn"].endswith("fct_orders,PROD)")


def test_no_change_pr_exits_quietly(tmp_path, monkeypatch):
    monkeypatch.delenv("DATAHUB_GMS_URL", raising=False)
    monkeypatch.delenv("DATAHUB_GMS_TOKEN", raising=False)
    out = tmp_path / "out"
    rc = guardian.run(guardian.parse_args([
        "--pr-number", "1",
        "--prod-manifest", str(PROD_MANIFEST),
        "--pr-manifest", str(PROD_MANIFEST),
        "--glossary", str(REPO_ROOT / "dbt_demo_project" / "datahub" /
                          "business_glossary.yml"),
        "--output-dir", str(out),
        "--no-post",
    ]))
    assert rc == 0
    assert not (out / "comment.md").exists()
