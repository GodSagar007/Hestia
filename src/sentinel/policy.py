"""
policy.py — the policy engine. This is where the layers meet.

It implements the synthesis we settled on:

  * Layer 1 (risk gate): deterministic. Decides how much scrutiny an action
    needs based purely on its tier.
  * Layer 2/3 (detectors): the learned classifier and the LLM reasoner. They
    raise suspicion but hold no enforcement authority.
  * Composition: most-restrictive-wins (verdict.compose), and an escalation
    rule that converts "suspicion on a high-stakes action" into a hard stop.

The flexibility/rigidity dial: detectors carry the open-ended judgment (so the
system isn't rigid), but on irreversible/external actions their suspicion is
escalated to BLOCK or a human pause (so the system isn't exploitable). Low-tier
actions stay permissive — cheap to get wrong, cheap to undo.
"""

from __future__ import annotations

from .detectors.base import Detector, InspectionContext
from .risk import HIGH_STAKES_TIER, RiskTier, tier_for
from .verdict import Decision, Verdict, compose


class PolicyEngine:
    def __init__(
        self,
        detectors: list[Detector],
        tiers: dict[str, RiskTier] | None = None,
        high_stakes_tier: RiskTier = HIGH_STAKES_TIER,
    ) -> None:
        self.detectors = detectors
        self.tiers = tiers
        self.high_stakes_tier = high_stakes_tier

    def evaluate(
        self,
        tool_name: str,
        arguments: dict,
        tool_result: str | None = None,
        session_tainted: bool = False,
    ) -> Verdict:
        """Render a final verdict for one tool call.

        Called twice in the proxy's lifecycle for a read->act chain: once before
        a tool runs (arguments only) and once after a read-only tool returns
        (with tool_result set), so indirect injection in returned data is caught
        before it can drive the *next*, higher-tier call.

        `session_tainted` carries the crucial cross-call context: True once this
        session has read untrusted content that tripped a detector. The function
        itself stays pure — the caller (GatewaySession) owns the taint state and
        passes it in — so this remains trivially testable.
        """
        tier = tier_for(tool_name, self.tiers)
        ctx = InspectionContext(
            tool_name=tool_name,
            tier=tier,
            arguments=arguments,
            tool_result=tool_result,
        )

        # Collect every layer's opinion. Detectors only ever return verdicts.
        verdicts = [d.inspect(ctx) for d in self.detectors]

        # Escalation rule — the rigidity where it counts, and the part that does
        # NOT depend on detection succeeding.
        #
        # For any high-stakes (irreversible / external) action:
        #   - if a detector flagged it, or the session is already tainted by
        #     injected content read earlier  -> hard BLOCK (a known threat is
        #     driving an irreversible action), and
        #   - otherwise                       -> FLAG / hold for human approval.
        #
        # That second branch is the important one: an irreversible action is held
        # for a human EVEN WHEN nothing was detected. A stealthy injection that
        # evades every classifier still cannot move money on autopilot — it can,
        # at most, ask, and a human decides. Detection is what upgrades the pause
        # to an automatic block; it is not what makes the system safe.
        # Low-tier actions are unaffected: cheap to get wrong, cheap to undo.
        detector_flagged = any(v.decision >= Decision.FLAG for v in verdicts)
        if tier >= self.high_stakes_tier:
            if detector_flagged or session_tainted:
                cause = "suspicious content" if detector_flagged else "tainted session"
                verdicts.append(
                    Verdict(
                        decision=Decision.BLOCK,
                        source="policy_engine",
                        reason=(
                            f"{cause} on high-stakes action ({tool_name}, tier "
                            f"{tier.name}); blocked"
                        ),
                    )
                )
            else:
                verdicts.append(
                    Verdict(
                        decision=Decision.FLAG,
                        source="policy_engine",
                        reason=(
                            f"high-stakes action ({tool_name}, tier {tier.name}) "
                            f"requires human approval before it runs"
                        ),
                    )
                )

        # Most-restrictive-wins. Monotonic: nothing here can downgrade a block.
        return compose(verdicts)
