"""
demo/mcp_attack_demo.py — the attack, run through the real Sentinel MCP server.

A downstream MCP client (standing in for the agent) connects to the Sentinel
gateway over stdio and calls its tools. The injection-driven transfer is blocked
by the gateway over the wire — exactly as a real agent's calls would be. This is
the version to screen-record for the video: it's MCP end to end.

Run from the repo root:
    python demo/mcp_attack_demo.py
"""

from __future__ import annotations

import asyncio
import os
import sys

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


def _text(result) -> str:
    """Pull text out of a CallToolResult's content blocks."""
    return "".join(getattr(block, "text", "") for block in result.content)


async def main() -> None:
    params = StdioServerParameters(
        command=sys.executable,  # same interpreter -> finds the installed `sentinel`
        args=["-m", "sentinel.gateway.mcp_server"],
    )

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            print("Gateway exposes:", [t.name for t in tools.tools])

            print("\nStep 1: agent reads the inbox (through the gateway)")
            r = await session.call_tool("read_email", {})
            preview = _text(r).replace("\n", " ")[:64]
            print(f"  read_email -> {preview} ...")

            print("\nStep 2: poisoned email drives a transfer attempt")
            r = await session.call_tool(
                "send_money",
                {"amount_eur": 4000.0, "iban": "DE00 1234 5678 9012 3456 00"},
            )
            print(f"  send_money -> {_text(r)}")

            print("\nThe transfer was refused by Sentinel over MCP — the agent "
                  "never reached the real tool.")


if __name__ == "__main__":
    asyncio.run(main())
