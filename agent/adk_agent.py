"""Live-mode narrative: a Google ADK LlmAgent that gets the detected facts
plus read-only DataHub tools, verifies the blast radius itself, and writes
the impact narrative. Deterministic scoring/codegen never depends on this —
if ADK/Gemini is unavailable the pipeline keeps the deterministic narrative
(ADR-0007)."""
from __future__ import annotations

import asyncio
import json

from agent.models import ImpactReport

INSTRUCTION = """\
You are the Downstream Impact Guardian reviewing a dbt pull request.
You receive detected facts as JSON: model changes (schema/logic), glossary
drift, downstream consumers and observed queries from DataHub.

Use the tools to double-check anything you doubt (lineage, queries, glossary
definitions). Then reply with ONLY:
1. An impact narrative of at most 150 words, written for the PR author,
   concrete about who breaks and why.
2. A line 'ACTIONS:' followed by the top 3 recommended actions as bullets.
Do not restate the raw data; interpret it."""


def build_tools(reader):
    def get_downstream_consumers(model_name: str) -> list[dict]:
        """List downstream consumers of a dbt model from DataHub lineage."""
        return [vars(c) for c in reader.get_downstream(model_name)]

    def get_observed_queries(model_name: str) -> list[dict]:
        """List recent real-world queries DataHub observed on a model."""
        return [vars(q) for q in reader.get_queries(model_name)]

    def get_glossary_definition(term_name: str) -> dict:
        """Get the current live business definition of a glossary term."""
        return reader.get_glossary_term(term_name) or {}

    return [get_downstream_consumers, get_observed_queries,
            get_glossary_definition]


async def _run(report: ImpactReport, reader) -> str:
    from google.adk.agents import Agent
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.genai import types

    agent = Agent(
        name="downstream_impact_guardian",
        model="gemini-flash-latest",
        instruction=INSTRUCTION,
        tools=build_tools(reader),
    )
    session_service = InMemorySessionService()
    await session_service.create_session(app_name="dig", user_id="ci",
                                         session_id="pr")
    runner = Runner(agent=agent, app_name="dig",
                    session_service=session_service)

    facts = {
        "model_changes": [{
            "model": c.model_name, "kinds": sorted(c.kinds),
            "renames": c.renames,
            "columns": [vars(col) for col in c.columns],
            "breaking": c.breaking,
        } for c in report.model_changes],
        "glossary_drift": [vars(g) for g in report.glossary_changes],
        "consumers": {m: [vars(c) for c in cs]
                      for m, cs in report.consumers.items()},
        "severity": report.severity,
    }
    final = ""
    async for event in runner.run_async(
        user_id="ci", session_id="pr",
        new_message=types.Content(
            role="user",
            parts=[types.Part.from_text(text=json.dumps(facts))]),
    ):
        if event.is_final_response() and event.content and event.content.parts:
            final = event.content.parts[0].text or ""
    return final.strip()


def enrich_narrative(report: ImpactReport, reader, api_key: str) -> None:
    """Best-effort: replace the deterministic narrative with an ADK/Gemini
    one. Any failure leaves the report untouched."""
    if not api_key:
        return
    try:
        import os
        os.environ.setdefault("GOOGLE_API_KEY", api_key)
        text = asyncio.run(_run(report, reader))
        if text:
            report.narrative = text
            report.narrative_source = "gemini-adk"
    except Exception as exc:
        print(f"[guardian] ADK narrative skipped: {exc}")
