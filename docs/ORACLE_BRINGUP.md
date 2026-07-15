# Judge-facing DataHub on Oracle Cloud Always Free (the $0 route)

Alternative to ADR-0003's GCE e2-standard-2 (~$30). Oracle's Always Free
tier is the only free tier big enough for DataHub: **VM.Standard.A1.Flex,
up to 4 Ampere ARM OCPUs + 24 GB RAM per tenancy**, 200 GB block storage,
10 TB egress/month. DataHub's images are multi-arch (arm64 verified — the
quickstart runs on Apple Silicon), so ARM is a non-issue.

Two known frictions, both manageable:
1. **A1 capacity** — "Out of capacity" errors at launch are common in busy
   home regions. Mitigation: pick a less busy home region at signup (home
   region is permanent), and/or upgrade to Pay As You Go.
2. **Idle reclamation** — Oracle reclaims *Always Free tenancy* A1
   instances deemed idle for 7 days (95th-percentile CPU < 20% etc.).
   Upgrading the tenancy to **Pay As You Go removes reclamation** and
   capacity headaches while still costing $0 within free limits. Recommended
   before the judging window.

## 1. Account (one-time, ~10 min, needs your card for identity only)

1. https://signup.cloud.oracle.com → sign up, pick **home region**
   (e.g. `ap-sydney-1` or `us-phoenix-1`; avoid famously-full ones like
   Ashburn if you can).
2. After activation, optionally: Billing → **Upgrade to Pay As You Go**
   (card on file, still $0 within Always Free limits; removes idle
   reclamation + improves A1 capacity odds).

## 2. Provision the VM (Console)

Compute → Instances → **Create instance**:

- **Image**: Ubuntu 24.04 (aarch64)
- **Shape**: Ampere → `VM.Standard.A1.Flex` → **4 OCPU / 24 GB** (the whole
  free allowance in one box)
- **Boot volume**: 100 GB (free allowance is 200 GB total)
- **VCN**: accept the default new VCN with a public subnet + public IP
- **SSH key**: paste your `~/.ssh/id_ed25519.pub`

If "Out of capacity": retry in a different Availability Domain, or retry
later (capacity is released constantly), or script the retry via OCI CLI.

## 3. Open the firewall — BOTH layers (the classic Oracle gotcha)

**Layer 1 — VCN Security List** (Console → your VCN → public subnet →
Security List → Add Ingress Rules):

| Source | Protocol | Port | Purpose |
|---|---|---|---|
| 0.0.0.0/0 | TCP | 22 | SSH (already present) |
| 0.0.0.0/0 | TCP | 9002 | DataHub frontend (judges) |
| your-ip/32 + GitHub Actions* | TCP | 8080 | GMS API (agent) |

*Simplest for the hackathon: 0.0.0.0/0 on 8080 too, with metadata auth ON
(step 5). Tighter: keep 8080 open but that's what the token is for.

**Layer 2 — on-instance iptables.** Oracle Ubuntu images ship a REJECT-all
rule that silently eats traffic even when the Security List allows it:

```bash
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 9002 -j ACCEPT
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 8080 -j ACCEPT
sudo netfilter-persistent save
```

## 4. Install Docker + DataHub (on the VM) — scripted

```bash
scp scripts/oracle_vm_setup.sh ubuntu@<public-ip>:
ssh ubuntu@<public-ip> bash oracle_vm_setup.sh
```

(Does the on-instance iptables too.) ~5–10 min first pull. Then
`http://<public-ip>:9002`, login `datahub` / `datahub`.

## 5. Harden before judges arrive (public instance ≠ local toy)

```bash
# 1. change the default password: UI → Settings → Users & Groups
# 2. enable metadata-service auth so GMS (8080) requires a token:
#    quickstart compose sets this via env; easiest supported path:
~/dh/bin/datahub docker quickstart --stop
# edit ~/.datahub/quickstart/docker-compose.yml: add to datahub-gms env:
#   METADATA_SERVICE_AUTH_ENABLED=true
~/dh/bin/datahub docker quickstart   # restarts with auth on
# 3. UI → Settings → Access Tokens → Generate → this becomes
#    DATAHUB_GMS_TOKEN everywhere
```

The agent already sends the bearer token only when set (`agent/config.py`),
so nothing in the repo changes.

## 6. Ingest (from your Mac) — scripted, verified against local quickstart

```bash
DATAHUB_GMS_URL=http://<public-ip>:8080 DATAHUB_GMS_TOKEN=<token> \
  bash scripts/ingest_all.sh
```

Wraps: BigQuery build (`agent-era`, token target, ADC untouched) →
`dbt test` last (assertions gotcha) → glossary ingest (versioned on
re-run) → dbt ingest → prod-manifest refresh. Same script, any instance.

## 7. Wire the repo (GitHub → Settings → Secrets and variables → Actions)

| Secret | Value |
|---|---|
| `DATAHUB_GMS_URL` | `http://<public-ip>:8080` |
| `DATAHUB_GMS_TOKEN` | token from step 5 |
| `GOOGLE_API_KEY` | Gemini key (ADK narrative) |

Variables: `GCP_PROJECT=agent-era`, `BQ_DATASET=fiction_retail`.

Then open the judge PR (`demo/breaking-change` → `master`) and watch the
Action run in live mode.

## 8. Keep-alive through Aug 17–31

- Pay As You Go tenancy: nothing to do.
- Still on Always Free tenancy: the quickstart stack itself generates
  enough baseline CPU that reclamation is unlikely, but don't gamble the
  judging window on it — upgrade.
- After judging: Console → terminate instance (or keep it; it's $0).

## Decision status

ADR-0003 still says GCE e2-standard-2. This runbook is the $0 alternative;
if we execute it and it holds up, amend ADR-0003 rather than duplicating a
new ADR. Both paths use identical DataHub setup + ingest steps from
`dbt_demo_project/README.md` — only the box differs.
