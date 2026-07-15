# tools/demo_ui/ — STRETCH GOAL, not part of the core loop

This is the tested (against a mock GitHub API) client for the "judge clicks
a button, a real branch+PR is created, live progress is narrated" web UI
discussed in docs/SPEC.md section 8.

**Do not build the frontend for this until the core loop
(.github/workflows/downstream-impact-guardian-check.yml + agent/) is fully working.** This
code was built ahead of schedule deliberately, so it's ready to wire up if
time remains — it is not a blocker or a dependency for a working submission.
The pre-made `demo/*` branch approach (fork this repo, open a PR from that
branch, watch the real Action fire) already satisfies the judges' testing
requirement without this UI.

## What's here and already verified working

- `github_demo_client.py` — `GitHubDemoRunner`: creates a branch, pushes a
  file change, opens a PR, polls check-run status, detects the bot's PR
  comment, and cleans up (closes PR + deletes branch) afterward. Point
  `base_url` at `https://api.github.com` with a real token to go live —
  the interface doesn't change.
- `mock_github_server.py` — an in-memory Flask mock of just enough of the
  real GitHub REST API to exercise the above end-to-end without real
  credentials or a real repo.
- `test_demo_flow.py` — full happy-path run against the mock.
- `test_cleanup_and_errors.py` — cleanup verification + two real bugs this
  caught during design (a timeout path that silently reported false
  success, and an under-strict mock auth check) — see docs/SPEC.md
  section 8 for what those were.

Run both test files directly (`python3 tools/demo_ui/test_demo_flow.py`)
to confirm they still pass before extending this.

## Not yet built / not yet tested (see docs/SPEC.md section 8)

- The actual frontend (trigger button, live status view)
- Rate limiting / one-run-at-a-time guard for a public button
- Scheduled cleanup sweep for abandoned demo branches
- Real GitHub Actions timing (mock simulates a 4s delay; tune
  `poll_timeout`/`poll_interval` against real dbt+agent runtime)
- Real auth scopes for a token Cloud Run would hold (fine-grained PAT or
  GitHub App, not a broad classic PAT)
