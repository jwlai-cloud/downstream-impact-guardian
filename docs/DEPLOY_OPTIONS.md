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
| **No live instance** — video + repo as evidence | — | **$0** | Nothing to launch; demo PR reports + offline fixture mode + Pages judge workbench + video carry the proof | Officially fine — organizer confirmed in Slack (2026-07-13): "live hosted URL isn't required — a public GitHub repo with clear setup instructions works, and judges can evaluate from your demo video too." Drops the MCP "interrogate the catalog" judge path and live UI |

All 16 GB class boxes at the big-3 clouds price out the same (~$60–70
for 500 hrs) — the vendor is one cost lever, but **instance size is the
bigger one**: superseding this section's original advice, an **8 GB box
does run the full quickstart stack** for a dataset this small, provided
4 GB swap and `vm.max_map_count=262144` are configured. That halves the
bill (see RESOLVED above). The rows below still quote 16 GB specs as
originally surveyed; read them as upper bounds, not requirements.

Cost trims that apply to any paid row:
- **Skip the soak**: start ~Aug 16 rather than Aug 10 → ~360 hrs (−30%).
  What we actually do: keep the box **stopped** until then.
- **Stop (don't terminate) when idle** pre-judging; keep the address
  stable (Elastic IP / static IP / Hetzner keeps IP while stopped —
  note Hetzner bills stopped servers unless deleted, but at $8/mo it
  hardly matters).

## RESOLVED (2026-07-26) — AWS EC2 `t4g.large`, deployed

The judge-facing instance is **live on AWS**, in the maintainer's personal
account (`us-east-1`), and the whole chain has been verified against it
(`mode=live`, CRITICAL 24, both contracts upserted, real Qwen narrative,
Slack alert, comment posted).

- **`t4g.large`** — 2 vCPU / 8 GB arm64 + **4 GB swap**, 40 GB gp3.
  Correcting the "don't downsize to 8 GB" note above: 8 GB *does* hold the
  full quickstart stack for a dataset this small (4 models, ~10 entities)
  once swap and `vm.max_map_count=262144` are set. Idle footprint is
  ~4.3 GB of 7.6 GB. `t4g.xlarge` remains a 2-minute resize away
  (stop → modify type → start) and the Elastic IP survives it, so no
  secret changes are needed if it ever proves tight.
- **~$0.067/hr ≈ $1.60/day** running, ~$0.11/day stopped (EBS only).
  Aug 17–31 continuous ≈ **$24**, well inside the $75 ceiling.
- **Elastic IP** so the URL survives stop/start — both repos' secrets stay
  valid across restarts.
- Why AWS over the cheaper Hetzner row: the account already existed, so
  there was **no signup/ID-check risk** before the deadline, and the whole
  bring-up (launch → harden → ingest → wire → teardown) is scriptable via
  the CLI. Hetzner would have been ~$16 but needed a new account.

Access and hardening details: [`AWS_BRINGUP.md`](AWS_BRINGUP.md).
Judge-facing routes: [`JUDGING.md`](JUDGING.md). Credentials live in the
maintainer's `~/dig-datahub-credentials.txt` and the Devpost private
testing-notes field — **never in this repo**.

Rows below remain valid as fallbacks if the instance is ever lost.
4. Video+repo-only is the floor, not a goal — the offline mode already
   guarantees the Action demo works without any instance; the live
   instance is what unlocks the MCP judge path and the button UI.

ADR-0003's self-hosted-OSS decision is unchanged by any row — only the
box vendor moves.
