"""Detection source #1 and #2: schema + logic changes, from dbt manifests.

Uses dbt's own state mechanism semantics (checksum + columns diff of
manifest.json) without executing anything against the warehouse — see
CLAUDE.md ("dbt ls, not dbt build") and ADR-0006 for where the prod
manifest comes from.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

from agent.models import (ColumnChange, GlossaryChange, ModelChange,
                          SuspectedDrift)


def load_manifest(path: str | Path) -> dict:
    with open(path) as f:
        return json.load(f)


def _models(manifest: dict) -> dict[str, dict]:
    return {
        uid: node
        for uid, node in manifest.get("nodes", {}).items()
        if uid.startswith("model.")
    }


def _norm_sql(sql: str) -> str:
    """Collapse whitespace and strip comments so cosmetic edits don't count
    as logic changes."""
    sql = re.sub(r"--[^\n]*", "", sql)
    return re.sub(r"\s+", " ", sql).strip().lower()


def diff_manifests(prod: dict, pr: dict) -> list[ModelChange]:
    prod_models, pr_models = _models(prod), _models(pr)
    changes: list[ModelChange] = []

    for uid, new in pr_models.items():
        old = prod_models.get(uid)
        if old is None:
            continue  # brand-new model: additive, nothing downstream yet
        change = ModelChange(
            model_name=new["name"],
            unique_id=uid,
            old_sql=old.get("raw_code", ""),
            new_sql=new.get("raw_code", ""),
            old_columns=list(old.get("columns", {})),
        )

        old_cols = old.get("columns", {})
        new_cols = new.get("columns", {})
        removed = [c for c in old_cols if c not in new_cols]
        added = [c for c in new_cols if c not in old_cols]
        for c in removed:
            change.columns.append(ColumnChange(name=c, change="removed",
                                               old_type=old_cols[c].get("data_type")))
        for c in added:
            change.columns.append(ColumnChange(name=c, change="added",
                                               new_type=new_cols[c].get("data_type")))
        # Rename heuristic: exactly one removed + one added in the same model.
        # Anything more ambiguous is reported as remove+add and the compat
        # view flags it for a human (see codegen).
        if len(removed) == 1 and len(added) == 1:
            change.renames.append((removed[0], added[0]))
        if removed or added:
            change.kinds.add("schema")

        if _norm_sql(change.old_sql) != _norm_sql(change.new_sql):
            change.kinds.add("logic")

        if change.kinds:
            changes.append(change)

    return changes


def find_suspected_drifts(pr_manifest: dict,
                          model_changes: list[ModelChange],
                          glossary_changes: list[GlossaryChange],
                          reader) -> list[SuspectedDrift]:
    """The "forgot the glossary" case: a model with metric drift has a column
    bound to a glossary term, and the PR does NOT update that term's
    definition. Flag for verification against the live definition —
    suspicion, not asserted divergence (see CONTEXT.md)."""
    updated_terms = {g.term_name for g in glossary_changes}
    models = _models(pr_manifest)
    suspected: list[SuspectedDrift] = []
    for change in model_changes:
        if "logic" not in change.kinds:
            continue
        node = models.get(change.unique_id, {})
        for col_name, col in (node.get("columns") or {}).items():
            term = (col.get("meta") or {}).get("business_glossary_term")
            if not term or term in updated_terms:
                continue
            live = reader.get_glossary_term(term)
            suspected.append(SuspectedDrift(
                term_name=term,
                model_name=change.model_name,
                column=col_name,
                live_definition=(live or {}).get("definition", "(term not found in DataHub)"),
            ))
    return suspected


def diff_glossary(pr_glossary_path: str | Path, reader) -> list[GlossaryChange]:
    """Detection source #3: PR-proposed glossary definitions vs what is live
    in DataHub right now (never the other way round — DataHub reflects
    reality, the PR is the hypothesis)."""
    path = Path(pr_glossary_path)
    if not path.exists():
        return []
    with open(path) as f:
        doc = yaml.safe_load(f) or {}

    changes: list[GlossaryChange] = []
    for node in doc.get("nodes", []):
        for term in node.get("terms", []):
            live = reader.get_glossary_term(term["name"])
            if live is None:
                continue  # term not in DataHub yet: additive
            proposed = " ".join(str(term.get("description", "")).split())
            current = " ".join(str(live.get("definition", "")).split())
            if proposed != current:
                changes.append(GlossaryChange(
                    term_name=term["name"],
                    live_definition=current,
                    proposed_definition=proposed,
                ))
    return changes
