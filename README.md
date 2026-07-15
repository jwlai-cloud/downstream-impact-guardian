# Downstream Impact Guardian

**Build with DataHub: The Agent Hackathon** — submission in progress.

An agent that catches breaking changes — schema, business logic, and semantic
definitions — *before* they land, by reading DataHub's context graph and
generating a real, mergeable fix.

## The problem

When teams change a dbt model's schema, its SQL logic, or a business glossary
definition, downstream consumers — other teams' pipelines, dashboards, ML
features — often find out only when something breaks in production. Without
proper data contracts, this is exactly the kind of silent, cross-team failure
that no single repo's CI can catch on its own, because no single repo knows
who else depends on it.

## What this agent does

Triggered on every pull request to a dbt project:

1. **Detects** what actually changed — schema (DataHub schema history), logic
   (`dbt state:modified`), and semantic definitions (DataHub glossary term
   versioning)
2. **Assesses blast radius** — cross-references DataHub lineage and query
   history to find every real downstream consumer, across systems, not just
   within this one repo
3. **Writes back to DataHub** — proposes a Data Contract formalizing the
   dependency that was just discovered, so the next person or agent inherits
   the knowledge
4. **Writes back to the repo** — posts a PR comment with a generated,
   backward-compatible migration (SQL view / dbt macro) plus tests, so a data
   team could actually merge it

## Why this needs DataHub, not just a coding agent

Any coding agent can write a compatibility view once told what changed. Only
a context platform like DataHub knows the change happened at all, in the
first place, and who else in the organization is quietly depending on the old
shape. The value here is in *knowing what to generate*, not the generation
itself.

## Status

Early build — see `docs/SPEC.md` for the full design and open questions, and
`CLAUDE.md` for the working context if you're picking this up in Claude Code.

## License

Apache 2.0 — see [LICENSE](./LICENSE).
