# Diagrams

Rendered inline by GitHub. Screenshot any panel for the Devpost gallery, or open
the [interactive walkthrough](https://claude.ai/code/artifact/c578039e-bce6-4330-8396-cb48b739e7c6)
for the same architecture with links to every technology.

## 1 · System architecture — hypothesis vs. reality

The pull request is a *hypothesis*; DataHub is *reality*. The agent reads the
catalog for what's live and the dbt/glossary diff for what's proposed — and
never ingests the PR's hypothetical state.

```mermaid
flowchart LR
  subgraph PR["Pull request — hypothesis"]
    A["dbt manifest diff"]
    B["glossary yml diff"]
  end
  subgraph DH["DataHub — reality"]
    L["lineage"]
    Q["observed queries"]
    S["live schema"]
    G["live glossary"]
  end
  A --> BR["Blast radius + severity<br/>deterministic · 48 tests"]
  B --> BR
  L --> BR
  Q --> BR
  G --> B
  BR --> N["Narrative<br/>ADK agent + Agent Context Kit"]
  BR --> CG["Codegen<br/>compat view + tests"]
  S --> CG
  BR --> CT["Data Contract · PROPOSED"] --> DHW[("DataHub")]
  N --> CM["One idempotent PR comment"]
  CG --> CM --> GH[("GitHub PR")]
  BR --> SL["Slack alert · HIGH/CRITICAL · opt-in"]
```

## 2 · Agent topology — deterministic core, one narrating agent

A flat topology on purpose. The deterministic pipeline (`main.py`) owns control
flow and every judgment; a single ADK agent adds the narrative and cross-checks
facts through read-only DataHub tools. The LLM never scores and never authors
merged code.

```mermaid
flowchart TB
  RUN["GitHub Action runner (consumer's repo)"] --> MAIN["main.py — deterministic pipeline"]
  MAIN --> DET["detect · dbt manifest diff · sqlglot · glossary"]
  MAIN --> BR["blast_radius.assess · severity + per-consumer verdicts"]
  MAIN --> CG["codegen · compatibility view + schema tests"]
  MAIN --> CT["contract · upsertDataContract (PROPOSED)"]
  MAIN --> NAR["enrich_narrative · live + configured only · bounded · retry 3×"]
  NAR --> AGENT["single ADK Agent · LiteLLM routing (gemini / openai / qwen)"]
  AGENT --> ACK["DataHub Agent Context Kit · read-only tools<br/>lineage · queries · schema"]
  MAIN --> OUT["one idempotent PR comment · optional Slack alert"]
  classDef det fill:#EEF0FE,stroke:#4F46E5,color:#161C29;
  classDef llm fill:#FFF4E6,stroke:#B45309,color:#161C29;
  class MAIN,DET,BR,CG,CT,OUT det;
  class NAR,AGENT,ACK llm;
```

## 3 · Sequence — one PR, end to end

```mermaid
sequenceDiagram
  autonumber
  actor Dev as dbt author
  participant GH as GitHub PR
  participant Act as Action runner
  participant Diff as dbt + glossary diff
  participant DH as DataHub (ACK + GraphQL)
  participant LLM as ADK agent (Qwen)
  participant Slack

  Dev->>GH: open PR (schema / logic / semantic change)
  GH->>Act: pull_request event
  Act->>Diff: detect change (manifest diff · sqlglot · glossary)
  Act->>DH: read lineage + observed queries (skipCache)
  Act->>Act: assess blast radius + severity (deterministic, tested)
  Act->>DH: upsert Data Contract (PROPOSED)
  Act->>LLM: narrate — facts + read-only ACK tools
  LLM->>DH: cross-check lineage / queries / schema
  LLM-->>Act: impact narrative + ranked actions
  Act->>GH: post one comment (verdict · blast radius · compat code)
  Act->>Slack: HIGH/CRITICAL alert (opt-in webhook)
```

## 4 · One-page infographic

The polished single-image summary lives in the
[interactive walkthrough](https://claude.ai/code/artifact/c578039e-bce6-4330-8396-cb48b739e7c6)
(architecture + the three detectors + precision ladder + two writebacks, with
headline numbers). Screenshot its hero + architecture section for a Devpost cover,
or use `slide-arch.png` here.
