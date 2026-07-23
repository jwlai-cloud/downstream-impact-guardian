# Devpost submission — Downstream Impact Guardian

> Draft. Numbers marked `[MEASURE]` need a real measured value before
> submitting — do not invent them. Structure follows Devpost's fixed
> section order; don't reorder.

**Track (primary):** Agents That Do Real Work
**Track (secondary claim, in description only):** Metadata-Aware Code
Generation & Development

---

## Inspiration

We're a data team, and we live in the middle of the blast zone. Upstream,
the ingestion team ships a change: if it's a sudden schema change, our
transformations fail loudly — annoying, but at least it pages someone. The
worst case is quieter: a *minor logical change to a field* slips through,
every query still runs, and the damage surfaces as **incorrect measures**
in the downstream data layer. The assumptions broke; nobody had a data
contract saying they couldn't. Weeks later an analyst or a business user
notices a number that feels wrong, and someone gets to spend days tracing
it back — dashboard, to mart, to staging, to ingestion.

And we're not innocent either: our own layer's changes break legacy
dashboards downstream whenever we forget to tell the analytics team. Same
failure, one seat over.

The repo told the truth the whole time: *nothing in this repo broke.* The
repo just couldn't see the finance team's scheduled query, the ML feature
pipeline, or the exec dashboard reading from that table. DataHub is the
source of truth for that cross-system picture — what we needed was an
agent that cross-references it on every PR: not just schema, but columnar
logic and semantic definition changes too.

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

**Demo scale, honestly.** The demo world is deliberately small: a
four-model dbt project, and the downstream dashboard/query lineage in
offline mode comes from mocked fixtures (clearly labeled in the report).
Don't let the size hide the shape of the real problem. In production this
is **multiple repos, thousands of models, and Looker dashboards
everywhere** — and each team has access to only a few of those repos, so
*no one* can see the whole graph from where they sit. That's precisely why
the agent's judgment must come from the catalog and not the codebase:
DataHub is the catalog center, the source of truth for what's live, and
the historical snapshot reference for what changed. The agent's
architecture is scale-independent — it reads whatever lineage the catalog
holds, whether that's four models or four thousand.

**The impact design, in four moves** (the part reviewers should slow
down on):

1. **Two orthogonal ratings.** *Severity* is PR-level (LOW→CRITICAL,
   deterministic score — drives advisory vs strict). *Impact level* is
   per-consumer: 🔴 BROKEN / 🟠 DISTORTED / 🟡 ADVISORY, honestly labeled
   as the worst-case upper bound from the upstream change kind.
2. **Stakeholders come from the catalog.** Each impacted consumer's
   DataHub owners appear right in the blast-radius table — and an
   *unowned* consumer is surfaced as a governance finding, never hidden.
   The informing protocol: comment always; Slack webhook on
   HIGH/CRITICAL; strict mode blocks CRITICAL; the Data Contract stays
   the durable record.
3. **Column-level evidence today.** sqlglot expression diffing attributes
   logic changes to specific fields; observed queries are matched per
   column; a Column-level effects table shows facts, not inference.
4. **A precision ladder for consumer impact** — *declared* > *derived* >
   *worst-case*. Declared is SHIPPED: consumers state what they read via
   `depends_on_columns` in their own dbt meta (ingested as custom
   properties); the guardian intersects with changed columns — match =
   BROKEN as fact, no match = 🟢 **SAFE**, the one verdict worst-case can
   never give. Derived (column-level lineage from the changed column's
   schemaField urn) is the roadmap rung; worst-case is always available.
   Each rung degrades honestly to the one below, and the agent audits
   declarations against observed queries — manufacturing the governance
   it consumes.

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
- **Column-expression diffing (removing the due-diligence dependency).**
  Semantic drift detection currently leans on glossary terms being
  attached — one act of human diligence per column. Parsing model SQL
  (sqlglot) to map each column to its expression would make "which
  field's logic changed" metadata-free, with the LLM classifying
  meaning-altering vs mechanical changes — and would let the guardian
  *invert* the diligence problem: spot metric-shaped columns with no
  glossary term and propose one, manufacturing the governance it relies
  on.
- **The one-click demo UI** (a button that opens a real breaking PR and
  narrates the run live) — the GitHub-API client and mock server are
  already built and tested in `tools/demo_ui/`.
- **Incident memory as a temporal knowledge graph.** DataHub's aspects
  are event-sourced; layering a Graphiti-style bi-temporal graph over the
  guardian's findings would let the agent remember incidents across PRs —
  "this table's contract has been broken three times, twice by the same
  upstream job" — turning per-PR judgment into longitudinal judgment.

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
- **Read the design story:** the full write-up — inspiration, design
  decisions, architecture, code walkthrough, and what each demo scenario
  actually outputs — lives at
  [`docs/blog/2026-07-23-designing-honest-blast-radius.md`](blog/2026-07-23-designing-honest-blast-radius.md).

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

