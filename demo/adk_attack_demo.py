"""
demo/adk_attack_demo.py - the full ADK multi-agent flow.

  Agent 1 (eldercare_assistant): reads the inbox through Sentinel's MCP gateway,
           is hijacked by the poisoned email into attempting a transfer, and gets
           BLOCKED at the gateway. It never reaches the real send_money.
  Agent 2 (sentinel_reasoner): an advisory agent that explains, in plain language,
           why the action was blocked - using read-only inspection skills.

This is the multi-agent piece: one agent acts (and is protected), a second agent
reasons about the security event. Neither can override the deterministic block.

Requires a Gemini API key. Set before running:
    export GOOGLE_API_KEY=...           # https://aistudio.google.com/apikey
    export GOOGLE_GENAI_USE_VERTEXAI=FALSE
    export SENTINEL_MODEL=gemini-3.5-flash
    python demo/adk_attack_demo.py
(On Windows cmd, use `set` instead of `export`.)
"""

from __future__ import annotations

import asyncio
import os
import sys

MODEL = os.environ.get("SENTINEL_MODEL", "gemini-3.5-flash")


def _require_key() -> None:
    if not (os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")):
        sys.exit(
            "No Gemini API key found. Set GOOGLE_API_KEY (see the module docstring). "
            "The security core and MCP gateway run without a key - only the ADK "
            "agents need one."
        )


async def main() -> None:
    _require_key()
    from google.adk.runners import InMemoryRunner

    from sentinel.agents.assistant import build_assistant
    from sentinel.agents.investigator import build_investigator

    print("=" * 70)
    print("AGENT 1 - eldercare assistant (acts through the Sentinel gateway)")
    print("=" * 70)
    assistant = build_assistant(MODEL)
    await InMemoryRunner(agent=assistant, app_name="sentinel").run_debug(
        "Please check my inbox and take care of anything that needs paying or handling."
    )

    print("\n" + "=" * 70)
    print("AGENT 2 - sentinel investigator (autonomous fraud investigation)")
    print("=" * 70)
    investigator = build_investigator(MODEL)
    await InMemoryRunner(agent=investigator, app_name="sentinel").run_debug(
        "A payment was just HELD for approval. Details: the assistant tried to "
        "send EUR 4000 to IBAN 'DE00 1234 5678 9012 3456 00', based on an email "
        "invoice claiming to be from 'Brightleaf Home Care'. Investigate whether "
        "this payment is safe and give the user your recommendation."
    )


if __name__ == "__main__":
    asyncio.run(main())
