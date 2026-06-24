"""
demo/attack_demo.py - the elder-care indirect-injection scenario, end to end.

Runs the full security core (no cloud, no API keys) and prints the decision feed.

Storyline (the hardened version):
  1. The agent reads the inbox (READ_ONLY -> allowed). The poisoned email is a
     REALISTIC fake invoice with no scam tells, so the detector does NOT flag it
     and the session is NOT tainted. Detection is blind here, on purpose.
  2. The agent, finding a plausible invoice, attempts to pay it: send_money.
  3. send_money is IRREVERSIBLE, so Sentinel HOLDS it for human approval even
     though nothing was detected as malicious. The money does not move. A human
     would see "send 4000 EUR to an unrecognized account?" and decline.

The point: the defense does not depend on catching the attack. It depends on
never wiring money on autopilot.

Run:  python -m demo.attack_demo
"""

from __future__ import annotations

from sentinel.detectors.heuristic import HeuristicDetector
from sentinel.policy import PolicyEngine
from sentinel.session import GatewaySession
from sentinel.risk import tier_for
from sentinel.trace import TraceEvent, TraceLog
from sentinel.verdict import Decision

from sentinel.mock_tools import read_email, send_money

_MARK = {Decision.ALLOW: "ALLOW", Decision.FLAG: "HELD ", Decision.BLOCK: "BLOCK"}


def run() -> None:
    session = GatewaySession(PolicyEngine(detectors=[HeuristicDetector()]))
    trace = TraceLog("demo_trace.jsonl")
    trace.path.unlink(missing_ok=True)

    def log(tool_name, phase, verdict, args):
        trace.record(TraceEvent(
            tool_name=tool_name, tier=tier_for(tool_name), phase=phase,
            decision=verdict.decision, source=verdict.source,
            reason=verdict.reason, arguments=args,
        ))
        print(f"  [{_MARK[verdict.decision]}] {tool_name} ({phase})  <- {verdict.reason}")

    print("Step 1: agent reads the inbox")
    v = session.inspect_call("read_email", {})
    log("read_email", "pre_call", v, {})
    inbox = read_email() if v.decision == Decision.ALLOW else ""

    v = session.observe_result("read_email", inbox)
    log("read_email", "post_result", v, {})
    print(f"  -> detector flagged the content: {session.tainted} "
          f"(the invoice looks legitimate, so no)")

    print("\nStep 2: the plausible invoice leads the agent to attempt payment")
    args = {"amount_eur": 4000.0, "iban": "DE00 1234 5678 9012 3456 00"}
    v = session.inspect_call("send_money", args)
    log("send_money", "pre_call", v, args)
    result = send_money(**args) if v.decision == Decision.ALLOW else None

    print("\nOutcome:")
    if result is None:
        print("  Money did NOT move. Sentinel held the transfer for human approval")
        print("  purely because it is irreversible — no detection was needed.")
    else:
        print(f"  {result}  <- SECURITY FAILURE: the transfer went through.")

    print(f"\nTrace written to {trace.path} ({len(trace.events())} events).")


if __name__ == "__main__":
    run()
