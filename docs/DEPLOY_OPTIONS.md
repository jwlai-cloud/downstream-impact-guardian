# Judge-facing DataHub — deployment menu

One decision, many vendors. The workload is fixed: a single Ubuntu box
with 16 GB RAM running the Docker quickstart for the judging window
(Aug 17–31, ideally soaking from ~Aug 10 ≈ 500 hrs). Everything after
"the box exists" is identical on every option:

```
scripts/oracle_vm_setup.sh   # plain Ubuntu + Docker + quickstart, any vendor
→ harden (password, METADATA_SERVICE_AUTH_ENABLED, judge read-only token)
→ scripts/ingest_all.sh
→ gh secret set DATAHUB_GMS_URL / DATAHUB_GMS_TOKEN  (both repos)
→ re-trigger demo PRs → live mode
```

Hardening and ingest steps are written once in `ORACLE_BRINGUP.md`
(steps 5+); `AWS_BRINGUP.md` covers the AWS-specific launch. Pick a row,
follow its launch notes, then join the shared path above.

## The menu

| Option | Spec | Cost (through Aug 31) | Launch notes | Catch |
|---|---|---|---|---|
| **Hetzner Cloud CAX31** | 8 vCPU / 16 GB arm64 | **~€7.34/mo ≈ $16 total** | Console → new project → CAX31, Ubuntu 24.04; firewall: 22 (your IP), 9002, 8080 | EU/US regions only; signup sometimes asks ID verification |
| **Oracle Always Free A1.Flex** | 4 OCPU / 24 GB arm64 | **$0** | `ORACLE_BRINGUP.md` end-to-end (incl. the dual-firewall trap) | Signup fraud filter rejected the debit card; needs a credit-card retry; Always-Free arm capacity is a lottery in popular regions |
| **Local Mac + Cloudflare Tunnel** | the laptop that already runs it | **$0** | `cloudflared tunnel` exposing 9002 + 8080 — no ports opened, TLS for free | Laptop must stay awake and online the whole window; one sleep = judges see a dead link |
| **GCE e2-standard-4** (agent-era project) | 4 vCPU / 16 GB x86 | ~$0.13/hr ≈ $67 | Console → Compute Engine, Ubuntu 24.04; firewall rules for 22/9002/8080 | Same price class as AWS — no advantage unless free credits appear |
| **AWS EC2 t4g.xlarge** | 4 vCPU / 16 GB arm64 | ~$0.13/hr ≈ $65 (credits offset) | `AWS_BRINGUP.md` end-to-end | Only worth it if credits actually cover it |
| **No live instance** — video + repo as evidence | — | **$0** | Nothing to launch; demo PR reports + offline fixture mode + video carry the proof | Rules explicitly permit this (judges aren't required to test live) — but drops the MCP "interrogate the catalog" judge path and live UI |

All 16 GB class boxes at the big-3 clouds price out the same (~$60–70
for 500 hrs) — the real cost lever is the vendor, not the instance
tuning. 8 GB boxes swap under the full quickstart stack; don't downsize.

Cost trims that apply to any paid row:
- **Soak later**: start Aug 16 instead of Aug 10 → ~360 hrs (−30%).
- **Stop (don't terminate) when idle** pre-judging; keep the address
  stable (Elastic IP / static IP / Hetzner keeps IP while stopped —
  note Hetzner bills stopped servers unless deleted, but at $8/mo it
  hardly matters).

## Recommendation

1. **Hetzner CAX31** — a real 24/7 server for roughly the price of two
   coffees; no signup fight reported, no credit gymnastics.
2. **Oracle retry with a credit card** if $0 matters more than the
   signup hassle.
3. **Cloudflare Tunnel** only if no card option works — it's free but
   fragile (human-must-keep-laptop-awake is a bad SLA for a 2-week
   window).
4. Video+repo-only is the floor, not a goal — the offline mode already
   guarantees the Action demo works without any instance; the live
   instance is what unlocks the MCP judge path and the button UI.

ADR-0003's self-hosted-OSS decision is unchanged by any row — only the
box vendor moves.
