from agent import contract
from agent.datahub_client import FixtureDataHubClient


def test_payload_bundles_existing_assertions():
    reader = FixtureDataHubClient()
    assertions = reader.get_assertions("fct_orders")
    payload = contract.build_contract_input(
        reader.get_dataset_urn("fct_orders"), assertions,
        "https://github.com/x/y/pull/1")
    assert payload["entityUrn"].endswith("fct_orders,PROD)")
    urns = [s["assertionUrn"] for s in payload["schema"]]
    assert "urn:li:assertion:fct_orders.unique_order_id" in urns
    props = {p["key"]: p["value"] for p in payload["properties"]}
    assert props["status"] == "PROPOSED"
    assert props["proposedBy"] == "downstream-impact-guardian"


def test_offline_mode_records_payload_without_writing():
    result = contract.write_contract(None, "urn:li:dataset:x", [],
                                     "https://github.com/x/y/pull/1",
                                     offline=True)
    assert result.mode == "recorded-offline"
    assert result.urn is None
    assert result.payload["entityUrn"] == "urn:li:dataset:x"


def test_live_mode_without_assertions_refuses_honestly():
    result = contract.write_contract(None, "urn:li:dataset:x", [],
                                     "pr", offline=False)
    assert result.mode == "failed"
    assert "must bundle existing assertions" in result.note
