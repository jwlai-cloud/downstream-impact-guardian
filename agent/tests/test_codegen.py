from agent import codegen
from agent.models import ColumnChange, ModelChange


def _rename_change():
    ch = ModelChange(
        model_name="fct_orders", unique_id="model.f.fct_orders",
        kinds={"schema"},
        old_columns=["order_id", "order_total", "currency"],
    )
    ch.columns = [ColumnChange("order_total", "removed"),
                  ColumnChange("order_amount_usd", "added")]
    ch.renames = [("order_total", "order_amount_usd")]
    return ch


def test_compat_view_maps_rename_and_is_valid_dbt():
    art = codegen.generate_compat_view(_rename_change())
    assert art.view_name == "fct_orders_compat"
    assert "order_amount_usd as order_total" in art.sql
    assert "{{ ref('fct_orders') }}" in art.sql
    assert not art.requires_human
    # last select item must not carry a trailing comma
    select_block = art.sql.split("select\n")[1].split("\nfrom")[0]
    assert not select_block.rstrip().endswith(",")
    assert "name: order_total" in art.schema_yml
    assert "not_null" in art.schema_yml


def test_removed_column_without_mapping_flags_human():
    ch = ModelChange(model_name="m", unique_id="model.f.m", kinds={"schema"},
                     old_columns=["a", "b", "c"])
    ch.columns = [ColumnChange("b", "removed"), ColumnChange("c", "removed")]
    art = codegen.generate_compat_view(ch)
    assert art.requires_human
    assert art.sql.count("cast(null as string)") == 2
    assert "fix me" in art.sql


def test_legacy_view_carries_old_sql_and_retargets_refs():
    ch = ModelChange(
        model_name="revenue_daily", unique_id="model.f.revenue_daily",
        kinds={"logic"},
        old_sql="select order_date, sum(order_total) as gross_revenue\n"
                "from {{ ref('fct_orders') }}\nwhere order_status != 'cancelled'\n"
                "group by order_date",
        new_sql="different",
    )
    arts = codegen.generate_all([_rename_change(), ch])
    names = [a.view_name for a in arts]
    assert names == ["fct_orders_compat", "revenue_daily_legacy"]
    legacy = arts[1]
    # the old SQL must keep compiling even though fct_orders was reshaped
    assert "ref('fct_orders_compat')" in legacy.sql
    assert "!= 'cancelled'" in legacy.sql


def test_deleted_model_gets_legacy_view():
    ch = ModelChange(
        model_name="fct_orders", unique_id="model.f.fct_orders",
        kinds={"removed"},
        old_sql="select order_id, order_total from {{ ref('stg_orders') }}",
        old_columns=["order_id", "order_total"],
    )
    arts = codegen.generate_all([ch])
    assert [a.view_name for a in arts] == ["fct_orders_legacy"]
    assert "select order_id, order_total" in arts[0].sql
    assert "DELETES the model" in arts[0].schema_yml


def test_deleted_model_without_sql_gets_nothing():
    ch = ModelChange(model_name="m", unique_id="model.f.m",
                     kinds={"removed"}, old_sql="")
    assert codegen.generate_all([ch]) == []


def test_schema_plus_logic_change_gets_compat_not_legacy():
    ch = _rename_change()
    ch.kinds.add("logic")
    arts = codegen.generate_all([ch])
    assert [a.view_name for a in arts] == ["fct_orders_compat"]
