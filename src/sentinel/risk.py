"""
risk.py — the deterministic risk-tier taxonomy.

This is layer 1 of Sentinel's defense-in-depth: a *hardcoded* classification of
what an action can DO, independent of any model's opinion about whether it's
safe. Carried over from the Marionette trace schema.

Design rationale:
    The blast radius of an action is a property of the action itself, not of the
    text that requested it. "Send money" is irreversible whether or not the
    request looks benign. We classify on capability so that the enforcement
    floor can never be argued out of by a clever prompt — there is no LLM in
    this module on purpose.
"""

from __future__ import annotations

from enum import IntEnum


class RiskTier(IntEnum):
    """Capability-based risk tiers, ordered by blast radius (low -> high).

    IntEnum so tiers compare numerically: a higher value == higher stakes.
    The ordering is load-bearing for the policy engine, which gates the
    expensive LLM reasoner and the human-in-the-loop path on tier >= a
    threshold.
    """

    READ_ONLY = 0          # fetch/list/read. Reversible by definition (no state change).
    REVERSIBLE_WRITE = 1   # writes that can be undone (draft a note, set a flag).
    IRREVERSIBLE_WRITE = 2 # state changes that cannot be cleanly undone (delete, pay).
    EXTERNAL_COMM = 3       # anything that leaves the trust boundary (send email, POST).


# A tool declares its tier once, at registration. We keep the mapping explicit
# and data-driven rather than inferring it at call time: the security posture of
# a tool should be a reviewable, version-controlled fact, not a runtime guess.
DEFAULT_TIERS: dict[str, RiskTier] = {
    "read_email": RiskTier.READ_ONLY,
    "list_contacts": RiskTier.READ_ONLY,
    "draft_note": RiskTier.REVERSIBLE_WRITE,
    "send_money": RiskTier.IRREVERSIBLE_WRITE,
    "send_email": RiskTier.EXTERNAL_COMM,
    # Hestia care tools:
    "read_documents": RiskTier.READ_ONLY,        # scan the drop-zone
    "export_calendar": RiskTier.READ_ONLY,        # generate an .ics file
    "create_reminder": RiskTier.REVERSIBLE_WRITE, # schedule a reminder (undoable)
    "pay_bill": RiskTier.IRREVERSIBLE_WRITE,      # money leaves the account
}

# The tier at or above which an action is "high-stakes": we refuse to let a
# permissive verdict pass on autopilot. This is the single most important
# tunable in the whole system, so it lives here as a named constant.
HIGH_STAKES_TIER: RiskTier = RiskTier.IRREVERSIBLE_WRITE


def tier_for(tool_name: str, registry: dict[str, RiskTier] | None = None) -> RiskTier:
    """Look up a tool's tier. Unknown tools fail closed to the highest tier.

    An unregistered tool is an unknown quantity; treating it as EXTERNAL_COMM
    means a tool nobody reviewed gets the strictest handling by default rather
    than slipping through as harmless.
    """
    reg = registry if registry is not None else DEFAULT_TIERS
    return reg.get(tool_name, RiskTier.EXTERNAL_COMM)
