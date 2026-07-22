from agent import blast_radius
from agent.models import (ColumnChange, Consumer, GlossaryChange, ModelChange,
                          QueryUsage)


def _breaking_change():
    ch = ModelChange(model_name="fct_orders",
                     unique_id="model.fiction_retail.fct_orders")
    ch.kinds.add("schema")
    ch.renames.append(("order_total", "order_amount_usd"))
    return ch


def test_breaking_change_with_real_consumers_is_critical():
    consumers = {"fct_orders": [
        Consumer(name="revenue_daily", platform="bigquery", entity_type="dataset"),
        Consumer(name="customer_ltv", platform="bigquery", entity_type="dataset"),
        Consumer(name="Finance KPIs", platform="looker", entity_type="dashboard"),
    ]}
    queries = {"fct_orders": [
        QueryUsage(sql="SELECT SUM(order_total) FROM fct_orders"),
    ]}
    report = blast_radius.assess([_breaking_change()], [], consumers, queries)
    # 3 breaking + 3 consumers + 2 external platform + 3 query hit = 11
    assert report.score == 11
    assert report.severity == "CRITICAL"
    assert queries["fct_orders"][0].references_changed_column


def test_query_not_referencing_changed_column_scores_lower():
    queries = {"fct_orders": [QueryUsage(sql="SELECT order_id FROM fct_orders")]}
    report = blast_radius.assess([_breaking_change()], [], {}, queries)
    assert not queries["fct_orders"][0].references_changed_column
    assert report.score == 3  # breaking only


def test_deleted_model_breaks_every_observed_query():
    ch = ModelChange(model_name="fct_orders",
                     unique_id="model.f.fct_orders", kinds={"removed"},
                     old_columns=["order_id", "order_total"])
    queries = {"fct_orders": [
        QueryUsage(sql="SELECT * FROM some_alias LIMIT 5"),  # no column token
        QueryUsage(sql="SELECT COUNT(*) FROM t"),            # no column token
    ]}
    report = blast_radius.assess([ch], [], {}, queries)
    assert all(q.references_changed_column for q in queries["fct_orders"])
    assert "MODEL DELETED" in report.narrative
    # 3 breaking + 2 query hits * 3 = 9 -> CRITICAL
    assert report.severity == "CRITICAL"


def test_logic_only_no_consumers_is_low():
    ch = ModelChange(model_name="m", unique_id="model.x.m", kinds={"logic"})
    report = blast_radius.assess([ch], [], {}, {})
    assert report.severity == "LOW"


def test_semantic_drift_adds_weight_and_narrative():
    drift = GlossaryChange("Gross Revenue", "refunds included",
                           "refunds excluded")
    ch = ModelChange(model_name="revenue_daily",
                     unique_id="model.x.revenue_daily", kinds={"logic"})
    report = blast_radius.assess([ch], [drift], {}, {})
    assert report.score == 3  # 1 logic + 2 drift
    assert report.severity == "MEDIUM"
    assert "Gross Revenue" in report.narrative


def test_impact_classification_worst_wins():
    from agent.blast_radius import classify_impact
    broken = ModelChange(model_name="a", unique_id="m.a", kinds={"removed"})
    drift = ModelChange(model_name="b", unique_id="m.b", kinds={"logic"})
    assert classify_impact(broken) == "BROKEN"
    assert classify_impact(drift) == "DISTORTED"
    # production shape: SEPARATE instances of the same entity per model
    inst_a = Consumer(name="Dash", platform="looker", entity_type="dashboard",
                      urn="urn:li:dashboard:(looker,dash)", owners=["bi@x"])
    inst_b = Consumer(name="Dash", platform="looker", entity_type="dashboard",
                      urn="urn:li:dashboard:(looker,dash)")
    consumers = {"a": [inst_a], "b": [inst_b]}
    blast_radius.assess([drift, broken], [], consumers, {})
    assert inst_a.impact == "BROKEN" and inst_b.impact == "BROKEN"
    assert inst_a.owners == inst_b.owners == ["bi@x"]  # owners unioned too


def test_declared_deps_fact_verdicts():
    from agent.blast_radius import classify_declared_impact
    ch = ModelChange(model_name="fct_orders", unique_id="m.f", kinds={"schema"})
    ch.renames = [("order_total", "order_amount_usd")]
    ch.columns = [ColumnChange("order_total", "removed"),
                  ColumnChange("order_amount_usd", "added")]
    assert classify_declared_impact(ch, ["order_total"]) == "BROKEN"
    assert classify_declared_impact(ch, ["order_id", "order_status"]) == "SAFE"
    deleted = ModelChange(model_name="m", unique_id="m.m", kinds={"removed"})
    assert classify_declared_impact(deleted, ["anything"]) == "BROKEN"
    drift = ModelChange(model_name="r", unique_id="m.r", kinds={"logic"})
    assert classify_declared_impact(drift, ["order_id"]) == "DISTORTED"  # filter change hits all
    drift.changed_expressions = ["gross_revenue"]
    assert classify_declared_impact(drift, ["order_id"]) == "SAFE"
    assert classify_declared_impact(drift, ["gross_revenue"]) == "DISTORTED"


def test_declared_consumer_gets_safe_in_assess():
    ch = _breaking_change()
    safe_c = Consumer(name="ops_snapshot", platform="bigquery",
                      entity_type="dataset",
                      declared_deps={"fct_orders": ["order_id"]})
    hit_c = Consumer(name="ltv", platform="bigquery", entity_type="dataset",
                     declared_deps={"fct_orders": ["order_total"]})
    report = blast_radius.assess([ch], [], {"fct_orders": [safe_c, hit_c]}, {})
    assert safe_c.impact == "SAFE"
    assert hit_c.impact == "BROKEN"
