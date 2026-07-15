# ADR-0003: Self-hosted OSS DataHub; contract writeback via upsert/SDK with PROPOSED status

Status: Accepted (2026-07-15) · corrects docs/SPEC.md §5

## Context

Verified 2026-07-15 against `docs.datahub.com/docs/api/tutorials/data-contracts`:
the tutorial documents **only** `upsertDataContract` and states it covers
DataHub **Cloud**; `proposeDataContract` and the proposal inbox are
Cloud-only. Separately, a DataHub Cloud free trial risks expiring inside
the Aug 17–31 judging window (dev is happening now, a month earlier).

## Decision

Self-hosted OSS DataHub: Docker quickstart for development, one GCE VM for
the judging window (~$30–60, inside the $75 ceiling). Contract writeback
(writeback #1) becomes a two-attempt strategy in `agent/contract.py`:

1. `upsertDataContract` GraphQL mutation (the DataContract entity exists in
   the OSS metadata model);
2. on failure, direct `dataContractProperties` +
   `dataContractStatus` aspect emission via the acryl-datahub SDK.

Either path stamps `status=PROPOSED`, `proposedBy=downstream-impact-guardian`
and the source PR URL. The human approval gate is merging the PR — honest
to the original "a human should approve a new contract" intent without a
Cloud-only mutation. In live mode with zero assertions on the dataset the
agent refuses and says why (a contract must bundle assertions, SPEC §5).

## Consequences

No trial-expiry risk; full API control. We lose the native proposal inbox
UI — acceptable, and worth one honest line in the submission. If judging
economics change, rules explicitly permit video+repo as primary evidence.
