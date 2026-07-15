"""Shared dataclasses for the guardian pipeline."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ColumnChange:
    name: str
    change: str  # "added" | "removed" | "type_changed"
    old_type: str | None = None
    new_type: str | None = None


@dataclass
class ModelChange:
    model_name: str            # e.g. "fct_orders"
    unique_id: str             # e.g. "model.fiction_retail.fct_orders"
    kinds: set[str] = field(default_factory=set)  # {"schema", "logic"}
    columns: list[ColumnChange] = field(default_factory=list)
    renames: list[tuple[str, str]] = field(default_factory=list)  # (old, new)
    old_sql: str = ""
    new_sql: str = ""
    old_columns: list[str] = field(default_factory=list)  # ordered, pre-change

    @property
    def breaking(self) -> bool:
        removed = {c.name for c in self.columns if c.change == "removed"}
        return bool(removed) or bool(self.renames)


@dataclass
class GlossaryChange:
    term_name: str
    live_definition: str       # what DataHub says is true today
    proposed_definition: str   # what the PR proposes


@dataclass
class SuspectedDrift:
    """Metric drift on a term-bound model with NO matching glossary update in
    the PR (the "forgot the glossary" case) — a suspicion to verify, never an
    asserted divergence. See CONTEXT.md."""
    term_name: str
    model_name: str
    column: str
    live_definition: str


@dataclass
class Consumer:
    name: str
    platform: str              # bigquery | looker | dbt | ...
    entity_type: str           # dataset | dashboard | chart | ...
    urn: str = ""
    hops: int = 1
    detail: str = ""


@dataclass
class QueryUsage:
    sql: str
    user: str = ""
    platform: str = ""
    run_count: int = 0
    references_changed_column: bool = False


@dataclass
class CompatArtifact:
    view_name: str
    sql: str
    schema_yml: str
    requires_human: bool = False   # true when a column vanished with no mapping
    for_model: str = ""


@dataclass
class ContractResult:
    mode: str                  # "upserted" | "sdk-emitted" | "recorded-offline" | "failed"
    urn: str | None
    payload: dict
    note: str = ""
    model_name: str = ""       # the impacted model this contract covers


@dataclass
class ImpactReport:
    model_changes: list[ModelChange]
    glossary_changes: list[GlossaryChange]
    consumers: dict[str, list[Consumer]]       # model_name -> consumers
    queries: dict[str, list[QueryUsage]]       # model_name -> query usage
    suspected_drifts: list[SuspectedDrift] = field(default_factory=list)
    severity: str = "LOW"                      # LOW | MEDIUM | HIGH | CRITICAL
    score: int = 0
    narrative: str = ""
    narrative_source: str = "deterministic"    # or "gemini-adk"
