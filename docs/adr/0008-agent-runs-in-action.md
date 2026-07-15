# ADR-0008: Agent executes inside the Action runner, not Cloud Run

Status: Accepted (2026-07-15) · narrows CLAUDE.md's "hosted on Cloud Run"

## Context

CLAUDE.md said "Google ADK on GCP, hosted on Cloud Run," but the settled
trigger is a GitHub Action running `python agent/main.py`. A Cloud Run
service behind the Action would add a network hop, auth surface, deploy
pipeline, and cold starts — for a check that runs for seconds, once per PR
push.

## Decision

The agent is a CLI executed in the Action runner. ADK is used as a library
(`agent/adk_agent.py`) for the live-mode narrative agent, not as a hosted
service. Cloud Run remains the right home for the stretch-goal web UI only.

## Consequences

Zero hosting cost and one less credential for the core loop. If the stretch
UI lands, it calls the same `agent/` package from its own Cloud Run
service — nothing here blocks that.
