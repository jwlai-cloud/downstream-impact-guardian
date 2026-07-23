# Example output — offline fixture mode

These files are the guardian's real output from an **offline fixture-mode
run** (no DataHub credentials): that is why `contract_payloads.json`
records `recorded-offline` with `urn: null` — in offline mode the exact
contract payload is recorded in the report instead of being upserted
(ADR-0007).

For **live-mode** output — real lineage, owners, Qwen-written narrative,
and contracts actually upserted with URNs — see the checked-in verified
runs the judge workbench serves: [`site/reports/`](../../site/reports/)
(rendered at
[jwlai-cloud.github.io/downstream-impact-guardian](https://jwlai-cloud.github.io/downstream-impact-guardian/)).
