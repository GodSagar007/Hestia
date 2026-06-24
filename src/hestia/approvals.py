"""
hestia/approvals.py — the caregiver approval loop.

When Sentinel holds an irreversible action, it doesn't vanish and it doesn't run.
It becomes a PendingApproval: a record the caregiver sees, with the advocate's
evidence attached, and a one-tap approve/deny. Approve runs the real action;
deny discards it. This is where Sentinel's "hold" becomes a product feature.

The queue executes the held action itself on approval — the agent never gets a
second chance to run it. Authority to actually perform an irreversible action
lives here, gated behind an explicit human yes.
"""

from __future__ import annotations

import itertools
from typing import Callable

from pydantic import BaseModel, Field


class PendingApproval(BaseModel):
    id: int
    tool: str
    summary: str                 # human-readable: "Pay 4000 EUR to DE00…"
    reason: str                  # why Sentinel held it
    evidence: list[str] = Field(default_factory=list)  # advocate findings
    status: str = "pending"      # pending | approved | denied
    result: str | None = None
    bill_id: int | None = None   # the ledger bill this would pay, if any


class ApprovalQueue:
    def __init__(self) -> None:
        self._ids = itertools.count(1)
        self._items: dict[int, PendingApproval] = {}
        self._actions: dict[int, Callable[[], str]] = {}

    def hold(
        self,
        tool: str,
        summary: str,
        reason: str,
        action: Callable[[], str],
        evidence: list[str] | None = None,
        bill_id: int | None = None,
    ) -> PendingApproval:
        """Record a held action and the thunk that performs it if approved."""
        pid = next(self._ids)
        pa = PendingApproval(
            id=pid, tool=tool, summary=summary, reason=reason,
            evidence=evidence or [], bill_id=bill_id,
        )
        self._items[pid] = pa
        self._actions[pid] = action
        return pa

    def pending(self) -> list[PendingApproval]:
        return [p for p in self._items.values() if p.status == "pending"]

    def approve(self, pid: int) -> PendingApproval:
        pa = self._items[pid]
        if pa.status != "pending":
            return pa
        pa.result = self._actions[pid]()   # execute the real action now
        pa.status = "approved"
        return pa

    def deny(self, pid: int) -> PendingApproval:
        pa = self._items[pid]
        if pa.status == "pending":
            pa.status = "denied"
        return pa
