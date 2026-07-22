from agent import blast_radius, codegen, pr_comment
from agent.models import (ColumnChange, ContractResult, GlossaryChange,
                          Consumer, ModelChange, QueryUsage, SuspectedDrift)


def _report():
    ch = ModelChange(model_name="fct_orders",
                     unique_id="model.f.fct_orders", kinds={"schema"},
                     old_columns=["order_id", "order_total"])
    ch.columns = [ColumnChange("order_total", "removed"),
                  ColumnChange("order_amount_usd", "added")]
    ch.renames = [("order_total", "order_amount_usd")]
    consumers = {"fct_orders": [Consumer(name="Finance KPIs",
                                         platform="looker",
                                         entity_type="dashboard")]}
    queries = {"fct_orders": [QueryUsage(
        sql="SELECT SUM(order_total) FROM fct_orders",
        user="finance@corp", platform="bigquery")]}
    drift = GlossaryChange("Gross Revenue", "refunds included",
                           "refunds excluded")
    return blast_radius.assess([ch], [drift], consumers, queries), ch


def test_render_contains_all_sections_and_marker():
    report, ch = _report()
    arts = codegen.generate_all([ch])
    contract = ContractResult(mode="recorded-offline", urn=None,
                              payload={"entityUrn": "urn:li:dataset:x"},
                              note="No DataHub credentials in this run",
                              model_name="fct_orders")
    body = pr_comment.render(report, [contract], arts, mode="offline")
    assert pr_comment.MARKER in body
    assert "offline fixture mode" in body
    assert "`order_total` → `order_amount_usd`" in body
    assert "Finance KPIs" in body
    assert "Queries that WILL break" in body
    assert "Semantic drift" in body
    assert "Data Contract" in body
    assert "fct_orders_compat" in body
    assert "```sql" in body


def test_render_live_contract_shows_urn():
    report, ch = _report()
    contract = ContractResult(mode="upserted",
                              urn="urn:li:dataContract:abc",
                              payload={}, model_name="fct_orders")
    body = pr_comment.render(report, [contract], [], mode="live")
    assert "urn:li:dataContract:abc" in body
    assert "offline fixture mode" not in body


def test_render_suspected_drift_and_multiple_contracts():
    report, ch = _report()
    report.suspected_drifts = [SuspectedDrift(
        term_name="Gross Revenue", model_name="revenue_daily",
        column="gross_revenue", live_definition="refunds included")]
    contracts = [
        ContractResult(mode="upserted", urn="urn:li:dataContract:a",
                       payload={}, model_name="fct_orders"),
        ContractResult(mode="upserted", urn="urn:li:dataContract:b",
                       payload={}, model_name="revenue_daily"),
    ]
    body = pr_comment.render(report, contracts, [], mode="live")
    assert "⚠️ suspected" in body
    assert "revenue_daily.gross_revenue" in body
    assert "urn:li:dataContract:a" in body
    assert "urn:li:dataContract:b" in body


def test_render_deleted_model_marker():
    ch = ModelChange(model_name="revenue_daily",
                     unique_id="model.f.revenue_daily", kinds={"removed"},
                     old_columns=["order_date"])
    report = blast_radius.assess([ch], [], {}, {})
    body = pr_comment.render(report, [], [], mode="offline")
    assert "removed" in body
    assert "model deleted in this PR" in body


def test_render_no_contracts_says_so():
    report, ch = _report()
    body = pr_comment.render(report, [], [], mode="live")
    assert "no contract proposed" in body.lower()


def test_blast_radius_table_shows_impact_and_owners():
    ch = ModelChange(model_name="fct_orders",
                     unique_id="model.f.fct_orders", kinds={"schema"})
    ch.renames = [("order_total", "order_amount_usd")]
    consumers = {"fct_orders": [
        Consumer(name="Finance KPIs", platform="looker",
                 entity_type="dashboard",
                 owners=["finance-bi@fiction-retail.example"]),
        Consumer(name="Monthly Board Pack", platform="looker",
                 entity_type="dashboard", owners=[]),
    ]}
    report = blast_radius.assess([ch], [], consumers, {})
    body = pr_comment.render(report, [], [], mode="offline")
    assert "Worst-case impact" in body
    assert "🔴 BROKEN" in body
    assert "finance-bi@fiction-retail.example" in body
    assert "unowned" in body            # governance finding, never hidden
    assert "honest upper bound" in body


def test_slack_payload_and_gating(monkeypatch):
    ch = ModelChange(model_name="m", unique_id="model.f.m", kinds={"logic"})
    consumers = {"m": [Consumer(name="Dash", platform="looker",
                                entity_type="dashboard", owners=["bi@x"])]}
    report = blast_radius.assess([ch], [], consumers, {})
    payload = pr_comment.build_slack_payload(report, "https://pr/1")
    assert "DISTORTED: Dash (bi@x)" in payload["text"]
    # gating: LOW severity + no webhook -> no crash, no send
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
    pr_comment.notify_slack(report, "https://pr/1")
