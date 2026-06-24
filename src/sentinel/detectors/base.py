"""
detectors/base.py — the pluggable detector interface.

A Detector inspects an InspectionContext and returns a Verdict. Both the learned
DeBERTa classifier (layer 2) and the LLM reasoner (layer 3) implement this same
protocol, which is what lets the policy engine treat them uniformly and compose
their verdicts.

The key contract, enforced socially here and structurally in the policy engine:
a detector RETURNS A VERDICT — it never calls a tool. Detectors have no hands.
The most a compromised detector can do is mislabel; it cannot act.
"""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel

from ..risk import RiskTier
from ..verdict import Verdict


class InspectionContext(BaseModel):
    """Everything a detector is allowed to see about one tool call.

    Note `tool_result`: indirect (tool-result) prompt injection is the modern
    attack — the poison arrives in DATA the agent reads back, not in the
    arguments it sends. So detectors get both the outgoing args and any
    returned content to inspect.
    """

    tool_name: str
    tier: RiskTier
    arguments: dict
    # Populated on the post-call inspection pass: the (untrusted) content a
    # read-only tool returned, which may carry an injected instruction.
    tool_result: str | None = None


class Detector(Protocol):
    """Structural type for all detectors. Implement `inspect`."""

    name: str

    def inspect(self, ctx: InspectionContext) -> Verdict:
        """Return this layer's Verdict for the given context."""
        ...
