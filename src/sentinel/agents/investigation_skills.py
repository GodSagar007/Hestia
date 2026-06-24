"""
agents/investigation_skills.py — read-only skills for the fraud investigator.

When Sentinel holds a payment, the investigator agent uses these to do the
checks an at-risk user often can't: does the IBAN actually match the vendor's
verified account, have we ever paid it, does it have any history. All read-only
— the investigator can look, but it cannot pay, approve, or release anything.

The mock data encodes a realistic vendor-impersonation fraud: the user really is
a Brightleaf customer, but the invoice routes money to an IBAN that is NOT
Brightleaf's verified account. That mismatch is the tell — and it's exactly the
kind of thing a busy or vulnerable person misses but an agent can catch.
"""

from __future__ import annotations


def _norm(iban: str) -> str:
    return iban.replace(" ", "").upper()


# The user's verified payee book: trusted payees -> their known-good IBAN.
_KNOWN_PAYEES = {
    "Brightleaf Home Care": "DE89 3704 0044 0532 0130 00",  # the REAL account
    "City Pharmacy": "DE12 5001 0517 0648 4898 90",
    "Dr. A. Mercer (GP)": "DE44 5001 0517 5407 3249 31",
}

# Past payments, keyed by normalized IBAN.
_HISTORY = {
    _norm("DE89 3704 0044 0532 0130 00"): {"payments": 7, "last_paid": "2026-05-02"},
    _norm("DE12 5001 0517 0648 4898 90"): {"payments": 3, "last_paid": "2026-04-18"},
}


def list_known_payees() -> list:
    """List the user's verified payees and the IBANs they are known to use.

    Use this first to check whether a claimed payee and the target IBAN match a
    trusted, verified account. Read-only.
    """
    return [{"payee": name, "verified_iban": iban} for name, iban in _KNOWN_PAYEES.items()]


def lookup_payment_history(iban: str) -> dict:
    """Return how many times the user has previously paid this IBAN, and when.

    A target IBAN with no payment history is a strong caution signal. Read-only.
    """
    rec = _HISTORY.get(_norm(iban))
    if rec:
        return {"iban": iban, "payments": rec["payments"], "last_paid": rec["last_paid"]}
    return {"iban": iban, "payments": 0, "last_paid": None}


def check_iban_reputation(iban: str) -> dict:
    """Check an IBAN against the verified payee book and history registry.

    Returns 'established' for known-good accounts, or 'unrecognized' with the
    specific reasons it looks risky. Read-only.
    """
    norm = _norm(iban)
    known = {_norm(v): k for k, v in _KNOWN_PAYEES.items()}
    if norm in known:
        return {"status": "established", "matches_payee": known[norm], "flags": []}
    return {
        "status": "unrecognized",
        "matches_payee": None,
        "flags": ["not in verified payee book", "no prior payments to this IBAN"],
    }
