# Judge-facing DataHub on AWS (the credits route)

> One row of the deployment menu — see `DEPLOY_OPTIONS.md` for the
> cost comparison (Hetzner/Oracle/local-tunnel/GCE) before choosing.

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
- **Security group** (inbound) — start restricted; widen only after
  step 3 hardening (a fresh quickstart ships `datahub`/`datahub` and no
  API auth — don't publish that):

  | Port | Source at launch | After step 3 |
  |---|---|---|
  | 22 | your-ip/32 | unchanged |
  | 9002 | your-ip/32 | 0.0.0.0/0 (DataHub UI, judges) |
  | 8080 | your-ip/32 | 0.0.0.0/0 (GMS API — Action + MCP, token-gated) |

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
4. Only now widen 9002/8080 to 0.0.0.0/0 in the security group.
5. Transport: prefer **Caddy + a domain (free TLS)** so tokens never
   cross the wire in plaintext. Running plain HTTP is a documented,
   deliberate risk acceptance for this instance only: the catalog holds
   fictional demo data, the judge token is read-only, and both tokens
   expire Sep 1 and are rotated/torn down after judging — interception
   buys vandalism of a disposable fiction catalog, nothing more. Do not
   copy this trade-off to any instance with real data.

## 4. Ingest + wire (from your Mac)

```bash
DATAHUB_GMS_URL=http://<ec2-ip>:8080 DATAHUB_GMS_TOKEN=<admin-token> \
  bash scripts/ingest_all.sh

# secrets + variables must exist in BOTH repos — the consumer repo's
# workflow reads its own copies:
for repo in jwlai-cloud/downstream-impact-guardian jwlai-cloud/fiction-retail-dbt; do
  gh secret set DATAHUB_GMS_URL  -R "$repo"
  gh secret set DATAHUB_GMS_TOKEN -R "$repo"
  gh variable set GCP_PROJECT -R "$repo" --body "agent-era"
  gh variable set BQ_DATASET  -R "$repo" --body "fiction_retail"
done
```

Re-trigger a demo PR → live mode.

## 5. Cost control with credits

- Judging window Aug 17–31 + soak from ~Aug 10: ~500 hrs × $0.13 ≈
  **$65 on t4g.xlarge** — well inside typical credit grants.
- **Stop** (not terminate) the instance when idle before Aug 10; with an
  Elastic IP the address — and therefore the secrets — stay valid.
  Stopped cost ≈ EBS pennies (+ small Elastic-IP idle fee).
- Terminate + release the Elastic IP after Aug 31.

## Decision status — CHOSEN AND DEPLOYED (2026-07-26)

This is the route we took, on a **personal** AWS account. ADR-0003's
self-hosted-OSS decision is unchanged — only the box vendor moved.
Actuals differ from the plan above in two ways worth recording:

- **`t4g.large` (2 vCPU / 8 GB), not `t4g.xlarge`.** 8 GB holds the full
  quickstart stack for this dataset once 4 GB swap and
  `vm.max_map_count=262144` are configured (~4.3 GB idle of 7.6 GB).
  Halves the cost to **~$1.60/day**; resize to `xlarge` is a 2-minute
  stop/modify/start and the Elastic IP makes it secret-transparent.
- **Deployed entirely via the AWS CLI**, not the console. The IAM user
  needed a scoped inline policy (EC2 launch/lifecycle + security groups +
  Elastic IP; no IAM, no billing), plus two `Deny` guardrails restricting
  instance types to `t4g`/`t3` `large`/`xlarge` and the region to
  `us-east-1` — a cheap cap against a fat-fingered GPU launch.

### What was actually hardened (verified, in this order)

The ordering matters: every step below was proven **before** the ports were
widened to `0.0.0.0/0`.

| Step | Verification |
|---|---|
| Default `datahub/datahub` login disabled — replaced via a host-mounted `user.props` with a 28-char password | old creds → `400 Invalid Credentials`; new → `200` |
| `METADATA_SERVICE_AUTH_ENABLED=true` on GMS | anonymous `POST /api/graphql` → **401** |
| Agent token (admin PAT) → `DATAHUB_GMS_TOKEN` in both repos | authenticated GraphQL returns `me.corpUser.username = datahub` |
| Separate `judge` account, **Reader** role | write mutation → *"Unauthorized to perform this action"*; lineage read → 8 results |
| SSH (22) restricted to the maintainer's IP — **never** widened | security group shows `22 → <ip>/32` only |
| Only then: 8080 + 9002 → `0.0.0.0/0` | judges + GitHub runners (whose IPs are dynamic) can reach it |

Gotchas hit, for anyone repeating this:

1. **`user.props` is baked into the frontend image**, not host-mounted — the
   UI's "Reset User Password" dialog targets *native* users and won't change
   the default admin. Bind-mount a replacement instead.
2. That mounted file must be readable by the container's user — it runs as
   **uid 100**, so a `chmod 600` file owned by `ubuntu` (uid 1000) yields
   `Login Failure: all modules ignored`. `chown 100:101` + `chmod 640`.
3. Driving `docker compose` directly (needed to add the env var and the
   mount) requires the vars the CLI normally injects — write a `.env` next
   to the generated compose containing the **existing**
   `DATAHUB_TOKEN_SERVICE_SALT`/`SIGNING_KEY` (from `.local-secrets.env`,
   or previously-issued tokens break) plus `DATAHUB_VERSION`.
4. A JAAS user created via `user.props` logs in fine but exists as a
   **key-only** corpuser — GMS then can't hydrate the actor and rejects its
   tokens with 401 (`Could not find entity for urn:li:corpuser:judge`).
   Emit a `corpUserInfo` aspect for it before minting tokens.

### Operating it

- **Stop when idle** (pre-judging): `aws ec2 stop-instances --instance-ids <id>`
  → billing drops to EBS only (~$0.11/day); the Elastic IP keeps the URL.
- **Teardown after Aug 31:** terminate the instance **and release the
  Elastic IP** — an unattached EIP bills ~$3.60/mo. Then delete the
  `dig-ec2-deploy` inline policy to return the IAM user to Bedrock-only.
- Instance id, IP, credentials, and both teardown commands live in the
  maintainer's `~/dig-datahub-credentials.txt` (never committed).
