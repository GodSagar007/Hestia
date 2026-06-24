"""
hestia/ask.py — "Ask Hestia": answer a caregiver's question from the care state.

Deterministic so it works with no key. (With a Gemini key the concierge agent
could answer via read tools; this keeps it reliable for the demo.)
"""

from __future__ import annotations

from datetime import datetime


def answer_question(care, question: str) -> str:
    q = (question or "").lower().strip()
    rems = care.reminders
    bills = care.bills.all()
    active_bills = [b for b in bills if b.status in ("due", "overdue")]

    if "paid" in q or "did i pay" in q:
        for b in bills:
            if b.payee.split()[0].lower() in q and b.status == "paid":
                return f"Yes — {b.payee} (€{b.amount_eur:,.0f}) is marked paid."
        if care.ledger:
            return "Payments so far: " + "; ".join(care.ledger) + "."
        return "No payments have been made yet."

    if any(w in q for w in ("overdue", "missed", "late", "forgot")):
        od = [r for r in rems.all() if (not r.done) and r.when < datetime.now()]
        if od:
            return "Not done yet: " + ", ".join(f"{r.title} ({r.when:%a %H:%M})" for r in od) + "."
        return "Nothing is overdue — you're on top of it."

    if any(w in q for w in ("flag", "fraud", "suspicious", "duplicate", "double")):
        flagged = [b for b in active_bills if b.flags]
        if flagged:
            return "Flagged: " + "; ".join(f"{b.payee} €{b.amount_eur:,.0f} — {b.flags[0]}" for b in flagged) + "."
        return "No bills are currently flagged."

    if any(w in q for w in ("appointment", "doctor", "visit", "clinic")):
        appts = [r for r in rems.upcoming() if r.kind == "appointment"]
        if appts:
            return "Appointments: " + ", ".join(f"{r.title} ({r.when:%a %d %b %H:%M})" for r in appts) + "."
        return "No upcoming appointments."

    if any(w in q for w in ("med", "dose", "pill", "prescription", "tablet")):
        meds = [r for r in rems.upcoming() if r.kind == "medication"]
        if meds:
            return "Medication: " + ", ".join(f"{r.title}{' (daily)' if r.repeat else ''} at {r.when:%H:%M}" for r in meds) + "."
        return "No medication reminders set."

    if any(w in q for w in ("bill", "owe", "pay", "invoice")):
        if active_bills:
            return "Bills to review: " + "; ".join(f"{b.payee} €{b.amount_eur:,.0f} ({b.status})" for b in active_bills) + "."
        return "No bills need review right now."

    # default: a quick what's-coming-up summary
    up = rems.upcoming()
    parts = []
    if up:
        parts.append(f"{len(up)} upcoming reminder(s): " + ", ".join(r.title for r in up[:4]))
    if active_bills:
        parts.append(f"{len(active_bills)} bill(s) to review")
    return (". ".join(parts) + ".") if parts else "Nothing scheduled and no bills to review."
