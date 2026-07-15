"""DataHub read access: one live GraphQL client, one fixture client with the
same surface. The fixture client is a first-class mode (ADR-0007), not a
test double — fork PRs have no secrets and still get a full report.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

import requests

from agent.config import FIXTURES_DIR, Config
from agent.models import Consumer, QueryUsage


class DataHubReader(Protocol):
    def get_dataset_urn(self, model_name: str) -> str | None: ...
    def get_schema(self, model_name: str) -> list[dict]: ...
    def get_downstream(self, model_name: str) -> list[Consumer]: ...
    def get_queries(self, model_name: str) -> list[QueryUsage]: ...
    def get_glossary_term(self, name: str) -> dict | None: ...
    def get_assertions(self, model_name: str) -> list[dict]: ...


class FixtureDataHubClient:
    """Reads committed JSON fixtures shaped like live responses."""

    def __init__(self, fixtures_dir: str | Path = FIXTURES_DIR):
        d = Path(fixtures_dir)
        self._datasets = json.loads((d / "datasets.json").read_text())
        self._lineage = json.loads((d / "lineage.json").read_text())
        self._queries = json.loads((d / "queries.json").read_text())
        self._glossary = json.loads((d / "glossary.json").read_text())

    def get_dataset_urn(self, model_name: str) -> str | None:
        ds = self._datasets.get(model_name)
        return ds["urn"] if ds else None

    def get_schema(self, model_name: str) -> list[dict]:
        return self._datasets.get(model_name, {}).get("schema", [])

    def get_downstream(self, model_name: str) -> list[Consumer]:
        return [Consumer(**c) for c in self._lineage.get(model_name, [])]

    def get_queries(self, model_name: str) -> list[QueryUsage]:
        return [QueryUsage(**q) for q in self._queries.get(model_name, [])]

    def get_glossary_term(self, name: str) -> dict | None:
        return self._glossary.get(name)

    def get_assertions(self, model_name: str) -> list[dict]:
        return self._datasets.get(model_name, {}).get("assertions", [])


class LiveDataHubClient:
    """Thin GraphQL client against a self-hosted OSS gms (ADR-0003).

    NOTE: exercised against fixtures in CI; the GraphQL documents follow the
    OSS schema as documented. Anything that errors degrades to empty results
    with a warning rather than failing the check.
    """

    def __init__(self, config: Config):
        self.config = config
        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f"Bearer {config.datahub_gms_token}",
            "Content-Type": "application/json",
        })

    def graphql(self, query: str, variables: dict | None = None) -> dict:
        resp = self._session.post(
            f"{self.config.datahub_gms_url}/api/graphql",
            json={"query": query, "variables": variables or {}},
            timeout=30,
        )
        resp.raise_for_status()
        body = resp.json()
        if body.get("errors"):
            raise RuntimeError(f"DataHub GraphQL errors: {body['errors']}")
        return body["data"]

    def get_dataset_urn(self, model_name: str) -> str | None:
        urn = self.config.dataset_urn(model_name)
        data = self.graphql(
            "query exists($urn: String!) { dataset(urn: $urn) { urn } }",
            {"urn": urn},
        )
        return urn if data.get("dataset") else None

    def get_schema(self, model_name: str) -> list[dict]:
        urn = self.config.dataset_urn(model_name)
        data = self.graphql(
            """query schema($urn: String!) {
                 dataset(urn: $urn) {
                   schemaMetadata { fields { fieldPath nativeDataType } }
                 }
               }""",
            {"urn": urn},
        )
        fields = (((data.get("dataset") or {}).get("schemaMetadata") or {})
                  .get("fields") or [])
        return [{"name": f["fieldPath"], "type": f.get("nativeDataType", "")}
                for f in fields]

    def get_downstream(self, model_name: str) -> list[Consumer]:
        urn = self.config.dataset_urn(model_name)
        data = self.graphql(
            """query lineage($input: SearchAcrossLineageInput!) {
                 searchAcrossLineage(input: $input) {
                   searchResults {
                     degree
                     entity {
                       urn
                       type
                       ... on Dataset {
                         name
                         platform { name }
                       }
                       ... on Dashboard {
                         properties { name }
                         platform { name }
                       }
                       ... on Chart {
                         properties { name }
                         platform { name }
                       }
                     }
                   }
                 }
               }""",
            {"input": {"urn": urn, "direction": "DOWNSTREAM",
                       "query": "*", "start": 0, "count": 50}},
        )
        results = ((data.get("searchAcrossLineage") or {})
                   .get("searchResults") or [])
        consumers = []
        for r in results:
            e = r["entity"]
            name = e.get("name") or (e.get("properties") or {}).get("name") or e["urn"]
            consumers.append(Consumer(
                name=name,
                platform=(e.get("platform") or {}).get("name", "unknown"),
                entity_type=e.get("type", "").lower(),
                urn=e["urn"],
                hops=r.get("degree", 1),
            ))
        return consumers

    def get_queries(self, model_name: str) -> list[QueryUsage]:
        urn = self.config.dataset_urn(model_name)
        data = self.graphql(
            """query queries($input: ListQueriesInput!) {
                 listQueries(input: $input) {
                   queries { properties { statement { value } source } }
                 }
               }""",
            {"input": {"datasetUrn": urn, "start": 0, "count": 20}},
        )
        queries = ((data.get("listQueries") or {}).get("queries") or [])
        return [QueryUsage(
            sql=((q.get("properties") or {}).get("statement") or {}).get("value", ""),
            platform=(q.get("properties") or {}).get("source", ""),
        ) for q in queries]

    def get_glossary_term(self, name: str) -> dict | None:
        data = self.graphql(
            """query find($input: SearchInput!) {
                 search(input: $input) {
                   searchResults {
                     entity {
                       urn
                       ... on GlossaryTerm {
                         properties { name definition }
                       }
                     }
                   }
                 }
               }""",
            {"input": {"type": "GLOSSARY_TERM", "query": f'"{name}"',
                       "start": 0, "count": 5}},
        )
        for r in ((data.get("search") or {}).get("searchResults") or []):
            props = r["entity"].get("properties") or {}
            if props.get("name", "").lower() == name.lower():
                return {"urn": r["entity"]["urn"],
                        "definition": props.get("definition", "")}
        return None

    def get_assertions(self, model_name: str) -> list[dict]:
        urn = self.config.dataset_urn(model_name)
        data = self.graphql(
            """query assertions($urn: String!) {
                 dataset(urn: $urn) {
                   assertions(start: 0, count: 50) {
                     assertions { urn info { type description } }
                   }
                 }
               }""",
            {"urn": urn},
        )
        assertions = (((data.get("dataset") or {}).get("assertions") or {})
                      .get("assertions") or [])
        return [{"urn": a["urn"],
                 "type": (a.get("info") or {}).get("type", ""),
                 "description": (a.get("info") or {}).get("description", "")}
                for a in assertions]


def make_reader(config: Config) -> DataHubReader:
    if config.mode == "live":
        return LiveDataHubClient(config)
    return FixtureDataHubClient()
