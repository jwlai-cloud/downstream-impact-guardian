from agent import blast_radius, codegen, pr_comment
from agent.models import (ColumnChange, ContractResult, GlossaryChange,
                          Consumer, ModelChange, QueryUsage)


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
                              note="No DataHub credentials in this run")
    body = pr_comment.render(report, contract, arts, mode="offline")
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
                              payload={})
    body = pr_comment.render(report, contract, [], mode="live")
    assert "urn:li:dataContract:abc" in body
    assert "offline fixture mode" not in body
