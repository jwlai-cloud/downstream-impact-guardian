# Devpost submission — Downstream Impact Guardian

> Draft. Numbers marked `[MEASURE]` need a real measured value before
> submitting — do not invent them. Structure follows Devpost's fixed
> section order; don't reorder.

**Track (primary):** Agents That Do Real Work
**Track (secondary claim, in description only):** Metadata-Aware Code
Generation & Development

---

## Inspiration

Every data team has lived this PR: someone renames a column in a dbt
model, CI is green, tests pass, it merges — and three days later a
dashboard two teams away is silently wrong. The repo told the truth:
*nothing in this repo broke.* The repo just couldn't see the finance
team's scheduled query, the ML feature pipeline, or the exec dashboard
that all read from that table.

That blind spot is structural. No amount of in-repo testing fixes it,
because the blast radius of a schema or logic change lives *across*
systems, and the only place that cross-system picture exists is the
metadata graph. So we built the agent that stands in the gap: it reads
the PR for what's *proposed*, reads DataHub for what's *real*, and
refuses to let the two drift apart silently.

Industry has validated the problem at scale: Pinterest's
[automated schema evolution framework](https://medium.com/pinterest-engineering/automated-schema-evolution-in-pinterests-next-generation-db-ingestion-framework-36c5c07070de)
treats schema as exactly this — "a cross-system contract spanning
ingestion, transformation, storage" — and auto-evolves additive changes
at the CDC layer, opening regenerated code as PRs for human review. But
it can afford **no lineage, no catalog, and no downstream-consumer
analysis** because Pinterest owns the entire pipeline; it also handles
structural changes only, never metric or semantic drift. Most data
teams own a dbt repo, not the pipeline. This project is the
complementary, shift-left half: catalog context (DataHub) substitutes
for pipeline ownership, so *any* dbt team gets consumer-aware impact
analysis, semantic-drift detection, and contract proposals — at PR
time, before anything ships.

## What it does

Downstream Impact Guardian is a reusable GitHub Action that catches
breaking dbt changes **that in-repo CI cannot see** — because the
evidence lives in DataHub's cross-system lineage, not in the repo. Its
demo PR is deliberately green in normal CI; only the metadata graph
reveals the damage.

On every pull request it:

1. **Detects three kinds of drift** from three sources — schema changes
   (committed prod manifest vs PR manifest), business-logic changes
   (normalized-SQL diff of the same), and semantic drift (the PR's
   glossary YAML vs the live DataHub glossary).
2. **Measures real blast radius** by cross-referencing DataHub lineage
   (`searchAcrossLineage`) with observed queries — cross-system,
   cross-team usage no single repo can see — and scores severity
   LOW/MEDIUM/HIGH/CRITICAL with a deterministic, inspectable rubric.
3. **Writes back to DataHub**: a Data Contract for each impacted model,
   upserted with PROPOSED status. The catalog now durably records "this
   shape was promised" — approval happens by merging the PR, a human
   gate.
4. **Writes back to the repo**: one idempotent PR comment with an
   ADK/Gemini-narrated impact story plus generated, mergeable
   compatibility code — `*_compat` / `*_legacy` dbt views and schema.yml
   tests that keep old consumers alive through the change.

Two invariants make it trustworthy rather than magical:

- **DataHub only ever reflects reality.** The PR is read locally as a
  hypothesis; nothing hypothetical is ever ingested into the graph.
- **The LLM narrates; it never scores and never authors merged code.**
  Severity and codegen are deterministic and unit-tested. The agent's
  writes are proposals gated on human approval — 0 unattended production
  changes, by construction.

## How we built it

- **Pipeline:** Python 3.11, ~1,300 lines of core agent code, run
  entirely inside the consumer's GitHub Actions runner by a composite
  action (`action.yml`) — no hosted service anywhere. Any dbt repo
  adopts it with one `uses:` block; our repo dogfoods its own action.
- **DataHub integration, four distinct paths:**
  - **Agent Context Kit** (`datahub-agent-context[google-adk]`,
    `build_google_adk_tools`, read-only) gives the ADK narrative agent
    live lineage/queries/schema/search tools in-process.
  - **Direct GraphQL** for the deterministic pipeline reads and the
    `upsertDataContract` writeback (with SDK aspect-emission fallback
    stamping PROPOSED provenance) — the paths the Kit doesn't expose.
  - **MCP Server** (`mcp-server-datahub`): the judge-facing interactive
    surface. `.mcp.json` ships preconfigured — point Claude/Cursor at
    the demo catalog and interrogate the same lineage and PROPOSED
    contract the guardian used.
  - **Ingestion** (dbt + business-glossary sources) seeds the demo
    reality: dbt tests become assertions backing the contract; glossary
    versions are the semantic-drift baseline.
- **Narrative:** Google ADK `Agent` on Gemini, first-party DataHub
  tools. Offline (fork PRs get no secrets) the agent degrades to a
  deterministic renderer against committed fixtures — the full comment
  still renders and lands in `$GITHUB_STEP_SUMMARY`.
- **Demo world:** a fiction-retail dbt project (seeds → staging →
  `fct_orders` → `revenue_daily`) on BigQuery, with a formal business
  glossary attached via dbt `meta`.
- **Change detection** reuses dbt's own `state:modified` semantics via
  manifest diff (`dbt parse`, no warehouse creds needed in CI), not a
  reinvented differ.

## Challenges we ran into

- **DataHub's contract-proposal inbox is Cloud-only.** We verified
  mid-design that `proposeDataContract` doesn't exist on self-hosted
  OSS. Rather than fake it, we upsert the contract with an explicit
  PROPOSED status aspect and made *PR merge* the approval gate — the
  human approval moved to where humans already are.
- **Assertions live on the wrong URN.** Live verification against a
  real OSS instance showed dbt-test assertions attach to the dbt
  *sibling* URN, not the warehouse dataset URN. The client now merges
  both siblings before contract assembly.
- **`upsertDataContract` rejects unknown keys.** Our provenance fields
  had to move out of the upsert input into a separate status aspect
  emitted via the SDK.
- **`dbt docs generate` silently overwrites `run_results.json`** —
  which destroyed test results before ingestion. Run order now: tests
  last, then ingest.
- **Empty env vars are not absent env vars.** The composite action
  exported empty-string warehouse inputs, which silently defeated
  `profiles.yml` defaults. Fixed by only exporting non-empty inputs and
  env-indirecting everything (no direct `${{ }}` interpolation in run
  scripts — also an injection-surface fix).
- **Dead ends we backed out of** (documented in `docs/SPEC.md`): AWS
  Strands (no DataHub integration exists) and Gemini's managed
  Antigravity agent (no `mcp`/`function_calling` support at the time we
  checked). Verifying vendor claims before building on them saved the
  schedule twice.

## Accomplishments that we're proud of

- **The demo asymmetry works end-to-end:** the staged breaking PR
  (column rename + silent metric redefinition + glossary drift) passes
  repo-internal CI green, and the guardian catches all three from
  metadata alone. That asymmetry *is* the pitch.
- **Full live-loop verification** against a real self-hosted DataHub +
  BigQuery: lineage traversal, sibling dedupe, glossary drift,
  `upsertDataContract` + PENDING status aspect all confirmed working,
  contract inspectable via OpenAPI.
- **26/26 deterministic tests passing** in 0.2s — severity scoring and
  codegen are fully unit-tested precisely because no LLM touches them.
- **Offline mode is first-class, not a degraded afterthought:** a fork
  PR with zero secrets still renders the complete impact comment from
  committed fixtures.
- **Generated code is mergeable as-is:** real compat/legacy views +
  schema.yml tests in `examples/generated/`, produced from an actual
  run — with a `requires_human` flag for the cases codegen honestly
  can't map.
- **[MEASURE] end-to-end Action latency** on the demo PR (detect →
  comment posted): measure one real run and put the number here.
- **Total infrastructure cost under $75** for the full judging window
  (self-hosted OSS DataHub on one GCE VM; BigQuery free tier).

## What we learned

- **The metadata graph is the only honest source of blast radius.** We
  went in planning to be clever about detection; the durable insight is
  that detection is easy and *consequence* is the hard part — and
  consequence is precisely what lineage + observed queries give you and
  nothing else does.
- **"Reality vs hypothesis" is a design principle, not a slogan.** The
  moment you're tempted to ingest a PR branch's state into the catalog
  "just for the demo," you've built a machine that pollutes its own
  source of truth. Keeping DataHub reality-only simplified every
  downstream decision.
- **Verify platform claims before you architect on them.** Three
  separate times (proposal inbox, Antigravity tool support, assertion
  URN placement) the documented-or-assumed behavior differed from what
  the running system does. The checks each cost an hour; not doing them
  would have cost the design.

## What's next

- **Prod-manifest refresh as a main-branch workflow** — it's a script
  today; automating it is the obvious next step and the one thing a
  real adopter would ask for first.
- **Query-usage ingestion in the live demo** so `listQueries` returns
  observed reads live (fixtures carry that part of the story today).
- **Richer rename detection** — today's heuristic handles the
  1-removed/1-added case and honestly flags the rest for a human;
  column-level lineage could close the gap.
- **The one-click demo UI** (a button that opens a real breaking PR and
  narrates the run live) — the GitHub-API client and mock server are
  already built and tested in `tools/demo_ui/`.

## Built with

`python` · `google-adk` · `gemini` · `datahub` · `datahub-agent-context`
· `mcp` · `dbt` · `bigquery` · `github-actions` · `graphql` ·
`docker`

*(check Devpost's tag autocomplete for exact canonical tag names at
form-fill time)*

## Try it out

- **Repo:** https://github.com/jwlai-cloud/downstream-impact-guardian
- **Watch the bot work:** open a PR from `demo/breaking-change` →
  `master` (read access suffices — no fork needed). CI is green; the
  guardian's comment shows what CI can't see.
- **Bring your own agent:** point Claude/Cursor at the demo catalog via
  the preconfigured `.mcp.json` (DataHub MCP Server) and interrogate
  the same lineage, glossary, and PROPOSED contract.

---

## Appendix — video script notes (NOT part of the Devpost form)

**"The edge" segment (~25s VO), place after the demo comment reveal,
before the adoption snippet:**

> Pinterest built an entire framework to treat schema as a cross-system
> contract — automated evolution, regenerated code, human-gated PRs. It
> works because Pinterest owns the whole pipeline, end to end. And even
> then it stops at structure: no lineage, no semantics, no idea *who
> breaks downstream*.
>
> Most data teams don't own a pipeline. They own a dbt repo.
>
> Downstream Impact Guardian answers the question that framework leaves
> open — who breaks? — using the only system that knows: the metadata
> graph. Schema, metric, and meaning. Checked at PR time, before
> anything ships.

On-screen beats: `Pinterest: schema = cross-system contract ✓` →
`but: no lineage · no catalog · structure only` →
`the missing half = DataHub`.

Full structured comparison (similar/different/honest-framing):
docs/SPEC.md §12.
