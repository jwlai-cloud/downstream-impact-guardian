# Architecture

One PR-triggered pipeline, two writebacks. Design rationale in
`SPEC.md`; decisions in `adr/`.

```mermaid
flowchart LR
    subgraph PR["Pull request (the hypothesis)"]
        A["dbt model diff\n(PR manifest via dbt parse)"]
        B["business_glossary.yml diff"]
    end

    subgraph DH["DataHub (the reality)"]
        L["get lineage\n(searchAcrossLineage)"]
        Q["observed queries\n(listQueries)"]
        S["live schema"]
        G["live glossary definitions"]
        AS["assertions\n(ingested dbt tests)"]
    end

    A -->|"schema + logic changes\n(dbt_state.py)"| BR
    B -->|"semantic drift\n(dbt_state.diff_glossary)"| BR
    L --> BR["Blast radius\n(blast_radius.py)\ndeterministic score"]
    Q --> BR
    G --> B

    BR --> N["Impact narrative\nADK Agent + Gemini (live)\ndeterministic fallback (offline)"]
    S --> CG["Codegen (codegen.py)\ncompat + legacy views\n+ schema.yml tests"]
    BR --> CG
    AS --> CT["Writeback 1\nData Contract, PROPOSED\n(contract.py)"]
    CT -->|"upsert / SDK emission"| DHW[("DataHub")]
    N --> CM["Writeback 2\nPR comment (pr_comment.py)\nidempotent + step summary"]
    CG --> CM
    CT --> CM
    CM --> GH[("GitHub PR")]
```

## Two invariants everything hangs off

1. **DataHub only ever reflects reality.** The PR diff is read locally as
   the *proposal*; DataHub is read as the *live truth* (schema, lineage,
   queries, glossary). Nothing hypothetical is ever ingested.
2. **The LLM narrates; it never scores and never authors merged code.**
   Severity scoring and codegen are deterministic and unit-tested; the ADK
   agent improves prose in live mode and vanishes harmlessly offline
   (ADR-0002, ADR-0007).

## Components

| Path | Role |
|---|---|
| `.github/workflows/downstream-impact-guardian-check.yml` | Trigger: `pull_request` touching `dbt_demo_project/**`. Installs deps, `dbt parse`, runs the agent. Fork-safe (ADR-0007). |
| `agent/main.py` | Orchestrates steps 1–6; CLI contract `--pr-number N`; exit 0 unless `--strict` |
| `agent/dbt_state.py` | Detection #1/#2: committed prod manifest (ADR-0006) vs PR manifest — column diff, rename heuristic, normalized-SQL logic diff. Detection #3: PR glossary yml vs live DataHub terms |
| `agent/datahub_client.py` | `LiveDataHubClient` (GraphQL) / `FixtureDataHubClient` (committed JSON), same protocol |
| `agent/blast_radius.py` | Lineage + query cross-reference; inspectable additive scoring → LOW/MEDIUM/HIGH/CRITICAL |
| `agent/contract.py` | Writeback 1: upsert → SDK-emission fallback, PROPOSED provenance (ADR-0003) |
| `agent/codegen.py` | Writeback 2 payload: deterministic `*_compat` / `*_legacy` views, live schema as the old-shape authority, `requires_human` flag for unmappable cases |
| `agent/adk_agent.py` | Google ADK `Agent` (gemini-flash-latest) with read-only DataHub tools; narrative only |
| `agent/pr_comment.py` | Renders + posts one idempotent comment (HTML marker), mirrors to `$GITHUB_STEP_SUMMARY` |
| `dbt_demo_project/` | fiction-retail: seeds → staging → `fct_orders` → `revenue_daily`; glossary + ingestion recipes (ADR-0001, ADR-0005) |
| `examples/generated/` | Real output of a run against `demo/breaking-change` |
| `tools/demo_ui/` | Stretch goal only — untouched, per CLAUDE.md |

## Modes

| | live | offline (fixtures) |
|---|---|---|
| Trigger condition | GMS URL + token present | any secret missing (e.g. fork PR) |
| Lineage/queries/schema/glossary | DataHub GraphQL | `agent/fixtures/*.json` |
| Contract | upsert → SDK fallback | exact payload recorded in the comment |
| Narrative | ADK + Gemini, deterministic fallback | deterministic |
| PR comment | posted/updated | rendered; step summary always written |

## Judge path

Open a PR from `demo/breaking-change` → `master` in this repo (read access
suffices; no fork). The branch stages one schema break, one silent metric
redefinition, one glossary drift. Repo-internal CI is green — only the
cross-system context in DataHub reveals the breakage. That asymmetry is the
whole pitch.

## Deliberate limitations (honest list)

- Rename detection is a 1-removed/1-added heuristic; anything more
  ambiguous is reported as remove+add and flagged for a human.
- `LiveDataHubClient` GraphQL documents follow OSS schema docs but have
  been exercised against fixtures only until the judge instance is up.
- `type_changed` detection is limited because dbt yml rarely carries
  `data_type`; the live-schema path is where that would come from.
- Prod-manifest refresh is a script, not a main-branch workflow — the
  obvious next automation.
