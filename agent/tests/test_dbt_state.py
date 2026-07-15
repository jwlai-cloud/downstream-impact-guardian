from agent import dbt_state
from agent.datahub_client import FixtureDataHubClient
from conftest import mk_manifest


def test_no_change_is_silent():
    m = mk_manifest([("fct_orders", ["a", "b"], "select a, b from t")])
    assert dbt_state.diff_manifests(m, m) == []


def test_cosmetic_sql_edit_not_logic_change():
    old = mk_manifest([("m", ["a"], "select a from t  -- old comment")])
    new = mk_manifest([("m", ["a"], "SELECT a\nFROM t")])
    assert dbt_state.diff_manifests(old, new) == []


def test_rename_detected_as_schema_change():
    old = mk_manifest([("fct_orders", ["order_id", "order_total"],
                        "select order_id, order_total from t")])
    new = mk_manifest([("fct_orders", ["order_id", "order_amount_usd"],
                        "select order_id, order_amount_usd from t")])
    changes = dbt_state.diff_manifests(old, new)
    assert len(changes) == 1
    ch = changes[0]
    assert "schema" in ch.kinds
    assert ch.renames == [("order_total", "order_amount_usd")]
    assert ch.breaking


def test_logic_only_change():
    old = mk_manifest([("revenue_daily", ["d", "rev"],
                        "select d, sum(x) as rev from t where s != 'cancelled' group by d")])
    new = mk_manifest([("revenue_daily", ["d", "rev"],
                        "select d, sum(x) as rev from t where s in ('completed') group by d")])
    changes = dbt_state.diff_manifests(old, new)
    assert len(changes) == 1
    assert changes[0].kinds == {"logic"}
    assert not changes[0].breaking


def test_new_model_is_additive():
    old = mk_manifest([("a", ["x"], "select x from t")])
    new = mk_manifest([("a", ["x"], "select x from t"),
                       ("b", ["y"], "select y from t")])
    assert dbt_state.diff_manifests(old, new) == []


def test_suspected_drift_when_glossary_forgotten():
    """Logic change on a term-bound model, no glossary edit in the PR."""
    import copy
    import json as _json
    from conftest import REPO_ROOT
    prod = _json.loads((REPO_ROOT / "dbt_demo_project" / "prod_state" /
                        "manifest.json").read_text())
    pr = copy.deepcopy(prod)
    pr["nodes"]["model.fiction_retail.revenue_daily"]["raw_code"] += "\n-- x"
    pr["nodes"]["model.fiction_retail.revenue_daily"]["raw_code"] = \
        pr["nodes"]["model.fiction_retail.revenue_daily"]["raw_code"].replace(
            "!= 'cancelled'", "in ('completed')")
    changes = dbt_state.diff_manifests(prod, pr)
    suspected = dbt_state.find_suspected_drifts(
        pr, changes, glossary_changes=[], reader=FixtureDataHubClient())
    assert len(suspected) == 1
    s = suspected[0]
    assert (s.term_name, s.model_name, s.column) == \
        ("Gross Revenue", "revenue_daily", "gross_revenue")
    assert "refunds included" in s.live_definition


def test_suspected_drift_suppressed_when_glossary_updated():
    from agent.models import GlossaryChange, ModelChange
    ch = ModelChange(model_name="revenue_daily",
                     unique_id="model.fiction_retail.revenue_daily",
                     kinds={"logic"})
    pr = {"nodes": {"model.fiction_retail.revenue_daily": {
        "name": "revenue_daily",
        "columns": {"gross_revenue":
                    {"meta": {"business_glossary_term": "Gross Revenue"}}}}}}
    updated = [GlossaryChange("Gross Revenue", "old", "new")]
    assert dbt_state.find_suspected_drifts(
        pr, [ch], updated, FixtureDataHubClient()) == []


def test_glossary_drift_against_live_datahub(tmp_path):
    g = tmp_path / "glossary.yml"
    g.write_text("""
version: "1"
nodes:
  - name: Commerce Metrics
    terms:
      - name: Gross Revenue
        description: Sum of order_total over completed orders only, refunds excluded.
      - name: Active Customer
        description: >
          A customer with at least one non-cancelled order in the trailing
          90 days.
""")
    changes = dbt_state.diff_glossary(g, FixtureDataHubClient())
    assert [c.term_name for c in changes] == ["Gross Revenue"]
    assert "refunds included" in changes[0].live_definition
    assert "refunds excluded" in changes[0].proposed_definition
