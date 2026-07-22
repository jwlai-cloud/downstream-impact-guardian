# ADR-0010: Per-consumer impact levels and the stakeholder informing protocol

Status: Accepted (2026-07-22)

## Context

The blast-radius table listed *who* is downstream but not *what happens
to them* — a dashboard that errors and a dashboard that silently shows
wrong numbers were indistinguishable rows. And knowing the victims'
names wasn't actionable: nothing said *whom to talk to*. Meanwhile
DataHub already holds ownership on every entity — an integration surface
the guardian wasn't using.

## Decision

Two orthogonal ratings (CONTEXT.md):
- **Severity** stays PR-level (LOW→CRITICAL, drives advisory/strict).
- **Impact level** is per-consumer: BROKEN / DISTORTED / ADVISORY,
  worst-applicable-wins, derived from the upstream change kind
  (removed|breaking → BROKEN, logic → DISTORTED, semantic-only →
  ADVISORY).

**Stakeholder** = DataHub owners of the impacted consumer entity
(ownership aspect, fetched with lineage). No owners → the row says
**unowned**, surfacing the governance gap instead of hiding it.

**Protocol**: (1) the PR comment always carries consumer × impact ×
owners; (2) HIGH/CRITICAL severity + configured `slack-webhook-url`
input → one Slack summary message; (3) CRITICAL + `strict` → check
fails until compat code is adopted (existing gate); (4) the PROPOSED
Data Contract remains the durable, catalog-level record.

## Consequences

- v1 classifies by upstream change kind, not by whether the specific
  consumer touches the changed column — worst-case until column-level
  lineage lands (documented limitation, consistent with the
  blast-radius over-approximation).
- Ownership becomes the fifth DataHub surface the guardian reads.
- Slack is fire-and-forget best-effort: a webhook failure never fails
  the check.

## Addendum (same day): declared column dependencies — the middle rung

Between worst-case impact (shipped) and derived column-level lineage
(roadmap) sits a consumer-declared protocol: each consumer declares the
upstream columns it depends on in ITS OWN dbt yml meta
(`depends_on_columns: {fct_orders: [order_total, ...]}`), its ingestion
lands that on its DataHub entity, and the guardian matches declarations
against the changed-column list. Declared match → BROKEN as fact;
declared no-match → SAFE (a verdict worst-case can never give); no
declaration → worst-case as today. The declaration's home is DataHub —
not the producer's repo — because the consumers that matter live in
other repos and other tools. Declaration rot is mitigated the same way
as glossary diligence: the guardian sees observed queries per column and
can suggest the declaration. Read-side implementation is deliberately
deferred until after this PR merges.
