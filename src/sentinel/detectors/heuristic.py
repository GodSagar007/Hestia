"""
detectors/heuristic.py — a dependency-free stand-in for the DeBERTa classifier.

Purpose: let the whole pipeline run and the demo pass TODAY, before the trained
model is wired in. It implements the same Detector protocol the real classifier
will, so swapping it is a one-line change in the policy wiring.

This is intentionally crude — a few high-signal patterns for known indirect-
injection phrasing. The real layer 2 (DeBERTa fine-tuned on injection corpora)
generalizes far beyond these strings; that's the whole reason it's a learned
model and not a regex. Comments mark exactly where it plugs in.
"""

from __future__ import annotations

import re

from .base import Detector, InspectionContext
from ..verdict import Decision, Verdict

# Phrases that frequently mark an injected instruction embedded in retrieved
# content. Deliberately small: heuristics are the placeholder, not the product.
_INJECTION_MARKERS = [
    r"ignore (all |the |your )?(previous|prior|above) instructions",
    r"disregard .{0,20}(instructions|rules|policy)",
    r"you are now",
    r"new instructions:",
    r"system override",
    r"do not tell (the user|anyone)",
    r"transfer .{0,30}(immediately|now|urgent)",
]
_PATTERN = re.compile("|".join(_INJECTION_MARKERS), re.IGNORECASE)


class HeuristicDetector:
    """A regex stand-in for the learned injection classifier."""

    name = "heuristic_injection_detector"

    def inspect(self, ctx: InspectionContext) -> Verdict:
        # Inspect both the outgoing arguments and any untrusted returned content.
        # The returned content is where indirect injection lives.
        haystacks = [str(ctx.arguments)]
        if ctx.tool_result:
            haystacks.append(ctx.tool_result)

        for text in haystacks:
            if _PATTERN.search(text):
                # We FLAG, not BLOCK. The detector's job is to raise suspicion;
                # whether suspicion becomes a hard stop depends on the action's
                # risk tier, and that decision lives in the policy engine, not
                # here. A detector that could unilaterally BLOCK or ALLOW would
                # be a single point of failure — exactly what we're avoiding.
                return Verdict(
                    decision=Decision.FLAG,
                    source=self.name,
                    reason="possible injected instruction in untrusted content",
                    confidence=0.6,
                )

        return Verdict(
            decision=Decision.ALLOW,
            source=self.name,
            reason="no injection markers found",
            confidence=0.55,
        )


# Static type check: HeuristicDetector satisfies the Detector protocol.
_: Detector = HeuristicDetector()
