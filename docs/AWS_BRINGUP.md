# Judge-facing DataHub on AWS (the credits route)

EC2 + Docker quickstart — same shape as the Oracle/GCE plans, funded by
AWS credits. Everything after the box exists is shared with
`ORACLE_BRINGUP.md`: same setup script, same hardening, same
`scripts/ingest_all.sh`, same repo secrets.

**Why EC2 over EKS/ECS:** DataHub's helm chart is the production path,
but for a 3-week judging window a single quickstart VM is simpler,
cheaper, and identical to what we live-verified locally. Don't
over-platform a demo.

## 1. Launch the instance (Console → EC2 → Launch)

- **AMI**: Ubuntu Server 24.04 LTS
- **Type**: `t4g.xlarge` (4 vCPU / 16 GB, ARM — arm64 images verified on
  our local quickstart; ~$0.13/hr ≈ $95/mo before credits). If you
  prefer x86: `t3.xlarge` (~$0.17/hr). **Not** `*.large` — 8 GB swaps
  under the full stack.
- **Key pair**: create/download one for SSH.
- **Storage**: 60 GB gp3.
- **Security group** (inbound):
  | Port | Source | Purpose |
  |---|---|---|
  | 22 | your-ip/32 | SSH |
  | 9002 | 0.0.0.0/0 | DataHub UI (judges) |
  | 8080 | 0.0.0.0/0 | GMS API (Action + MCP; token-gated after step 3) |
- Optional: allocate + associate an **Elastic IP** so the address
  survives stop/start (secrets reference it).

No dual-firewall trap here — unlike Oracle, Ubuntu AMIs on AWS ship
without a REJECT-all iptables layer; the security group is the whole
story. The setup script's iptables lines are harmless no-ops.

## 2. Install (from your Mac)

```bash
scp -i <key.pem> scripts/oracle_vm_setup.sh ubuntu@<ec2-ip>:
ssh -i <key.pem> ubuntu@<ec2-ip> bash oracle_vm_setup.sh
```

(The script is plain Ubuntu + Docker + quickstart — nothing
Oracle-specific despite the name.) ~5–10 min, then
`http://<ec2-ip>:9002`, login `datahub`/`datahub`.

## 3. Harden — before the ports are meaningfully public

Same as ORACLE_BRINGUP steps 5 + security section:
1. Change the default password (UI → Settings → Users & Groups).
2. `METADATA_SERVICE_AUTH_ENABLED=true` on datahub-gms, restart stack.
3. Create a read-only **judge** user + token (expiry Sep 1) — that pair
   goes in the Devpost testing field; the admin token goes in repo
   secrets only.
4. Plain-HTTP caveat applies (bearer token on the wire): acceptable for
   a disposable fiction-data demo; Caddy + a domain if you want TLS.

## 4. Ingest + wire (from your Mac)

```bash
DATAHUB_GMS_URL=http://<ec2-ip>:8080 DATAHUB_GMS_TOKEN=<admin-token> \
  bash scripts/ingest_all.sh
gh secret set DATAHUB_GMS_URL  -R jwlai-cloud/downstream-impact-guardian   # and fiction-retail-dbt
gh secret set DATAHUB_GMS_TOKEN -R jwlai-cloud/downstream-impact-guardian  # and fiction-retail-dbt
gh variable set GCP_PROJECT -R jwlai-cloud/downstream-impact-guardian --body "agent-era"
gh variable set BQ_DATASET  -R jwlai-cloud/downstream-impact-guardian --body "fiction_retail"
```

Re-trigger a demo PR → live mode.

## 5. Cost control with credits

- Judging window Aug 17–31 + soak from ~Aug 10: ~500 hrs × $0.13 ≈
  **$65 on t4g.xlarge** — well inside typical credit grants.
- **Stop** (not terminate) the instance when idle before Aug 10; with an
  Elastic IP the address — and therefore the secrets — stay valid.
  Stopped cost ≈ EBS pennies (+ small Elastic-IP idle fee).
- Terminate + release the Elastic IP after Aug 31.

## Decision status

Supersedes the Oracle plan as plan A while credits exist (no signup
fraud-filter fight, no Always-Free capacity roulette). ORACLE_BRINGUP.md
stays as the $0 fallback. ADR-0003's self-hosted-OSS decision is
unchanged — only the box vendor moved.