**Design-intro beat (~15s VO), place between the comment reveal and the
architecture flash:**

> Under the hood: severity for the PR, impact level per victim — broken,
> distorted, or advisory — each with the owners to inform, pulled from
> DataHub. Column-level evidence from SQL parsing and observed queries.
> And when a consumer declares the columns it reads, the guardian can say
> the one thing every data team wants to hear: you're safe.

On-screen beats for it: `Severity → the PR` · `Impact → each victim` ·
`Stakeholders → from the catalog` · `declared > derived > worst-case`.

On-screen beats: `Pinterest: schema = cross-system contract ✓` →
`but: no lineage · no catalog · structure only` →
`the missing half = DataHub`.

Full structured comparison (similar/different/honest-framing):
docs/SPEC.md §12.

### Shot list (~2:50 total — verify the platform's hard limit before locking)

**Recording strategy: capture everything RAW at natural speed, then
accelerate in post** (`ffmpeg setpts` speed-ramps; dead time excised, not
skipped on camera). Raw captures stay in `video/raw/` (gitignored) so any
beat can be re-cut without re-shooting. GitHub scrolls driven by
Playwright, not hand-mousing — deterministic re-takes.

Sources: tab A = GitHub PR #5 · tab B = Actions run · tab C = DataHub UI
(local quickstart) · tab D = how-it-works artifact · T = terminal ·
S = static diagram.

| # | Time | Src | On screen | Narration / overlay | Technique |
|---|---|---|---|---|---|
| 1 | 0:00–0:08 | S | Black slate → title | "Every data team has lived this PR." | title fade-in |
| 2 | 0:08–0:20 | A | PR #5 diff, slow scroll over the 3 changes | "A column rename. A metric quietly redefined. A glossary edit. Tests pass. CI is green." | raw scroll @1×, cut tight |
| 3 | 0:20–0:28 | A | Checks section, bot reviews visible, all green | "Nothing in this repo knows anything is wrong." | highlight box on green checks |
| 4 | 0:28–0:40 | B | Action run: steps executing start-to-finish | "On every PR, the guardian wakes up inside GitHub Actions — no server, no bot host." | **raw 48 s → 8× ≈ 6 s** timelapse, then 1× on the final green step |
| 5 | 0:40–1:00 | A | Comment reveal: 🔴 CRITICAL header | "It read DataHub — and found what the repo can't see." | hard cut, zoom-in on severity line |
| 6 | 1:00–1:15 | A | Blast radius table | "A finance dashboard. A marketing feature table. The board pack. None of them live in this repo." | Ken Burns across table rows |
| 7 | 1:15–1:30 | A | "Queries that WILL break" section | "These are real observed queries — they still reference the old column. Guaranteed breakage." | highlight box on `order_total` in SQL |
| 8 | 1:30–1:45 | A | Semantic drift + generated compat view | "And it doesn't just warn — it writes the fix. A compat view, mergeable as-is." | zoom on `order_amount_usd as order_total` |
| 9 | 1:45–2:00 | C | DataHub lineage graph → contract entity (PENDING + provenance) | "Writeback two: a Data Contract, proposed into the catalog — the next team inherits the knowledge." | raw UI nav @1×, speed-ramp 2× between screens |
| 10 | 2:00–2:25 | S/D | Architecture diagram, then Pinterest edge beats | Edge segment VO (appendix above) — end on the scale line: "The demo is four models and mocked dashboards — honestly labeled. Production is thousands of models across repos no single team can see. That's why the judgment comes from the catalog, not the codebase." | text-overlay beats: `Pinterest ✓` → `no lineage · structure only` → `missing half = DataHub` → `4 models here · 4,000 in prod · same agent` |
| 11 | 2:25–2:33 | T | `pytest -q` → `26 passed in 0.2s` | "Deterministic core — the LLM narrates, it never scores and never writes the merged code." | big number overlay: **26 tests · 0.2 s** |
| 12 | 2:33–2:43 | S | Adoption `uses:` block | "One block in any dbt repo. The runner is the bot." | code overlay, typewriter reveal |
| 13 | 2:43–2:50 | S | Repo URL + "open the demo PR yourself" | "Downstream Impact Guardian. The PR looks fine. DataHub knows better." | hold ≥5 s, readable |

Post checklist: sound-off watchability pass; every number matches this doc
(26 tests, CRITICAL 22, 48 s run); total runtime under the platform limit.
