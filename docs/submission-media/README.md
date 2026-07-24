# Submission media

Judge-facing images and diagrams for **Downstream Impact Guardian** (Build with
DataHub · The Agent Hackathon). Everything here is a real, checked-in artifact —
no mockups presented as live.

## Links

- **Repo:** https://github.com/jwlai-cloud/downstream-impact-guardian
- **Live demo (one-screen):** https://downstream-impact-guardian.vercel.app/
- **Judge workbench (zero-credential):** https://jwlai-cloud.github.io/downstream-impact-guardian/
- **Interactive engineering walkthrough:** https://claude.ai/code/artifact/c578039e-bce6-4330-8396-cb48b739e7c6
- **Demo video:** `captures/video/dig-demo-v6.mp4` (~2:57)
- **Diagrams:** [`DIAGRAMS.md`](DIAGRAMS.md) — architecture · agent topology · sequence

## Screenshots

| File | What it shows |
|---|---|
| `pr1-comment-header-hl.png` | The verdict — CRITICAL (score 24), the agent's PR comment header |
| `pr1-blast-radius-hl.png` | Blast radius table — impact level + stakeholders (advisory, never blocking) |
| `pr1-queries-hl.png` | Observed production queries still hitting the renamed column = certain breakage |
| `pr1-compat.png` | The generated fix — a mergeable compatibility view + schema tests |
| `dh-properties-hl.png` | A consumer's `depends_on_columns` declaration, live in DataHub properties |
| `dh-contract.png` | The PROPOSED Data Contract written back into DataHub |
| `dh-lineage-downstream.png` | DataHub lineage — the cross-system view no repo can see |
| `pr5-qwen-narrative-hl.png` | Real LLM narrative, attributed (Qwen via ADK + Agent Context Kit) |
| `joblog-b3.png` | The live Action run log — `mode=live`, CRITICAL 24, contracts upserted, comment posted |
| `slack-real.png` | The real Slack alert posted on a HIGH/CRITICAL run (proof of the opt-in integration) |
| `slide-arch.png` | Architecture at a glance (hypothesis vs reality) |
| `slide-ladder.png` | The precision ladder — declared / derived / worst-case |

_Screenshots are exported from the demo capture rig; the Slack image is the actual
message the Action posted (webhook-gated, HIGH/CRITICAL only)._
