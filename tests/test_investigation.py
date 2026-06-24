"""
tests/test_investigation.py — the investigator's evidence is deterministic and
testable, even though the agent's reasoning over it needs a model. These lock in
the fraud signal the agent depends on.
"""

from __future__ import annotations

from sentinel.agents.investigation_skills import (
    check_iban_reputation,
    list_known_payees,
    lookup_payment_history,
)

INVOICE_IBAN = "DE00 1234 5678 9012 3456 00"          # attacker-controlled
BRIGHTLEAF_VERIFIED = "DE89 3704 0044 0532 0130 00"   # the real account


def test_invoice_iban_is_unrecognized():
    rep = check_iban_reputation(INVOICE_IBAN)
    assert rep["status"] == "unrecognized"
    assert lookup_payment_history(INVOICE_IBAN)["payments"] == 0


def test_real_vendor_account_is_recognized():
    rep = check_iban_reputation(BRIGHTLEAF_VERIFIED)
    assert rep["status"] == "established"
    assert rep["matches_payee"] == "Brightleaf Home Care"


def test_vendor_known_but_iban_mismatches():
    """The crux of the fraud: Brightleaf is a trusted payee, but the invoice's
    IBAN is not the one on file for them."""
    payees = {p["payee"]: p["verified_iban"] for p in list_known_payees()}
    assert "Brightleaf Home Care" in payees
    assert payees["Brightleaf Home Care"].replace(" ", "") != INVOICE_IBAN.replace(" ", "")
