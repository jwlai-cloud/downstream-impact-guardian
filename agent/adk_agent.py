"""Live-mode narrative: a Google ADK LlmAgent that gets the detected facts
plus read-only DataHub tools, verifies the blast radius itself, and writes
the impact narrative. Deterministic scoring/codegen never depends on this —
if ADK/Gemini is unavailable the pipeline keeps the deterministic narrative
(ADR-0007)."""
from __future__ import annotations

import asyncio
import json

from agent.models import ImpactReport

DEFAULT_MODEL = "gemini-flash-latest"


def resolve_model(name: str | None):
    """ADK model argument for the narrative agent. Gemini names pass
    through as strings (ADK-native). Anything else — 'openai/gpt-4o-mini',
    'openai/qwen-max' with OPENAI_API_BASE pointing at an
    OpenAI-compatible endpoint — is wrapped in ADK's LiteLLM adapter."""
    name = (name or DEFAULT_MODEL).strip()
    if name.startswith("gemini"):
        return name
    from google.adk.models.lite_llm import LiteLlm
    return LiteLlm(model=name)


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
    """DataHub read tools for the narrative agent. Primary path: the
    first-party Agent Context Kit (Track 1's named integration). Local
    wrappers fill in what the Kit doesn't cover (observed query usage) and
    stand in entirely if the Kit can't initialize."""
    def get_observed_queries(model_name: str) -> list[dict]:
        """List recent real-world queries DataHub observed on a model."""
        return [vars(q) for q in reader.get_queries(model_name)]

    try:
        from datahub.sdk.main_client import DataHubClient
        from datahub_agent_context.google_adk_tools import \
            build_google_adk_tools

        client = DataHubClient.from_env()
        # read-only on purpose: writebacks are deterministic pipeline steps,
        # never LLM tool calls (ADR-0002). The Kit covers lineage, queries,
        # assertions, schema fields, and search — the full read surface.
        tools = build_google_adk_tools(client, include_mutations=False)
        print("[guardian] narrative tools: DataHub Agent Context Kit")
        return tools
    except Exception as exc:
        print(f"[guardian] Agent Context Kit unavailable ({exc}); "
              "using local read tools")

        def get_downstream_consumers(model_name: str) -> list[dict]:
            """List downstream consumers of a dbt model from DataHub lineage."""
            return [vars(c) for c in reader.get_downstream(model_name)]

        def get_glossary_definition(term_name: str) -> dict:
            """Get the current live business definition of a glossary term."""
            return reader.get_glossary_term(term_name) or {}

        return [get_downstream_consumers, get_glossary_definition,
                get_observed_queries]


async def _run(report: ImpactReport, reader) -> str:
    from google.adk.agents import Agent
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.genai import types

    import os
    agent = Agent(
        name="downstream_impact_guardian",
        model=resolve_model(os.environ.get("GUARDIAN_NARRATIVE_MODEL")),
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


def validate_narrative_config(google_api_key: str) -> str | None:
    """A configured model with no key for its provider is a plumbing
    error, not a fallback case — fail loudly with the fix (the silent
    template fallback is reserved for 'no LLM configured at all')."""
    import os
    model = (os.environ.get("GUARDIAN_NARRATIVE_MODEL") or "").strip()
    if not model:
        return None
    if model.startswith("gemini"):
        if not google_api_key:
            return (f"narrative-model '{model}' is configured but no Google "
                    "key is set. Add GOOGLE_API_KEY as a GitHub Actions "
                    "secret (repo Settings → Secrets and variables → "
                    "Actions) and pass it via the action's google-api-key "
                    "input — or unset GUARDIAN_NARRATIVE_MODEL.")
        return None
    if not os.environ.get("OPENAI_API_KEY"):
        return (f"narrative-model '{model}' is configured but OPENAI_API_KEY "
                "is empty. Add it as a GitHub Actions secret (repo Settings "
                "→ Secrets and variables → Actions) and pass it via the "
                "action's openai-api-key input (plus openai-base-url for "
                "OpenAI-compatible providers) — or unset "
                "GUARDIAN_NARRATIVE_MODEL.")
    return None


def enrich_narrative(report: ImpactReport, reader, api_key: str) -> None:
    """Best-effort: replace the template narrative with an LLM-written one
    (Gemini by default; any LiteLLM-supported provider via
    GUARDIAN_NARRATIVE_MODEL + that provider's env vars). A runtime
    failure (provider outage, rejected key) keeps the labeled template —
    but is surfaced as an Actions error annotation, never swallowed."""
    import os
    if not api_key and not os.environ.get("OPENAI_API_KEY"):
        return
    model = (os.environ.get("GUARDIAN_NARRATIVE_MODEL") or DEFAULT_MODEL).strip()
    try:
        if api_key:
            os.environ.setdefault("GOOGLE_API_KEY", api_key)
        # Bounded: a hung model call must not stall the Action job
        text = asyncio.run(asyncio.wait_for(_run(report, reader), timeout=120))
        if text:
            report.narrative = text
            report.narrative_source = model
    except Exception as exc:
        print(f"::error title=Guardian narrative LLM failed::{model}: "
              f"{type(exc).__name__} — check the provider key secret and "
              "base URL; report falls back to the labeled template narrative.")
        print(f"[guardian] ADK narrative skipped: {exc}")
