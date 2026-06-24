"""
hestia/care.py — the Hestia care service, on the Sentinel spine.

Reminders and bill-recording flow through (reversible / read-only). Paying a bill
is irreversible, so Sentinel HOLDS it into a caregiver approval; approving it both
performs the payment and marks the bill paid. Bills are flagged at intake for a
suspicious account (vendor-impersonation) or a likely double billing.
"""

from __future__ import annotations

from datetime import date, datetime

from sentinel.agents.investigation_skills import (
    check_iban_reputation,
    list_known_payees,
    lookup_payment_history,
)
from sentinel.detectors.heuristic import HeuristicDetector
from sentinel.policy import PolicyEngine
from sentinel.session import GatewaySession
from sentinel.verdict import Decision

from .approvals import ApprovalQueue
from .bills import Bill, BillStore
from .reminders import Reminder, ReminderStore, to_ics


def _norm(iban: str) -> str:
    return (iban or "").replace(" ", "").upper()


def gather_payment_evidence(iban: str, payee_claim: str) -> list[str]:
    payees = {p["payee"]: p["verified_iban"] for p in list_known_payees()}
    out: list[str] = []
    if payee_claim in payees and _norm(payees[payee_claim]) != _norm(iban):
        out.append(
            f"{payee_claim} is a known payee, but their verified account is "
            f"{payees[payee_claim]} — this bill uses a different IBAN"
        )
    if iban and lookup_payment_history(iban)["payments"] == 0:
        out.append("No prior payments have ever gone to this account")
    if iban and check_iban_reputation(iban)["status"] != "established":
        out.append("This IBAN is unrecognized — not in the verified payee book")
    return out


def advise(flags: list[str]) -> str | None:
    """Turn findings into a plain 'what to do' for the caregiver."""
    low = " ".join(flags).lower()
    if "double billing" in low:
        return ("Contact the biller to dispute this — you appear to have already been "
                "billed for it (see the matched bill above). Don't pay it twice.")
    if "different iban" in low or "unrecognized" in low or "no prior payments" in low:
        return ("Call the payee on a number from their official website — not the "
                "email or invoice — to confirm the account before paying.")
    return None


class HestiaCare:
    def __init__(self, guarded: bool = True) -> None:
        self.guarded = guarded   # when False, Sentinel is bypassed (demo: see the harm)
        self.auto_pay_limit = 500.0   # verified routine bills up to this are paid automatically
        self.session = GatewaySession(PolicyEngine(detectors=[HeuristicDetector()]))
        self.reminders = ReminderStore()
        self.bills = BillStore()
        self.approvals = ApprovalQueue()
        self.ledger: list[str] = []

    # --- reminders (reversible) ---
    def schedule_reminder(self, reminder: Reminder) -> Reminder:
        self.session.inspect_call("create_reminder", {"title": reminder.title})
        return self.reminders.add(reminder)

    def complete_reminder(self, rid: int):
        return self.reminders.complete(rid)

    # --- bills (recorded, flagged; never auto-paid) ---
    def record_bill(self, payee: str, amount_eur: float, iban: str = "",
                    reference: str = "", due: date | None = None) -> Bill:
        # All advocate intelligence — fraud flags, duplicate detection, advice —
        # is part of Sentinel. With Sentinel off, the bill is recorded naively.
        flags = gather_payment_evidence(iban, payee) if (self.guarded and iban) else []
        bill = self.bills.add(
            Bill(payee=payee, amount_eur=amount_eur, iban=iban, reference=reference, due=due),
            extra_flags=flags,
            check_duplicates=self.guarded,
        )
        if self.guarded:
            advice = advise(bill.flags)
            if advice:
                bill.flags.append("Advice: " + advice)
        return bill

    # --- pay a bill (irreversible -> Sentinel hold -> caregiver approval) ---
    def is_auto_payable(self, payee: str, iban: str, amount_eur: float, bill_id: int | None = None) -> bool:
        """A verified, routine, low-value payment to a known account is standing-
        authorized — the caregiver already trusts this payee, so the agent pays it.
        Anything flagged, novel, or large is held."""
        if not self.guarded:
            return False
        bill = self.bills.get(bill_id) if bill_id else None
        if bill and bill.flags:
            return False
        payees = {p["payee"]: p["verified_iban"] for p in list_known_payees()}
        verified = payee in payees and _norm(payees[payee]) == _norm(iban)
        return verified and amount_eur <= self.auto_pay_limit

    def pay_bill(self, amount_eur: float, iban: str, payee: str, bill_id: int | None = None):
        if not self.guarded:
            return self._execute_payment(amount_eur, iban, bill_id)
        if self.is_auto_payable(payee, iban, amount_eur, bill_id):
            return self._execute_payment(amount_eur, iban, bill_id)   # verified routine -> auto-pay
        evidence = (self.bills.get(bill_id).flags if bill_id and self.bills.get(bill_id) and self.bills.get(bill_id).flags
                    else gather_payment_evidence(iban, payee))
        verdict = self.session.inspect_call("pay_bill", {"amount_eur": amount_eur, "iban": iban})
        return self.approvals.hold(
            tool="pay_bill",
            summary=f"Pay {amount_eur:.0f} EUR to {iban}  ({payee})",
            reason=verdict.reason,
            action=lambda: self._execute_payment(amount_eur, iban, bill_id),
            evidence=evidence,
            bill_id=bill_id,
        )

    def deny_payment(self, pid: int):
        """Caregiver denied a held payment -> cancel the bill so it leaves the list."""
        pa = self.approvals.deny(pid)
        if pa and pa.bill_id:
            self.bills.mark_cancelled(pa.bill_id)
        return pa

    def _execute_payment(self, amount_eur: float, iban: str, bill_id: int | None = None) -> str:
        record = f"PAID {amount_eur:.2f} EUR to {iban}"
        self.ledger.append(record)
        if bill_id:
            self.bills.mark_paid(bill_id)
        return record

    def export_calendar(self) -> str:
        return to_ics(self.reminders.all())

    # --- the daily briefing ---
    def daily_briefing(self, now: datetime | None = None) -> dict:
        return {
            "upcoming_reminders": [r.title for r in self.reminders.upcoming(now)],
            "overdue_reminders": [r.title for r in self.reminders.overdue(now)],
            "bills_due": [f"{b.payee} €{b.amount_eur:,.0f}" for b in self.bills.all() if b.status != "paid"],
            "needs_your_approval": [p.summary for p in self.approvals.pending()],
        }
