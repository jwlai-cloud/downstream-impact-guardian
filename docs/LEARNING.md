# LEARNING — tech breakdown for slow reading

Written for the builder, not the judges: what each piece actually is, why
it's here, and the primary sources used. Read after the hackathon.

## DataHub: the metadata graph

**What it is.** An open-source metadata platform: every dataset, dashboard,
pipeline, and glossary term becomes an *entity* with a URN; *aspects*
(schema, lineage, ownership, assertions) attach to entities; GraphQL and a
Python SDK sit on top. The insight this project leans on: the graph knows
*cross-system* facts no single repo can — who consumes a table, which
queries hit it, what a business term currently means.

- Entity/aspect model + Timeline API: https://docs.datahub.com/docs/dev-guides/timeline
- Lineage read we use (`searchAcrossLineage`) and why siblings appear
  twice: dbt ingestion creates a dbt-platform entity AND a
  warehouse-platform entity per model, linked as siblings. Learned live:
  **dbt-test assertions attach to the dbt sibling**, so a client asking the
  warehouse URN sees zero assertions (agent/datahub_client.py merges both).
- Data Contracts: entity bundling existing assertions. Learned live:
  `upsertDataContract` works on OSS (the docs' Cloud-only framing applies
  to the proposal *inbox*, not the mutation), input rejects unknown keys,
  and PROPOSED semantics are expressible as a `dataContractStatus` aspect
  (`state: PENDING` + customProperties).
  https://docs.datahub.com/docs/api/tutorials/data-contracts

## The three DataHub agent-integration surfaces (and when each fits)

1. **Agent Context Kit** (`datahub-agent-context[google-adk]`) — Python
   package producing framework-native tools (`build_google_adk_tools`).
   Right when the agent is embedded Python: in-process, no server hop.
   https://docs.datahub.com/docs/dev-guides/agent-context/google-adk
2. **MCP Server** (`mcp-server-datahub`) — same tool family over the Model
   Context Protocol. Right for *external* agents (Claude Desktop, Cursor)
   talking to your catalog; wrong inside a Python pipeline that can import
   the Kit. On OSS it auto-disables mutation tools (`is_oss=true`).
   https://docs.datahub.com/docs/features/feature-guides/mcp
3. **Raw GraphQL/SDK** — for what neither exposes: `upsertDataContract`,
   sibling-aware assertion lookup, status-aspect emission.

## Google ADK (Agent Development Kit)

`Agent(model, instruction, tools)` + `Runner` + session service; Python
functions become tools via introspection. Design choice worth remembering:
the LLM here *narrates* — scoring and codegen stay deterministic and
unit-tested, so the agent works (degraded but complete) with no key at all.
That split is why 26 tests run in 0.2 s with zero network.

- Quickstart pattern used: `Runner.run_async` + `InMemorySessionService`
  (agent/adk_agent.py). Model: `gemini-flash-latest`.

## dbt state semantics without a warehouse

`dbt parse` builds `manifest.json` without opening a connection — that's
what lets CI diff prod-vs-PR manifests with zero warehouse credentials
(dbt's own `state:modified` idea, reimplemented as a column-level diff
because `dbt ls` yields node names only).
https://docs.getdbt.com/reference/node-selection/methods#state

Gotchas that cost real time:
- `dbt docs generate` **overwrites `run_results.json`** with an entry the
  DataHub source skips — run `dbt test` LAST before ingesting.
- dbt 1.10+ deprecations: column `meta` moves under `config.meta`; generic
  test args move under `arguments`.
- `oauth-secrets` profile method + `gcloud auth print-access-token
  --account=X` = run dbt as any credentialed account without touching ADC.

## GitHub Actions as bot infrastructure

A composite action (`action.yml`, `runs.using: composite`) turns a repo
into an installable bot: consumers add one `uses:` block; the consumer's
runner is the compute; `github.action_path` locates the action's own code.
Two security lessons, both caught by review bots or the permission
classifier:
- **Never interpolate `${{ inputs.* }}` into `run:` scripts** — expression
  injection; map inputs through `env:` and read shell variables.
- **Unset repo vars arrive as empty strings**, which defeat
  `env_var('X', 'default')` in dbt profiles AND `os.environ.get(k, d)` in
  Python — treat empty-as-unset at every layer.

Also: anyone with read access can open a PR between existing branches of a
public repo (the judge path needs no fork); fork PRs get no secrets (why
offline fixture mode is first-class, ADR-0007).

## Oracle Cloud Always Free (the $0 DataHub host)

A1.Flex ARM, 4 OCPU/24 GB — the only free tier big enough for the DataHub
quickstart. Traps: capacity errors by home region, 7-day idle reclamation
(both fixed by upgrading the tenancy to Pay-As-You-Go, still $0), the
two-layer firewall (VCN Security List AND on-instance iptables REJECT
rule), and signup fraud filters that dislike debit cards.
Runbook: docs/ORACLE_BRINGUP.md.

## Related work

Pinterest's automated schema evolution — same "schema is a cross-system
contract" worldview, opposite trade-off (pipeline ownership + deep
automation vs catalog context + consequence analysis). Full comparison:
docs/SPEC.md §12.
