"""
hestia/concierge_tools.py — the concierge agent's tools.

Each is a function the agent can choose to call. They act on the live care
session (runtime.care) and return plain-language results the agent reasons over.
Crucially, attempt_payment cannot move money: it routes through Sentinel, which
holds it for the caregiver. The agent decides WHICH tools to use; it can't
escape the guardrail.
"""

from __future__ import annotations

from datetime import datetime

from . import runtime
from .reminders import Reminder


def schedule_reminder(title: str, when_iso: str, kind: str = "general", notes: str = "", repeat: str = "") -> str:
    """Schedule a reminder. when_iso is ISO 8601 (e.g. 2026-06-23T14:30).
    kind is one of: medication, appointment, bill, general.
    repeat can be "daily" for recurring dosage reminders (else leave empty)."""
    try:
        when = datetime.fromisoformat(when_iso)
    except ValueError:
        return f"Could not understand the date '{when_iso}'. Use ISO like 2026-06-23T14:30."
    r = runtime.care.schedule_reminder(Reminder(title=title, when=when, kind=kind, notes=notes, repeat=repeat))
    rep = f" (repeats {r.repeat})" if r.repeat else ""
    return f"Scheduled '{r.title}' for {r.when:%a %d %b %H:%M}{rep} (id {r.id})."


def record_bill(payee: str, amount_eur: float, iban: str = "", reference: str = "") -> str:
    """Record a bill in the ledger. Always record bills; never pay automatically.
    Returns any fraud or double-billing warnings found at intake."""
    b = runtime.care.record_bill(payee, amount_eur, iban, reference)
    msg = f"Recorded bill #{b.id}: {b.payee} €{b.amount_eur:,.0f} (status: {b.status})."
    if b.flags:
        msg += " WARNINGS: " + " | ".join(b.flags)
    return msg


def attempt_payment(amount_eur: float, iban: str, payee: str) -> str:
    """Attempt to pay a bill. This NEVER sends money directly — Sentinel holds it
    for the caregiver's approval. Only use for bills that look legitimate."""
    res = runtime.care.pay_bill(amount_eur, iban, payee)
    if isinstance(res, str):
        return res
    return (f"Payment of €{amount_eur:,.0f} was HELD for the caregiver's approval "
            f"(approval id {res.id}); it was not sent.")


TOOLS = [schedule_reminder, record_bill, attempt_payment]
