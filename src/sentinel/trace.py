"""
trace.py — structured behavioral trace of every decision Sentinel makes.

Lineage: the trace schema from Marionette. Every intercepted call becomes one
append-only JSON event. This is what turns "trust me, it's secure" into "here's
the evidence" — for the judges, for the writeup, and for a real incident review.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from pydantic import BaseModel, Field

from .risk import RiskTier
from .verdict import Decision


class TraceEvent(BaseModel):
    ts: float = Field(default_factory=time.time)
    tool_name: str
    tier: RiskTier
    phase: str  # "pre_call" or "post_result"
    decision: Decision
    source: str  # which layer governed the final verdict
    reason: str
    arguments: dict


class TraceLog:
    """Append-only JSONL writer. One line per event, flushed immediately so a
    crash mid-incident still leaves a complete record up to the last decision."""

    def __init__(self, path: str | Path = "sentinel_trace.jsonl") -> None:
        self.path = Path(path)

    def record(self, event: TraceEvent) -> None:
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(event.model_dump_json() + "\n")

    def events(self) -> list[TraceEvent]:
        if not self.path.exists():
            return []
        return [
            TraceEvent.model_validate_json(line)
            for line in self.path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
