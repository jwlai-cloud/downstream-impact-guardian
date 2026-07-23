#!/usr/bin/env python3
"""Seed the demo catalog with the cross-team consumer layer.

The dbt + BigQuery ingestion gives DataHub the in-repo lineage only. The
demo story — and any real deployment — has consumers the repo can't see:
other teams' tables, BI dashboards, scheduled queries. This script emits
that layer (honestly mocked, clearly fictional) so live mode carries the
same story the fixtures do:

- marketing.customer_ltv  (declares depends_on_columns -> BROKEN-as-fact)
- ops.open_orders_snapshot (declares columns it does NOT read -> SAFE)
- Looker dashboards Finance KPIs (owned) + Monthly Board Pack (unowned ->
  surfaced as a governance finding)
- observed queries still referencing fct_orders.order_total
- ownership on revenue_daily

Usage:
  DATAHUB_GMS_URL=http://localhost:8080 [DATAHUB_GMS_TOKEN=...] \
    python3 scripts/seed_demo_consumers.py
"""
import json
import os
import time
import urllib.request

GMS = os.environ.get("DATAHUB_GMS_URL", "http://localhost:8080").rstrip("/")
TOKEN = os.environ.get("DATAHUB_GMS_TOKEN", "")
NOW = int(time.time() * 1000)
ACTOR = "urn:li:corpuser:datahub"
AUDIT = {"time": NOW, "actor": ACTOR}

BQ = "urn:li:dataPlatform:bigquery"
FCT = f"urn:li:dataset:({BQ},agent-era.fiction_retail.fct_orders,PROD)"
REV = f"urn:li:dataset:({BQ},agent-era.fiction_retail.revenue_daily,PROD)"
LTV = f"urn:li:dataset:({BQ},agent-era.marketing.customer_ltv,PROD)"
OPS = f"urn:li:dataset:({BQ},agent-era.ops.open_orders_snapshot,PROD)"
DASH_KPI = "urn:li:dashboard:(looker,finance_kpis)"
DASH_BOARD = "urn:li:dashboard:(looker,board_pack)"


def preflight() -> None:
    """Fail fast with a clear message — this is a manual, maintainer-side
    tool (never part of the Action/agent path, which has its own offline
    mode). Default target is the documented local quickstart."""
    try:
        req = urllib.request.Request(f"{GMS}/health")
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp.read()
    except Exception as e:
        raise SystemExit(
            f"Cannot reach DataHub GMS at {GMS} ({e}).\n"
            "Set DATAHUB_GMS_URL to your instance (and DATAHUB_GMS_TOKEN "
            "if metadata auth is enabled), or start the local quickstart.")


def get_ownership_owners(urn: str) -> list[dict]:
    """Current owners of an entity (empty if none) — so seeding merges
    instead of clobbering pre-existing ownership."""
    from urllib.parse import quote
    req = urllib.request.Request(
        f"{GMS}/aspects/{quote(urn, safe='')}?aspect=ownership&version=0",
        headers={**({"Authorization": f"Bearer {TOKEN}"} if TOKEN else {})})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = json.loads(resp.read())
        return (body.get("aspect", {}).get("com.linkedin.common.Ownership", {})
                .get("owners", []))
    except Exception:
        return []


