"""
verdict.py — decisions and the monotonic composition that makes Sentinel safe.

This module encodes the core security property of the whole project:

    Every layer can only ADD restriction. No layer can remove it.

That single rule is what defeats the "jailbreak the judge" attack. Even if the
LLM reasoner is talked into emitting ALLOW, composing it with the other layers
can never *downgrade* a BLOCK that the deterministic gate or the detector
raised. The fooled component has no hand on the lever.
"""

from __future__ import annotations

from enum import IntEnum

from pydantic import BaseModel, Field


class Decision(IntEnum):
    """Possible outcomes, ordered by restrictiveness (permissive -> strict).

    Ordering is the whole point: `max(decisions)` is "most restrictive wins".
    ALLOW < FLAG < BLOCK, so combining verdicts is just a max().
    """

    ALLOW = 0  # let the tool call through.
    FLAG = 1   # pause and require a human to approve (human-in-the-loop).
    BLOCK = 2  # refuse outright.


class Verdict(BaseModel):
    """One layer's opinion about one tool call.

    `decision` is the verdict; `reason` and `source` exist so the trace and the
    human-approval UI can explain *why* — an unexplained block is almost as
    useless as no block.
    """

    decision: Decision
    source: str = Field(description="which layer produced this verdict")
    reason: str = Field(default="")
    # Confidence is advisory only. It informs triage/explanation; it is never
    # allowed to relax enforcement (see compose()).
    confidence: float | None = None


def compose(verdicts: list[Verdict]) -> Verdict:
    """Combine layer verdicts into a final decision: most-restrictive-wins.

    This is monotonic by construction. We take the max Decision across all
    layers. The returned Verdict carries the reason from the layer that set the
    bar, so the audit trail points at the actual cause.

    An empty list fails closed to BLOCK: if no layer rendered an opinion,
    something is wrong upstream and we do not default to letting the call run.
    """
    if not verdicts:
        return Verdict(
            decision=Decision.BLOCK,
            source="compose",
            reason="no verdicts produced; failing closed",
        )

    governing = max(verdicts, key=lambda v: v.decision)
    return Verdict(
        decision=governing.decision,
        source=governing.source,
        reason=governing.reason,
        confidence=governing.confidence,
    )
