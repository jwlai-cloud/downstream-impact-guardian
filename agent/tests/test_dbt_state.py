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


def test_deleted_model_detected_as_breaking():
    old = mk_manifest([("fct_orders", ["order_id", "order_total"],
                        "select order_id, order_total from t"),
                       ("keeper", ["x"], "select x from t")])
    new = mk_manifest([("keeper", ["x"], "select x from t")])
    changes = dbt_state.diff_manifests(old, new)
    assert len(changes) == 1
    ch = changes[0]
    assert ch.model_name == "fct_orders"
    assert ch.kinds == {"removed"}
    assert ch.breaking
    assert ch.old_columns == ["order_id", "order_total"]
    assert "order_total" in ch.old_sql


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


def test_expression_diff_attributes_changed_columns():
    """Only avg_order_value's formula changes -> attributed per column."""
    old = mk_manifest([("revenue_daily", ["order_date", "gross_revenue", "avg_order_value"],
        "select order_date, sum(order_total) as gross_revenue, "
        "avg(order_total) as avg_order_value "
        "from {{ ref('fct_orders') }} group by order_date")])
    new = mk_manifest([("revenue_daily", ["order_date", "gross_revenue", "avg_order_value"],
        "select order_date, sum(order_total) as gross_revenue, "
        "sum(order_total) / nullif(count(distinct customer_id), 0) as avg_order_value "
        "from {{ ref('fct_orders') }} group by order_date")])
    changes = dbt_state.diff_manifests(old, new)
    assert changes[0].kinds == {"logic"}
    assert changes[0].changed_expressions == ["avg_order_value"]


def test_where_only_change_has_no_expression_attribution():
    """Filter change alters every column's VALUES but no expression —
    changed_expressions stays empty, logic change still detected."""
    old = mk_manifest([("revenue_daily", ["d", "rev"],
        "select d, sum(x) as rev from {{ ref('t') }} "
        "where s != 'cancelled' group by d")])
    new = mk_manifest([("revenue_daily", ["d", "rev"],
        "select d, sum(x) as rev from {{ ref('t') }} "
        "where s in ('completed', 'shipped') group by d")])
    changes = dbt_state.diff_manifests(old, new)
    assert changes[0].kinds == {"logic"}
    assert changes[0].changed_expressions == []


def test_unparseable_sql_degrades_gracefully():
    assert dbt_state._column_expressions("{% macro weird %} not sql at all (((") is None
    assert dbt_state._diff_expressions("((broken", "select 1 as a from t") == []


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


def test_resolve_narrative_model():
    from agent.adk_agent import resolve_model
    assert resolve_model(None) == "gemini-flash-latest"
    assert resolve_model("gemini-2.5-pro") == "gemini-2.5-pro"
    # non-gemini ids require the LiteLLM adapter (import may be absent in
    # the offline test env — either outcome proves the routing)
    try:
        m = resolve_model("openai/gpt-4o-mini")
        assert type(m).__name__ == "LiteLlm"
    except ImportError:
        pass


def test_parse_declared_deps_variants():
    from agent.datahub_client import parse_declared_deps
    assert parse_declared_deps(
        {"depends_on_columns": '{"fct_orders": ["order_total"]}'}
    ) == {"fct_orders": ["order_total"]}
    assert parse_declared_deps(
        {"depends_on_columns.fct_orders": "['order_id', 'order_date']"}
    ) == {"fct_orders": ["order_id", "order_date"]}
    assert parse_declared_deps(
        {"depends_on_columns.fct_orders": "order_id, order_date"}
    ) == {"fct_orders": ["order_id", "order_date"]}
    assert parse_declared_deps({"unrelated": "x"}) == {}
    assert parse_declared_deps({"depends_on_columns": "not json ["}) == {}


def test_validate_narrative_config(monkeypatch):
    from agent.adk_agent import validate_narrative_config as v
    monkeypatch.delenv("GUARDIAN_NARRATIVE_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    # nothing configured -> fine (labeled template narrative)
    assert v("") is None
    # gemini model without a Google key -> actionable error
    monkeypatch.setenv("GUARDIAN_NARRATIVE_MODEL", "gemini-flash-latest")
    assert "GOOGLE_API_KEY" in v("")
    assert v("some-google-key") is None
    # OpenAI-compatible model without OPENAI_API_KEY -> actionable error
    monkeypatch.setenv("GUARDIAN_NARRATIVE_MODEL", "openai/qwen3.6-flash")
    assert "OPENAI_API_KEY" in v("")
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    assert v("") is None


def test_validate_narrative_config_openai_key_without_model(monkeypatch):
    from agent.adk_agent import validate_narrative_config as v
    monkeypatch.delenv("GUARDIAN_NARRATIVE_MODEL", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    # OpenAI key alone would silently target the Gemini default -> error
    assert "GUARDIAN_NARRATIVE_MODEL" in v("")
    # ...unless a Google key exists for the Gemini default
    assert v("google-key") is None