def emit(entity_type: str, urn: str, aspect_name: str, aspect: dict) -> None:
    body = json.dumps({
        "proposal": {
            "entityType": entity_type,
            "entityUrn": urn,
            "changeType": "UPSERT",
            "aspectName": aspect_name,
            "aspect": {
                "contentType": "application/json",
                "value": json.dumps(aspect),
            },
        }
    }).encode()
    req = urllib.request.Request(
        f"{GMS}/aspects?action=ingestProposal", data=body,
        headers={"Content-Type": "application/json",
                 **({"Authorization": f"Bearer {TOKEN}"} if TOKEN else {})},
        method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        resp.read()
    print(f"  {aspect_name:<20} {urn}")


def ownership(*emails: str, merge_urn: str | None = None) -> dict:
    """Ownership aspect; pass merge_urn for entities that may already have
    owners (aspect UPSERT replaces wholesale — never clobber)."""
    existing = get_ownership_owners(merge_urn) if merge_urn else []
    have = {o.get("owner") for o in existing}
    new = [{"owner": f"urn:li:corpuser:{e}", "type": "TECHNICAL_OWNER"}
           for e in emails if f"urn:li:corpuser:{e}" not in have]
    return {"owners": existing + new, "lastModified": AUDIT}


def upstream(*urns: str) -> dict:
    return {"upstreams": [
        {"auditStamp": AUDIT, "dataset": u, "type": "TRANSFORMED"}
        for u in urns]}


preflight()
print("datasets:")
emit("dataset", LTV, "datasetProperties", {
    "name": "customer_ltv",
    "description": "Marketing's LTV feature table (fictional demo asset).",
    "customProperties": {
        "depends_on_columns.fct_orders": "order_total,customer_id",
        "demo": "fiction-retail"}})
emit("dataset", LTV, "ownership",
     ownership("marketing-analytics@fiction-retail.example"))
emit("dataset", LTV, "upstreamLineage", upstream(FCT))

emit("dataset", OPS, "datasetProperties", {
    "name": "open_orders_snapshot",
    "description": "Ops snapshot; declares the columns it reads (fictional).",
    "customProperties": {
        "depends_on_columns.fct_orders": "order_id,order_status",
        "demo": "fiction-retail"}})
emit("dataset", OPS, "ownership", ownership("ops-eng@fiction-retail.example"))
emit("dataset", OPS, "upstreamLineage", upstream(FCT))

emit("dataset", REV, "ownership",
     ownership("data-team@fiction-retail.example", merge_urn=REV))

# Declares it reads ONLY order_date from revenue_daily — a metric
# redefinition there leaves it untouched, earning the 🟢 SAFE verdict.
XDD = f"urn:li:dataset:({BQ},agent-era.finance_ops.exec_daily_digest,PROD)"
emit("dataset", XDD, "datasetProperties", {
    "name": "exec_daily_digest",
    "description": "Finance-ops daily email extract; reads dates only "
                   "(fictional demo asset).",
    "customProperties": {
        "depends_on_columns.revenue_daily": "order_date",
        "demo": "fiction-retail"}})
emit("dataset", XDD, "ownership",
     ownership("finance-ops@fiction-retail.example"))
emit("dataset", XDD, "upstreamLineage", upstream(REV))

print("dashboards:")
emit("dashboard", DASH_KPI, "dashboardInfo", {
    "title": "Finance KPIs",
    "description": "Board-level finance dashboard (fictional demo asset).",
    "datasetEdges": [{"destinationUrn": REV, "created": AUDIT},
                     {"destinationUrn": FCT, "created": AUDIT}],
    "lastModified": {"created": AUDIT, "lastModified": AUDIT}})
emit("dashboard", DASH_KPI, "ownership",
     ownership("finance-bi@fiction-retail.example"))
emit("dashboard", DASH_BOARD, "dashboardInfo", {
    "title": "Monthly Board Pack",
    "description": "Monthly board reporting (fictional demo asset). "
                   "Deliberately unowned: the guardian surfaces it.",
    "datasetEdges": [{"destinationUrn": REV, "created": AUDIT}],
    "lastModified": {"created": AUDIT, "lastModified": AUDIT}})

print("observed queries:")
QUERIES = [
    ("dig-usage-fct-1",
     "SELECT order_date, SUM(order_total) AS revenue\n"
     "FROM `agent-era.fiction_retail.fct_orders`\n"
     "WHERE order_status = 'completed'\nGROUP BY order_date", FCT),
    ("dig-usage-fct-2",
     "SELECT customer_id, AVG(order_total) AS aov\n"
     "FROM `agent-era.fiction_retail.fct_orders`\nGROUP BY customer_id", FCT),
    ("dig-usage-rev-1",
     "SELECT order_date, gross_revenue\n"
     "FROM `agent-era.fiction_retail.revenue_daily`\n"
     "ORDER BY order_date DESC LIMIT 90", REV),
]
for qid, sql, subject in QUERIES:
    qurn = f"urn:li:query:{qid}"
    emit("query", qurn, "queryProperties", {
        "statement": {"value": sql, "language": "SQL"},
        "source": "SYSTEM",
        "created": AUDIT,
        "lastModified": AUDIT})
    emit("query", qurn, "querySubjects",
         {"subjects": [{"entity": subject}]})

print("done.")
