"""Writeback #1: a Data Contract into DataHub.

Verified against a live OSS quickstart 2026-07-15: `upsertDataContract`
EXISTS and works on self-hosted OSS (SPEC §11 was right to distrust the
docs' Cloud-only framing on this one point — only the proposal *inbox* is
Cloud-only). The input takes entityUrn + assertion bundles ONLY; PROPOSED
provenance goes on afterwards as a `dataContractStatus` aspect
(state=PENDING + customProperties) via the SDK. Human approval gate stays
the PR merge (ADR-0003).
"""
from __future__ import annotations

from agent.models import ContractResult

UPSERT_MUTATION = """
mutation upsert($input: UpsertDataContractInput!) {
  upsertDataContract(input: $input) { urn }
}
"""


def build_contract_input(entity_urn: str, assertions: list[dict]) -> dict:
    """Pure UpsertDataContractInput — no extra keys, the GraphQL schema
    rejects unknown fields."""
    schema_assertions = [a for a in assertions
                         if "unique" in (a.get("description") or "").lower()
                         or "not_null" in (a.get("description") or "").lower()
                         or (a.get("type") or "").upper() in ("DATASET", "FIELD")]
    quality_assertions = [a for a in assertions if a not in schema_assertions]
    contract_input: dict = {"entityUrn": entity_urn}
    if schema_assertions:
        contract_input["schema"] = [{"assertionUrn": a["urn"]}
                                    for a in schema_assertions]
    if quality_assertions:
        contract_input["dataQuality"] = [{"assertionUrn": a["urn"]}
                                         for a in quality_assertions]
    return contract_input


def build_provenance(pr_url: str) -> dict:
    return {"status": "PROPOSED",
            "proposedBy": "downstream-impact-guardian",
            "sourcePullRequest": pr_url}


def _emit_status_aspect(config, contract_urn: str, provenance: dict) -> str:
    """Stamp PROPOSED provenance on the contract. Returns a note ('' on
    success). Best-effort: the contract itself already exists."""
    try:
        from datahub.emitter.mcp import MetadataChangeProposalWrapper
        from datahub.ingestion.graph.client import (DatahubClientConfig,
                                                    DataHubGraph)
        import datahub.metadata.schema_classes as models

        status = models.DataContractStatusClass(
            state=models.DataContractStateClass.PENDING,
            customProperties=provenance)
        graph = DataHubGraph(DatahubClientConfig(
            server=config.datahub_gms_url,
            token=config.datahub_gms_token or None))
        graph.emit_mcp(MetadataChangeProposalWrapper(
            entityUrn=contract_urn, aspect=status))
        return ""
    except Exception as exc:
        return (f"Contract created, but PROPOSED status aspect could not be "
                f"stamped: {exc}")


def write_contract(live_client, entity_urn: str, assertions: list[dict],
                   pr_url: str, offline: bool) -> ContractResult:
    payload = build_contract_input(entity_urn, assertions)
    provenance = build_provenance(pr_url)
    payload_for_record = {**payload, "provenance": provenance}

    if offline:
        return ContractResult(
            mode="recorded-offline", urn=None, payload=payload_for_record,
            note="No DataHub credentials in this run; the exact contract "
                 "payload the agent would submit is recorded below.")

    if not assertions:
        return ContractResult(
            mode="failed", urn=None, payload=payload_for_record,
            note="No assertions found on the dataset — a Data Contract must "
                 "bundle existing assertions (SPEC §5). Ingest dbt test "
                 "results first.")

    # Attempt 1: GraphQL upsert (verified working on OSS), then stamp
    # PROPOSED provenance as a status aspect.
    graphql_error = ""
    try:
        data = live_client.graphql(UPSERT_MUTATION, {"input": payload})
        urn = (data.get("upsertDataContract") or {}).get("urn")
        if urn:
            note = _emit_status_aspect(live_client.config, urn, provenance)
            return ContractResult(mode="upserted", urn=urn,
                                  payload=payload_for_record, note=note)
        graphql_error = "mutation returned no urn"
    except Exception as exc:
        graphql_error = str(exc)

    # Attempt 2: build the whole contract via SDK aspect emission.
    try:
        from datahub.emitter.mcp import MetadataChangeProposalWrapper
        from datahub.ingestion.graph.client import (DatahubClientConfig,
                                                    DataHubGraph)
        import datahub.metadata.schema_classes as models
        import uuid

        contract_urn = f"urn:li:dataContract:{uuid.uuid4()}"
        schema_urns = [s["assertionUrn"] for s in payload.get("schema", [])]
        dq_urns = [d["assertionUrn"] for d in payload.get("dataQuality", [])]
        props = models.DataContractPropertiesClass(
            entity=entity_urn,
            schema=[models.SchemaContractClass(assertion=u)
                    for u in schema_urns] or None,
            dataQuality=[models.DataQualityContractClass(assertion=u)
                         for u in dq_urns] or None,
        )
        status = models.DataContractStatusClass(
            state=models.DataContractStateClass.PENDING,
            customProperties=provenance)
        graph = DataHubGraph(DatahubClientConfig(
            server=live_client.config.datahub_gms_url,
            token=live_client.config.datahub_gms_token or None))
        for aspect in (props, status):
            graph.emit_mcp(MetadataChangeProposalWrapper(
                entityUrn=contract_urn, aspect=aspect))
        return ContractResult(
            mode="sdk-emitted", urn=contract_urn, payload=payload_for_record,
            note=f"upsertDataContract failed ({graphql_error[:120]}); "
                 "emitted contract aspects directly via SDK.")
    except Exception as exc:
        return ContractResult(
            mode="failed", urn=None, payload=payload_for_record,
            note=f"GraphQL upsert failed ({graphql_error[:120]}); SDK "
                 f"emission also failed: {exc}")
