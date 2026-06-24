"""
hestia/bills.py — the unpaid-bill ledger with duplicate detection.

Tracks bills through due -> overdue -> paid, and flags two kinds of trouble at
intake: a suspicious payee/account (vendor-impersonation fraud), and a likely
DOUBLE BILLING — a new bill that duplicates one already in the ledger (same
payee + amount, or a repeated invoice reference). Catching the duplicate before
it's paid is the "faulty double billing" guard.
"""

from __future__ import annotations

import itertools
from datetime import date, datetime

from pydantic import BaseModel, Field


def _norm(s: str) -> str:
    return (s or "").replace(" ", "").upper()


class Bill(BaseModel):
    id: int = 0
    payee: str
    amount_eur: float
    iban: str = ""
    reference: str = ""
    due: date | None = None
    status: str = "due"             # due | overdue | paid
    flags: list[str] = Field(default_factory=list)  # advocate warnings

    def is_overdue(self, today: date | None = None) -> bool:
        return self.status == "due" and self.due is not None and self.due < (today or date.today())


class BillStore:
    def __init__(self) -> None:
        self._ids = itertools.count(1)
        self._items: dict[int, Bill] = {}

    def _duplicate_of(self, bill: Bill) -> Bill | None:
        for b in self._items.values():
            if b.status == "cancelled":
                continue                       # paid bills DO count — re-billing a paid item is the classic double bill
            same_ref = bill.reference and _norm(b.reference) == _norm(bill.reference)
            same_amount_payee = (
                b.payee.lower() == bill.payee.lower()
                and abs(b.amount_eur - bill.amount_eur) < 0.01
            )
            if same_ref or same_amount_payee:
                return b
        return None

    def add(self, bill: Bill, extra_flags: list[str] | None = None,
            check_duplicates: bool = True) -> Bill:
        dup = self._duplicate_of(bill) if check_duplicates else None
        bill.flags = list(extra_flags or [])
        if dup:
            if dup.status == "paid":
                bill.flags.append(
                    f"Possible DOUBLE BILLING — you already PAID bill #{dup.id} "
                    f"({dup.payee}, €{dup.amount_eur:,.0f}). Do not pay this again."
                )
            else:
                bill.flags.append(
                    f"Possible double billing — matches unpaid bill #{dup.id} "
                    f"({dup.payee}, €{dup.amount_eur:,.0f})."
                )
        bill.id = next(self._ids)
        self._items[bill.id] = bill
        return bill

    def get(self, bid: int) -> Bill | None:
        return self._items.get(bid)

    def all(self, today: date | None = None) -> list[Bill]:
        for b in self._items.values():
            if b.is_overdue(today):
                b.status = "overdue"
        return sorted(self._items.values(), key=lambda b: (b.status == "paid", b.due or date.max))

    def mark_paid(self, bid: int) -> Bill | None:
        b = self._items.get(bid)
        if b:
            b.status = "paid"
        return b

    def mark_cancelled(self, bid: int) -> Bill | None:
        b = self._items.get(bid)
        if b:
            b.status = "cancelled"
        return b
