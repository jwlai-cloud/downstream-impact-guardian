# Submission media

Judge-facing images and diagrams for **Downstream Impact Guardian** (Build with
DataHub · The Agent Hackathon). Everything here is a real, checked-in artifact —
no mockups presented as live.

## Links

- **Judge guide (start here):** [`../JUDGING.md`](../JUDGING.md)
- **Repo:** https://github.com/jwlai-cloud/downstream-impact-guardian
- **Live demo (one-screen):** https://downstream-impact-guardian.vercel.app/
- **Judge workbench (zero-credential):** https://jwlai-cloud.github.io/downstream-impact-guardian/
- **Live DataHub catalog:** URL + read-only judge login are in the Devpost
  private testing-notes field (never committed here)
- **Interactive engineering walkthrough:** https://claude.ai/code/artifact/c578039e-bce6-4330-8396-cb48b739e7c6
- **Demo video:** `captures/video/dig-demo-v6.mp4` (~2:57)
- **Diagrams:** [`DIAGRAMS.md`](DIAGRAMS.md) — architecture · agent topology · sequence

## Upload order for the Devpost gallery

Devpost shows the first image as the card thumbnail, so lead with the cover.

| # | File | Why it earns the slot |
|---|---|---|
| 1 | `00-cover.png` | Thumbnail — problem + pipeline at a glance (16:9) |
| 2 | `pr1-comment-header-hl.png` | The verdict in situ: CRITICAL (24) on a real PR |
| 3 | `pr1-blast-radius-hl.png` | The differentiator — impact level **and** who to notify |
| 4 | `01-architecture.png` | Hypothesis vs reality, one frame |
| 5 | `dh-lineage-downstream.png` | Proof the blast radius comes from DataHub |
| 6 | `dh-contract.png` | The PROPOSED contract the agent wrote back |
| 7 | `02-sequence.png` | The handshake, step by step |
| 8 | `pr1-compat.png` | Generated, mergeable compatibility code |
| 9 | `slack-real.png` | The real Slack alert (proof, not a mockup) |
| 10 | `dh-properties-hl.png` | `depends_on_columns` live in the catalog |
| 11 | `03-topology.png` | Deterministic core vs the one narrating agent |
| 12 | `00-overview.png` | Full one-pager, for anyone who wants everything |

Remaining files (`joblog-b3.png`, `pr1-queries-hl.png`, `pr5-qwen-narrative-hl.png`,
`slide-arch.png`, `slide-ladder.png`) are supporting evidence — worth attaching if
the platform allows more, but the twelve above carry the story.

## Diagrams (generated, not hand-drawn)

Built with the Archify diagram generator from the typed specs in
[`specs/`](specs/), each passing its showcase validation with 0 errors and 0
warnings. The `.html` versions are **interactive** — pan, zoom, search, focus a
node, trace a relationship — and the architecture diagram's nodes carry `SRC`
badges linking to the real functions they represent.

| Diagram | Interactive | Image |
|---|---|---|
| System architecture | [`dig-architecture.html`](dig-architecture.html) | `01-architecture.png` |
| Sequence (one PR, end to end) | [`dig-sequence.html`](dig-sequence.html) | `02-sequence.png` |
| Agent topology | [`dig-topology.html`](dig-topology.html) | `03-topology.png` |

`DIAGRAMS.md` keeps the same three as inline Mermaid, for reading on GitHub.

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
