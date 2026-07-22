# The PR looks fine. Your catalog knows better.

*Notes from building Downstream Impact Guardian — a PR bot that reads
DataHub to figure out who you're about to break. What we designed, what
we got wrong, and how "you're safe" became the hardest feature.*

*(Built for the DataHub Agent Hackathon. Code:
[jwlai-cloud/downstream-impact-guardian](https://github.com/jwlai-cloud/downstream-impact-guardian),
Apache 2.0.)*

---

## Where this comes from

I work on a data team. We sit in the middle of the pipeline, which means
we get hit from both directions.

Upstream, the ingestion team ships a change. If it's a schema change,
our models fail loudly. Annoying, but fine — loud failures page someone.
The bad ones are quiet: someone tweaks the logic of one field, every
query still runs, and three weeks later an analyst says "this revenue
number looks weird." Then you spend days walking the chain backwards.
Dashboard, mart, staging, ingestion. I've done that walk. Everyone on a
data team has done that walk.

And to be fair: we do the same thing to the people downstream of us.
We change a model, forget to tell the analytics team, and some legacy
dashboard quietly goes wrong. Nobody's malicious. There's just no
mechanism.

The thing that took me too long to accept: **the repo can't fix this.**
Our CI was green every single time. Of course it was — nothing *in the
repo* broke. The scheduled query that broke belongs to finance. The LTV
table belongs to marketing. Different repos, different teams, and none
of us can see each other's code. The only place the whole dependency
graph exists is the catalog.

So the bot does one thing: on every dbt PR, it reads DataHub for what's
actually live, reads the PR for what's proposed, and posts a comment
about who gets hurt. DataHub is reality, the PR is a hypothesis. We
never ingest PR state into the catalog. That rule saved us from a bunch
of bad ideas.

## "Breaking change" is three different problems

First design mistake: we called everything a breaking change. That word
buries the distinction that actually matters to whoever's downstream:

- **Breaking** — column removed/renamed, model deleted. Your query
  errors. You notice today.
- **Metric drift** — logic changed, columns didn't. Your query runs
  fine and the number is silently different. You notice at the end of
  the quarter, maybe. This is the expensive one.
- **Semantic drift** — the *definition* moved. The glossary says gross
  revenue includes refunds; the PR's yml now says it doesn't. Plus the
  variant that's most of real life: someone changes the logic of a
  term-bound column and doesn't touch the glossary at all. We flag that
  as *suspected* drift — the forgot-the-glossary case.

Mechanically it's boring, which is the point. Schema and logic come from
diffing the committed prod manifest against the PR's manifest (`dbt
parse`, no warehouse creds in CI). We added sqlglot to diff the SELECT
expression per column, so the report can say "logic changed in
`avg_order_value`" instead of "SQL modified, good luck." Semantics come
from comparing the PR's glossary yml against what's live in DataHub.

## Severity ≠ impact

We almost shipped one rating for everything. Bad idea. Ended up with
two, and they answer different questions:

**Severity** rates the PR. LOW to CRITICAL. It's a dumb additive score
on purpose — breaking +3, each observed query that will break +3, each
consumer +1, and so on. You can read the weights in one screen of code.
The LLM is not allowed anywhere near it.

**Impact level** rates each victim. What happens to *this* dashboard:
BROKEN (errors), DISTORTED (runs, wrong numbers), ADVISORY (meaning
moved).

"How bad is this change" and "what happens to you specifically" are
different questions. Mixing them into one number was making both answers
worse.

## The part where I argued with my own table

Here's the problem I kept coming back to: without column-level lineage,
per-consumer impact is a guess. A dashboard that only reads `order_id`
survives the `order_total` rename completely. Table-level lineage can't
see that, so the classifier stamps it BROKEN anyway. A review bot filed
the same complaint against our own PR a few hours after I did.

We could have shipped it and looked precise. Instead the column header
literally says **"Worst-case impact"** and there's a footnote explaining
what would tighten it. My rule of thumb: an advisory tool is allowed to
over-warn, but it has to *tell you* it's over-warning. Silent
under-warning is how you lose trust; fake precision is worse.

Then we turned the limitation into a ladder:

```
declared  >  derived  >  worst-case
 (facts)     (roadmap)    (default)
```

**Worst-case** you get for free, always. **Derived** is column-level
lineage — DataHub can build column-to-column edges at ingestion (it
runs its own SQL parser), and then you query lineage from the changed
*column's* urn instead of the table's. That's on the roadmap; it's one
ingestion flag plus one query change, but it needs re-ingestion and
verification we didn't want to rush before the deadline.

**Declared** is the one we shipped, and it's my favorite thing in the
project. A consumer declares which upstream columns it reads, in its own
dbt yml:

```yaml
models:
  - name: customer_ltv
    config:
      meta:
        depends_on_columns:
          fct_orders: [order_total, customer_id]
```

Their normal ingestion puts that on their DataHub entity. The guardian
intersects it with the changed columns. Match → BROKEN, as a fact.
No match → **SAFE**. 

SAFE is the verdict I didn't know I wanted until it existed. Every other
row in the report is a warning. This one is the bot telling a team "this
change does not touch you, go back to work" — and it can only say that
because the team told it what they depend on. The incentive loop closes
itself: declaring your dependencies is how you stop getting worst-cased.

Declarations rot, obviously — SQL evolves, yml doesn't. But the bot
already sees observed queries per column, so it can notice "you query
`order_total` but never declared it" and suggest the fix. Same trick as
the suspected-drift flag. I keep coming back to this pattern: the agent
generating the governance it depends on, instead of assuming somebody
else did the homework.

## Tell people, don't just count them

The blast-radius table originally listed victims with no phone numbers.
Useless. DataHub has ownership on every entity, so now each row carries
the owners to inform — and if an entity has *no* owner, the row says
**unowned** in bold, because that's a finding, not a formatting problem.

The rest of the informing protocol is deliberately unexciting: comment
on every PR, one Slack message on HIGH/CRITICAL if you configured a
webhook, strict mode blocks CRITICAL until you adopt the generated
compat code, and a proposed Data Contract lands in the catalog as the
durable record for whoever joins next quarter.

About that compat code: the bot never just says no. It generates
`*_compat` and `*_legacy` dbt views that keep the old shape and old
logic alive so downstream teams can migrate on their own schedule. When
it can't map something automatically, it writes a FIXME into the SQL and
flags the artifact instead of shipping something silently broken.

## Three things I'd tell you over coffee

**Check vendor docs against the running system.** Three times the docs
said one thing and reality said another: a mutation documented as
Cloud-only that works fine on self-hosted OSS, test assertions attaching
to a different sibling entity than we assumed, and `dbt docs generate`
silently overwriting `run_results.json` (run `dbt test` last, or your
assertions never ingest). Each check took an hour. Guessing would have
cost the architecture.

**Your own tooling should be allowed to catch you.** The day we added
unit tests to CI, they caught *me* — well, caught our side — merging the
one PR the guardian had marked CRITICAL. It was the staged demo PR,
merged by reflex minutes after its check went green. CI failed on the
next PR because master's state now contradicted the fixtures. Reverted
in minutes. Demo PRs are drafts now — GitHub won't let you merge a
draft. Best product demo we never planned.

**Honest labels compound.** Every time we picked the honest label over
the impressive one — "worst-case impact," "offline fixture mode,"
"needs human attention" — that honesty later became the exact seam where
a better feature attached. SAFE only makes sense because worst-case
admitted it was worst-case.

---

*It's a composite GitHub Action — one `uses:` block in any dbt repo, no
hosting, the CI runner is the compute. There's an independent consumer
repo with three standing demo PRs (rename, whole-model deletion, silent
metric drift) if you want to watch it judge something real.*
