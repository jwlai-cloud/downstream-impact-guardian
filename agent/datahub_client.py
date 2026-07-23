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


def parse_declared_deps(custom_props: dict) -> dict[str, list[str]]:
    """Tolerant parser for depends_on_columns custom properties (ADR-0010
    addendum). Ingestion flattens dbt meta differently across versions:
    - single key "depends_on_columns" with a JSON dict value
    - dotted keys "depends_on_columns.<model>" with JSON-list or
      comma-separated string values"""
    deps: dict[str, list[str]] = {}
    for key, raw in (custom_props or {}).items():
        if not str(key).startswith("depends_on_columns"):
            continue
        try:
            if key == "depends_on_columns":
                parsed = json.loads(raw) if isinstance(raw, str) else raw
                if isinstance(parsed, dict):
                    for model, cols in parsed.items():
                        deps[str(model)] = [str(c) for c in cols]
            else:
                model = str(key).split(".", 1)[1]
                if isinstance(raw, str):
                    try:
                        cols = json.loads(raw.replace("'", '"'))
                    except Exception:
                        cols = [c.strip() for c in raw.split(",") if c.strip()]
                else:
                    cols = list(raw)
                deps[model] = [str(c) for c in cols]
        except Exception:
            continue  # malformed declaration: ignore, fall back to worst-case
    return deps


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
        self._session.headers.update({"Content-Type": "application/json"})
        if config.datahub_gms_token:
            self._session.headers.update(
                {"Authorization": f"Bearer {config.datahub_gms_token}"})

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
                         properties { customProperties { key value } }
                         ownership { owners { owner {
                           ... on CorpUser { username }
                           ... on CorpGroup { name }
                         } } }
                       }
                       ... on Dashboard {
                         properties { name customProperties { key value } }
                         platform { name }
                         ownership { owners { owner {
                           ... on CorpUser { username }
                           ... on CorpGroup { name }
                         } } }
                       }
                       ... on Chart {
                         properties { name }
                         platform { name }
                         ownership { owners { owner {
                           ... on CorpUser { username }
                           ... on CorpGroup { name }
                         } } }
                       }
                     }
                   }
                 }
               }""",
            # skipCache: GMS caches searchAcrossLineage per (urn, direction);
            # a stale entry means a stale blast radius — freshness beats
            # latency for a judgment that names stakeholders.
            {"input": {"urn": urn, "direction": "DOWNSTREAM",
                       "query": "*", "start": 0, "count": 50,
                       "searchFlags": {"skipCache": True}}},
        )
        results = ((data.get("searchAcrossLineage") or {})
                   .get("searchResults") or [])
        consumers = []
        for r in results:
            e = r["entity"]
            name = e.get("name") or (e.get("properties") or {}).get("name") or e["urn"]
            owners = [(o.get("owner") or {}).get("username")
                      or (o.get("owner") or {}).get("name")
                      for o in ((e.get("ownership") or {}).get("owners") or [])]
            props = ((e.get("properties") or {}).get("customProperties") or [])
            custom = {p_["key"]: p_["value"] for p_ in props
                      if isinstance(p_, dict) and "key" in p_}
            consumers.append(Consumer(
                name=name,
                platform=(e.get("platform") or {}).get("name", "unknown"),
                entity_type=e.get("type", "").lower(),
                urn=e["urn"],
                hops=r.get("degree", 1),
                owners=[o for o in owners if o],
                declared_deps=parse_declared_deps(custom),
            ))
        # dbt ingestion creates a dbt + warehouse sibling per model; both
        # appear in lineage. Collapse to one logical consumer (lowest hops).
        consumers.sort(key=lambda c: c.hops)
        seen: set[tuple] = set()
        deduped = []
        for c in consumers:
            key = (c.name.split(".")[-1].lower(), c.entity_type)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(c)
        return deduped

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
        # dbt test assertions attach to the DBT sibling, not the warehouse
        # entity (verified against OSS quickstart 2026-07-15) — query both.
        merged: dict[str, dict] = {}
        for platform in (self.config.datahub_platform, "dbt"):
            urn = self.config.dataset_urn(model_name, platform=platform)
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
            for a in (((data.get("dataset") or {}).get("assertions") or {})
                      .get("assertions") or []):
                info = a.get("info") or {}
                merged[a["urn"]] = {"urn": a["urn"],
                                    "type": info.get("type") or "",
                                    "description": info.get("description") or ""}
        return list(merged.values())


def make_reader(config: Config) -> DataHubReader:
    if config.mode == "live":
        return LiveDataHubClient(config)
    return FixtureDataHubClient()
