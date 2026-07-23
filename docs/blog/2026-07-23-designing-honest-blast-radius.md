# The PR looks fine. Your catalog knows better.

*Building Downstream Impact Guardian — a PR bot that reads DataHub to
figure out who you're about to break, writes a Data Contract back, and
generates the code that makes the breakage painless. Inspiration, design,
architecture, some code, and what the three demo scenarios actually
output.*

*(Built for the DataHub Agent Hackathon. Code:
[jwlai-cloud/downstream-impact-guardian](https://github.com/jwlai-cloud/downstream-impact-guardian),
Apache 2.0. Demo consumer repo:
[fiction-retail-dbt](https://github.com/jwlai-cloud/fiction-retail-dbt).)*

---

## 1. Where this comes from

I work on a data team. We sit in the middle of the pipeline, which means
we get hit from both directions.

Upstream, the ingestion team ships a change. If it's a schema change, our
models fail loudly. Annoying, but fine — loud failures page someone. The
bad ones are quiet: someone tweaks the logic of one field, every query
still runs, and three weeks later an analyst says "this revenue number
looks weird." Then you spend days walking the chain backwards. Dashboard,
mart, staging, ingestion. I've done that walk. Everyone on a data team
has done that walk.

And to be fair: we do the same thing to the people downstream of us. We
change a model, forget to tell the analytics team, and some legacy
dashboard quietly goes wrong. Nobody's malicious. There's just no
mechanism.

The thing that took me too long to accept: **the repo can't fix this.**
Our CI was green every single time. Of course it was — nothing *in the
repo* broke. The scheduled query that broke belongs to finance. The LTV
table belongs to marketing. Different repos, different teams, and in a
real org — multiple repos, thousands of models, dashboards everywhere —
none of us can see each other's code. The only place the whole dependency
graph exists is the catalog.

So the bot does one thing: on every dbt PR, it reads DataHub for what's
actually live, reads the PR for what's proposed, and posts a comment
about who gets hurt.

Two rules fell out of that sentence and never changed:

1. **DataHub is reality; the PR is a hypothesis.** We never ingest PR
   state into the catalog. Ever.
2. **The LLM narrates; it never scores and never writes the merged
   code.** Severity math and code generation are deterministic and
   unit-tested. The model makes the report readable, not correct.

## 2. Design: naming the failure modes properly

### "Breaking change" is three different problems

- **Breaking** — column removed/renamed, model deleted. Your query
  errors. You notice today.
- **Metric drift** — logic changed, columns didn't. Your query runs fine
  and the number is silently different. You notice at quarter end. This
  is the expensive one.
- **Semantic drift** — the *definition* moved: the glossary says gross
  revenue includes refunds; the PR's yml now says it doesn't. Plus the
  variant that's most of real life, **suspected semantic drift**: someone
  changes the logic of a glossary-bound column and doesn't touch the
  glossary at all.

Every term lives in a checked-in glossary (`CONTEXT.md`) and the review
bots got surprisingly good at policing our own definitions against our
own code.

### Severity ≠ impact

**Severity** rates the PR: LOW→CRITICAL, a dumb additive score on
purpose. Breaking +3, each observed query that will break +3, each
downstream consumer +1 (capped), each non-warehouse platform +2, semantic
drift +2, suspected +1. You can read the whole rubric in one screen of
`blast_radius.py`. It decides advisory-vs-blocking, nothing else.

**Impact level** rates each victim: 🔴 BROKEN (errors), 🟠 DISTORTED
(runs, wrong numbers), 🟡 ADVISORY (meaning moved). "How bad is this
change" and "what happens to *you*" are different questions.

### The columnar honesty problem, and the ladder

Without column-level lineage, per-consumer impact is a guess: a dashboard
that only reads `order_id` survives the `order_total` rename, but
table-level lineage can't see that, so worst-case stamps it BROKEN. We
refused to fake precision — the report column literally says
**"Worst-case impact"** — and then built a ladder out of the limitation:

```
declared  >  derived  >  worst-case
 (facts)     (roadmap)    (default)
```

**Declared** is the shipped rung, and my favorite thing in the project.
A consumer declares which upstream columns it reads, in its own repo:

```yaml
models:
  - name: customer_ltv
    config:
      meta:
        depends_on_columns:
          fct_orders: [order_total, customer_id]
```

Their normal ingestion lands that on their DataHub entity as custom
properties. The guardian intersects declarations with the changed
columns: match → BROKEN *as a fact*; no match → 🟢 **SAFE** — the one
verdict worst-case classification can never produce. The incentive loop
closes itself: declaring dependencies is how a team stops getting
worst-cased.

Declarations rot, so the bot audits them against behavior: it already
sees observed queries per column and can suggest "you query `order_total`
but never declared it." Same trick as suspected drift. The pattern I keep
coming back to: **the agent manufactures the governance it consumes.**

### Stakeholders and the informing protocol

DataHub holds ownership on every entity, so the blast-radius table reads
consumer × worst-case impact × **owners to inform** — and an entity with
no owners prints **unowned** in bold, because that's a finding, not a
formatting gap. Protocol: comment always; one Slack message on
HIGH/CRITICAL if a webhook is configured; strict mode blocks CRITICAL
until the generated compat code is adopted; a proposed Data Contract
stays in the catalog as the durable record.

## 3. Architecture

### Distribution: the CI runner is the bot

No server anywhere. The agent is a composite GitHub Action; a consumer
integrates with one block:

```yaml
- uses: jwlai-cloud/downstream-impact-guardian@master
  with:
    dbt-project-dir: dbt
    datahub-url: ${{ secrets.DATAHUB_GMS_URL }}
    datahub-token: ${{ secrets.DATAHUB_GMS_TOKEN }}
```

The action checks out nothing itself — the consumer's checkout is the
data, `github.action_path` is the code. Two hard-won portability lessons
live in `action.yml`: never interpolate `${{ inputs.* }}` into `run:`
scripts (injection surface — every input goes through `env:`
indirection), and never export empty-string inputs (an empty env var
silently defeats `env_var()` defaults in dbt profiles — found by our
first real consumer run, invisible to dogfooding).

### The pipeline

```
detect (dbt manifests + glossary yml)          repo-side, deterministic
  → blast radius (DataHub lineage + queries    catalog-side
     + ownership + declared deps)
  → narrative (one flat ADK agent)             best-effort, 120s bound
  → writeback 1: Data Contracts (PROPOSED)     catalog-side
  → codegen: *_compat / *_legacy views         deterministic templates
  → writeback 2: idempotent PR comment         repo-side
```

ADK topology is deliberately flat: one `LlmAgent`, no sub-agent graph.
Its tools are the first-party DataHub Agent Context Kit
(`build_google_adk_tools`, mutations off — ten read tools: lineage,
queries, assertions, schema, search). The model is pluggable:
`gemini-*` ids run ADK-native; anything else (`openai/gpt-...`, Qwen via
an OpenAI-compatible base URL) routes through ADK's LiteLLM adapter.
The judged novelty is what the agent reads and writes, not the wiring.

### Five DataHub surfaces, each earning its place

| Surface | Used for |
|---|---|
| Agent Context Kit | the narrative agent's read tools, in-process |
| GraphQL | deterministic reads + `upsertDataContract` (the Kit doesn't expose contract writes) |
| Ingestion (dbt + glossary sources) | seeds reality: models, lineage, dbt tests → assertions, versioned glossary |
| SDK aspect emission | stamping `dataContractStatus` = PENDING + provenance |
| Ownership + custom properties | stakeholders and declared dependencies, fetched with lineage |

Plus MCP as the *interactive* surface: the repo ships `.mcp.json` running
`mcp-server-datahub` locally, so a judge can point Claude or Cursor at
the catalog and ask "who breaks if fct_orders drops order_total?"
themselves.

### Offline mode is a feature, not a fallback

Fork PRs get no secrets — that's GitHub's design. So the agent has a
first-class offline mode: committed fixtures shaped exactly like live
responses, the full report still renders (banner says so), and the body
always lands in `$GITHUB_STEP_SUMMARY` where comment-posting isn't
possible. Same mode let us build and test the whole pipeline before any
DataHub instance existed. 44 tests, 0.3 seconds, zero network.

## 4. Code walkthrough, the load-bearing bits

**Deleted models were invisible** until an audit noticed the diff only
visited PR-side models. The fix is a sweep over prod-only models — the
most breaking change a PR can make is now a first-class finding:

```python
# dbt_state.diff_manifests — after the PR-side loop
for uid, old in prod_models.items():
    if uid in pr_models:
        continue
    changes.append(ModelChange(
        model_name=old["name"], unique_id=uid, kinds={"removed"},
        old_sql=old.get("raw_code", ""),
        old_columns=list(old.get("columns", {})),
    ))
```

**Declared impact is a fact machine**, with the asymmetry spelled out —
a filter change moves *every* column's values, so a declaration can't
clear it:

```python
def classify_declared_impact(change, declared):
    if "removed" in change.kinds:
        return "BROKEN"                    # the relation itself is gone
    declared_set = {d.lower() for d in declared}
    if declared_set & {c.lower() for c in _changed_column_names(change)}:
        return "BROKEN"                    # your column got renamed/removed
    if "logic" in change.kinds:
        exprs = {c.lower() for c in change.changed_expressions}
        if not exprs:                      # filters/joins: everyone moves
            return "DISTORTED"
        if declared_set & exprs:
            return "DISTORTED"
    return "SAFE"
```

**The contract writeback** survived a docs-vs-reality fight. The API
tutorial frames Data Contracts as Cloud-only; live against a self-hosted
OSS quickstart, `upsertDataContract` works fine — the input just rejects
unknown keys, so PROPOSED provenance rides a status aspect instead:

```python
data = live_client.graphql(UPSERT_MUTATION, {"input": payload})
urn = (data.get("upsertDataContract") or {}).get("urn")
# then: DataContractStatusClass(state=PENDING,
#         customProperties={"proposedBy": "downstream-impact-guardian",
#                           "sourcePullRequest": pr_url})
```

Two more live-only discoveries the fixtures could never show: dbt test
assertions attach to the **dbt sibling** urn, not the warehouse entity
(the client queries both and merges), and `dbt docs generate` silently
overwrites `run_results.json` — run `dbt test` last or your assertions
never ingest.

**Codegen never says no.** A rename produces a `*_compat` view
re-exposing the old shape — sourced from DataHub's *live schema*, not the
manifest's possibly-partial column docs (that bug would have broken the
very queries the view exists to protect). Logic drift and deletions
produce `*_legacy` views carrying the old SQL, with `ref()`s retargeted
through sibling compat/legacy views so cascading changes still compile.
Anything unmappable gets a FIXME in the SQL and a `requires_human` flag —
incomplete is fine, silently broken is not.

## 5. What the demos actually output

The consumer repo integrates with the one `uses:` block above and runs
three standing draft PRs (drafts on purpose — see §6). All three reports
below were posted by the published action, cross-repo, in ~45 seconds
each.

**Scenario 1 — the classic combo**
([PR #1](https://github.com/jwlai-cloud/fiction-retail-dbt/pull/1)):
rename `order_total` → `order_amount_usd`, quietly redefine
`gross_revenue`, update the glossary. → 🔴 **CRITICAL (22)**. The report
shows the rename, per-column attribution, two observed production
queries that still reference the old column ("guaranteed breakage"),
semantic drift with both definitions quoted, two proposed contracts, and
mergeable `fct_orders_compat` + `revenue_daily_legacy` views.

<!-- TODO screenshot: PR #1 guardian comment — severity header + blast-radius table -->

**Scenario 2 — the deletion**
([PR #2](https://github.com/jwlai-cloud/fiction-retail-dbt/pull/2)):
`git rm revenue_daily.sql`, "finance says they don't use it anymore."
→ 🔴 **CRITICAL (10)**: *"revenue_daily: MODEL DELETED, 2 downstream
consumer(s); 1 observed production query still references the old
column(s) — guaranteed breakage"* — plus a generated
`revenue_daily_legacy` view so consumers keep a working relation while
they migrate. (Finance's Monthly Board Pack very much still uses it.
Only the lineage graph knew.)

<!-- TODO screenshot: PR #2 comment — MODEL DELETED narrative + legacy view -->

**Scenario 3 — the quiet one**
([PR #3](https://github.com/jwlai-cloud/fiction-retail-dbt/pull/3)):
one WHERE-clause edit, no columns touched, no glossary update, every test
green. → 🟠 **HIGH (6)** with the flag I care most about: *"suspected
semantic drift: `revenue_daily.gross_revenue` is bound to glossary term
**Gross Revenue** and its logic changed, but this PR does not update the
term."* The forgot-the-glossary case, caught deterministically.

<!-- TODO screenshot: PR #3 comment — suspected drift section -->

There's also a one-button web demo (Vercel + two serverless functions):
pick a scenario, it opens a fresh PR on a unique branch, polls the check,
and renders the guardian's comment inline.

<!-- TODO screenshot: demo UI — scenario cards + rendered report -->
<!-- TODO screenshot: DataHub UI — lineage graph + PROPOSED contract entity -->

## 6. Three things I'd tell you over coffee

**Check vendor docs against the running system.** Three times the docs
said one thing and reality said another (the "Cloud-only" contract
mutation, the sibling-urn assertions, the run_results overwrite). Each
check took an hour. Guessing would have cost the architecture.

**Your own tooling should be allowed to catch you.** The day unit tests
landed in CI, they caught our side merging the one PR the guardian had
marked CRITICAL — the staged demo PR, merged by reflex minutes after its
check went green. CI failed on the next PR because master now
contradicted the fixtures. Reverted in minutes; demo PRs are drafts now,
physically unmergeable. Best product demo we never planned.

**Honest labels compound.** "Worst-case impact," "offline fixture mode,"
"needs human attention" — every honest label later became the seam a
better feature attached to. SAFE only exists because worst-case admitted
what it was.

---

*One `uses:` block in any dbt repo. No hosting. Three standing demos.
Repo: [jwlai-cloud/downstream-impact-guardian](https://github.com/jwlai-cloud/downstream-impact-guardian).*
