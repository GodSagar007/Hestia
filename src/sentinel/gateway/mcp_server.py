"""
gateway/mcp_server.py — Sentinel as a real MCP server (the gateway).

This is the piece that makes Sentinel a *security layer any agent can sit behind*
rather than checks bolted onto one agent. A downstream agent connects to this
MCP server and calls its tools; Sentinel enforces policy on every call before
(optionally) forwarding to the real upstream tool.

The flow for each call is the whole architecture in miniature:
    inspect (pre-call)  ->  BLOCK | run upstream  ->  observe result (taint)

Upstream tools are local callables here so the gateway runs standalone with no
cloud. In production the `upstream_*` calls become requests to a real upstream
MCP server via an MCP client (mcp.client) — Sentinel becomes a true
man-in-the-middle proxy. The enforcement logic above doesn't change.

Run as an MCP server over stdio:
    PYTHONPATH=src:. python -m sentinel.gateway.mcp_server
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from sentinel.detectors.heuristic import HeuristicDetector
from sentinel.policy import PolicyEngine
from sentinel.risk import tier_for
from sentinel.session import GatewaySession
from sentinel.trace import TraceEvent, TraceLog
from sentinel.verdict import Decision

# Upstream tools. Swap these two imports for MCP-client calls to a real upstream
# server and Sentinel becomes a transparent proxy — nothing else changes.
from sentinel.mock_tools import read_email as upstream_read_email
from sentinel.mock_tools import send_money as upstream_send_money

mcp = FastMCP("sentinel-gateway")

# One GatewaySession per server process. A stdio server serves one client
# connection, so process scope == session scope here. In a multi-client HTTP
# deployment you'd key a GatewaySession by MCP connection/context; taint must
# never leak between unrelated agents. Flagged for the deployment milestone.
_session = GatewaySession(PolicyEngine(detectors=[HeuristicDetector()]))
_trace = TraceLog("gateway_trace.jsonl")


def _guard(tool_name: str, arguments: dict, run_upstream):
    """Enforce policy around one upstream call."""
    verdict = _session.inspect_call(tool_name, arguments)
    _trace.record(TraceEvent(
        tool_name=tool_name, tier=tier_for(tool_name), phase="pre_call",
        decision=verdict.decision, source=verdict.source,
        reason=verdict.reason, arguments=arguments,
    ))
    if verdict.decision == Decision.BLOCK:
        # Return a clean refusal, not an exception: the agent learns its action
        # was denied and why, while the dangerous call never executes.
        return f"[SENTINEL BLOCKED] {tool_name}: {verdict.reason}"
    if verdict.decision == Decision.FLAG:
        # Held pending human approval. In autonomous operation there is no human
        # to approve in-band, so the action does NOT execute. A real deployment
        # surfaces an approval prompt to the user here ("send 4000 EUR to an
        # unrecognized account?"). The action runs only on an explicit yes.
        return (
            f"[SENTINEL HELD FOR APPROVAL] {tool_name}: {verdict.reason}. "
            f"Not executed — awaiting human approval."
        )

    result = run_upstream()

    # Inspect untrusted returned content and taint the session if it's suspicious.
    post = _session.observe_result(tool_name, str(result))
    _trace.record(TraceEvent(
        tool_name=tool_name, tier=tier_for(tool_name), phase="post_result",
        decision=post.decision, source=post.source, reason=post.reason,
        arguments={},
    ))
    return result


@mcp.tool(description="Read the user's inbox. Read-only; returns untrusted content.")
def read_email() -> str:
    return _guard("read_email", {}, upstream_read_email)


@mcp.tool(description="Transfer money to an IBAN. Irreversible; high-stakes.")
def send_money(amount_eur: float, iban: str) -> str:
    return _guard(
        "send_money",
        {"amount_eur": amount_eur, "iban": iban},
        lambda: upstream_send_money(amount_eur, iban),
    )


if __name__ == "__main__":
    mcp.run()
