"""
agents/skills.py — read-only inspection skills for the Sentinel reasoner agent.

These plain functions become ADK tools (FunctionTool) — "agent skills" in the
course's vocabulary. Every one of them is READ-ONLY: it inspects and reports.
None of them can execute, approve, or release an action. This is the structural
expression of "the guard has no hands" at the skill level — even a fully
jailbroken reasoner can only call functions that look, never functions that act.
"""

from __future__ import annotations

from ..detectors.base import InspectionContext
from ..detectors.heuristic import HeuristicDetector
from ..risk import RiskTier, tier_for

_detector = HeuristicDetector()


def classify_injection(text: str) -> dict:
    """Run the injection detector over a piece of text and report the finding.

    Use this to analyze suspicious content (e.g. the body of an email the agent
    read). Returns the detector's decision and reason. Read-only.
    """
    verdict = _detector.inspect(
        InspectionContext(
            tool_name="(adhoc)", tier=RiskTier.READ_ONLY, arguments={}, tool_result=text
        )
    )
    return {
        "decision": verdict.decision.name,
        "reason": verdict.reason,
        "confidence": verdict.confidence,
    }


def risk_tier_of(tool_name: str) -> str:
    """Look up the deterministic risk tier of a named tool. Read-only."""
    return tier_for(tool_name).name


def explain_policy() -> str:
    """Return Sentinel's enforcement policy in plain language. Read-only."""
    return (
        "Sentinel composes three layers, most-restrictive-wins: (1) a hardcoded "
        "risk-tier gate, (2) a learned injection detector, (3) this advisory "
        "reasoner. Suspicion on an irreversible or external action — or any "
        "action taken in a session already tainted by injected content — is "
        "escalated to BLOCK or a human-approval pause. No layer can downgrade "
        "another layer's restriction."
    )
