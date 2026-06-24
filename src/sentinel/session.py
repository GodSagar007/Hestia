"""
session.py — the stateful wrapper that turns per-call verdicts into a coherent
defense across a read->act chain.

PolicyEngine is intentionally pure (one call in, one verdict out). But indirect
injection is a *cross-call* attack: the poison enters on one call and detonates
on a later one. Something has to remember "this session touched bad data." That
state lives here, isolated from the pure decision logic, so the engine stays
easy to reason about and test.

A session is the unit of trust: in the real proxy, one agent conversation == one
GatewaySession. Taint is sticky for the session's lifetime — once an agent has
read a malicious instruction, we treat the rest of that session as operating
under possible influence until a human clears it.
"""

from __future__ import annotations

from .policy import PolicyEngine
from .verdict import Decision, Verdict


class GatewaySession:
    def __init__(self, engine: PolicyEngine) -> None:
        self.engine = engine
        self.tainted = False
        self.taint_reason = ""

    def inspect_call(self, tool_name: str, arguments: dict) -> Verdict:
        """Pre-call check: verdict for an outgoing tool call, given current taint."""
        return self.engine.evaluate(
            tool_name, arguments, session_tainted=self.tainted
        )

    def observe_result(self, tool_name: str, result: str) -> Verdict:
        """Post-call check on UNTRUSTED returned content.

        If a detector flags the returned content, the session becomes tainted —
        this is the propagation step that links the poisoned read to the later
        blocked action. Taint only ever turns ON here; clearing it requires an
        explicit human action (see clear_taint), never a model's say-so.
        """
        verdict = self.engine.evaluate(tool_name, {}, tool_result=result)
        if verdict.decision >= Decision.FLAG:
            self.tainted = True
            self.taint_reason = verdict.reason
        return verdict

    def clear_taint(self, approver: str) -> None:
        """Human-in-the-loop reset. Only a person can vouch that the session is
        clean again — the system will not self-clear on a model's assurance."""
        self.tainted = False
        self.taint_reason = f"cleared by {approver}"
