"""Writeback #1: a Data Contract into DataHub.

Verified 2026-07-15 (SPEC §11): proposeDataContract / the proposal inbox is
DataHub Cloud-only. On self-hosted OSS we try upsertDataContract; if the
mutation is absent we fall back to emitting dataContractProperties via the
acryl-datahub SDK. Either way the contract carries PROPOSED provenance and
the human approval gate is the PR merge itself.
"""
from __future__ import annotations

from agent.models import ContractResult

UPSERT_MUTATION = """
mutation upsert($input: UpsertDataContractInput!) {
  upsertDataContract(input: $input) { urn }
}
"""


def build_contract_input(entity_urn: str, assertions: list[dict],
                         pr_url: str) -> dict:
    schema_assertions = [a for a in assertions
                         if "unique" in a.get("description", "").lower()
                         or "not_null" in a.get("description", "").lower()
                         or a.get("type", "").upper() in ("DATASET", "FIELD")]
    quality_assertions = [a for a in assertions if a not in schema_assertions]
    contract_input: dict = {"entityUrn": entity_urn}
    if schema_assertions:
        contract_input["schema"] = [{"assertionUrn": a["urn"]}
                                    for a in schema_assertions]
    if quality_assertions:
        contract_input["dataQuality"] = [{"assertionUrn": a["urn"]}
                                         for a in quality_assertions]
    # Provenance: PROPOSED by the guardian, pending human approval (= merge).
    contract_input["properties"] = [
        {"key": "proposedBy", "value": "downstream-impact-guardian"},
        {"key": "status", "value": "PROPOSED"},
        {"key": "sourcePullRequest", "value": pr_url},
    ]
    return contract_input


def write_contract(live_client, entity_urn: str, assertions: list[dict],
                   pr_url: str, offline: bool) -> ContractResult:
    payload = build_contract_input(entity_urn, assertions, pr_url)

    if offline:
        return ContractResult(
            mode="recorded-offline", urn=None, payload=payload,
            note="No DataHub credentials in this run; the exact contract "
                 "payload the agent would submit is recorded below.")

    if not assertions:
        return ContractResult(
            mode="failed", urn=None, payload=payload,
            note="No assertions found on the dataset — a Data Contract must "
                 "bundle existing assertions (SPEC §5). Ingest dbt test "
                 "results first.")

    # Attempt 1: GraphQL upsert.
    try:
        data = live_client.graphql(UPSERT_MUTATION, {"input": payload})
        urn = (data.get("upsertDataContract") or {}).get("urn")
        if urn:
            return ContractResult(mode="upserted", urn=urn, payload=payload)
    except Exception as exc:  # mutation missing on OSS build, auth, etc.
        graphql_error = str(exc)

    # Attempt 2: direct aspect emission via the Python SDK.
    try:
        from datahub.emitter.mce_builder import make_data_platform_urn  # noqa: F401
        from datahub.emitter.mcp import MetadataChangeProposalWrapper
        from datahub.ingestion.graph.client import (DatahubClientConfig,
                                                    DataHubGraph)
        import datahub.metadata.schema_classes as models
        import time
        import uuid

        contract_urn = f"urn:li:dataContract:{uuid.uuid4()}"
        props = models.DataContractPropertiesClass(
            entity=entity_urn,
            schema=[models.SchemaContractClass(assertion=a["urn"])
                    for a in assertions[:1]],
            dataQuality=[models.DataQualityContractClass(assertion=a["urn"])
                         for a in assertions[1:]] or None,
        )
        status = models.DataContractStatusClass(
            customProperties={"status": "PROPOSED",
                              "proposedBy": "downstream-impact-guardian",
                              "sourcePullRequest": pr_url})
        graph = DataHubGraph(DatahubClientConfig(
            server=live_client.config.datahub_gms_url,
            token=live_client.config.datahub_gms_token))
        for aspect in (props, status):
            graph.emit_mcp(MetadataChangeProposalWrapper(
                entityUrn=contract_urn, aspect=aspect))
        return ContractResult(
            mode="sdk-emitted", urn=contract_urn, payload=payload,
            note=f"upsertDataContract unavailable ({graphql_error[:120]}); "
                 "emitted dataContractProperties directly via SDK.")
    except Exception as exc:
        return ContractResult(
            mode="failed", urn=None, payload=payload,
            note=f"Both GraphQL upsert and SDK emission failed: {exc}")
