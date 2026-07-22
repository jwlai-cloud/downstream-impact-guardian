# Architecture Decision Records

Short Nygard-style records. Context that predates these (framework choice,
three-source detection, dual writeback, PR-bot interface) lives in
`docs/SPEC.md` §1–10; these ADRs record the decisions made from the
2026-07-15 grill session onward.

| ADR | Decision |
|---|---|
| [0001](0001-fiction-retail-dataset.md) | fiction-retail as the demo dataset |
| [0002](0002-compat-artifact-shape.md) | Compat artifact = dbt view(s) + tests, deterministic codegen |
| [0003](0003-self-hosted-datahub-contract-writeback.md) | Self-hosted OSS DataHub; contract via upsert/SDK with PROPOSED status |
| [0004](0004-github-auth-builtin-token.md) | Built-in Actions GITHUB_TOKEN |
| [0005](0005-formal-glossary-terms.md) | Formal glossary terms for semantic drift detection |
| [0006](0006-committed-prod-manifest.md) | Prod dbt manifest committed to the repo |
| [0007](0007-offline-fixture-mode.md) | Offline fixture mode as a first-class agent mode |
| [0008](0008-agent-runs-in-action.md) | Agent executes inside the Action runner, not Cloud Run |
| [0009](0009-contract-per-impacted-model.md) | One Data Contract per impacted model |
| [0010](0010-impact-levels-and-informing-protocol.md) | Per-consumer impact levels + stakeholder informing protocol |
