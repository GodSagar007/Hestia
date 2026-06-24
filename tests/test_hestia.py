"""tests/test_hestia.py — the Hestia care service on the Sentinel spine."""

from datetime import datetime

from hestia.care import HestiaCare
from hestia.reminders import Reminder, ReminderStore, to_ics

INVOICE_IBAN = "DE00 1234 5678 9012 3456 00"
VERIFIED_IBAN = "DE89 3704 0044 0532 0130 00"


def test_reminder_ics_valid():
    s = ReminderStore()
    s.add(Reminder(title="Med", when=datetime(2026, 7, 1, 8, 0), kind="medication"))
    ics = to_ics(s.all())
    assert ics.startswith("BEGIN:VCALENDAR") and "SUMMARY:Med" in ics


def test_reminder_tick_and_overdue():
    c = HestiaCare()
    r = c.schedule_reminder(Reminder(title="Pills", when=datetime(2000, 1, 1, 8, 0), kind="medication"))
    assert c.reminders.overdue()                     # past + not done -> overdue
    c.complete_reminder(r.id)
    assert not c.reminders.overdue()                 # ticked -> no longer overdue


def test_recorded_bill_is_flagged_not_paid():
    c = HestiaCare()
    b = c.record_bill("Brightleaf Home Care", 4000, INVOICE_IBAN, "BH-2231")
    assert b.status == "due" and c.ledger == []
    assert any("different IBAN" in f for f in b.flags)


def test_double_billing_detected():
    c = HestiaCare()
    c.record_bill("Brightleaf Home Care", 4000, INVOICE_IBAN, "BH-2231")
    dup = c.record_bill("Brightleaf Home Care", 4000, INVOICE_IBAN, "BH-2231")
    assert any("double billing" in f.lower() for f in dup.flags)


def test_verified_routine_bill_auto_pays():
    c = HestiaCare()
    b = c.record_bill("Brightleaf Home Care", 50, VERIFIED_IBAN, "OK-1")  # verified, low, clean
    res = c.pay_bill(b.amount_eur, b.iban, b.payee, bill_id=b.id)
    assert isinstance(res, str) and c.bills.get(b.id).status == "paid"   # paid automatically


def test_large_verified_bill_is_held():
    c = HestiaCare()
    b = c.record_bill("Brightleaf Home Care", 5000, VERIFIED_IBAN, "BIG-1")  # over auto-pay limit
    pa = c.pay_bill(b.amount_eur, b.iban, b.payee, bill_id=b.id)
    assert not isinstance(pa, str) and c.ledger == []   # held despite being verified


def test_held_fraud_then_approved():
    c = HestiaCare()
    b = c.record_bill("Brightleaf Home Care", 4000, INVOICE_IBAN, "BH-2231")
    pa = c.pay_bill(b.amount_eur, b.iban, b.payee, bill_id=b.id)
    assert pa.status == "pending" and c.ledger == []
    c.approvals.approve(pa.id)
    assert c.ledger and c.bills.get(b.id).status == "paid"


def test_deny_cancels_the_bill():
    c = HestiaCare()
    b = c.record_bill("Brightleaf Home Care", 4000, INVOICE_IBAN, "BH-2231")
    pa = c.pay_bill(b.amount_eur, b.iban, b.payee, bill_id=b.id)
    c.deny_payment(pa.id)
    assert c.ledger == [] and c.bills.get(b.id).status == "cancelled"


def test_flagged_bill_includes_advice():
    c = HestiaCare()
    b = c.record_bill("Brightleaf Home Care", 4000, INVOICE_IBAN, "BH-2231")
    assert any(f.startswith("Advice:") for f in b.flags)


def test_sentinel_off_sends_immediately():
    c = HestiaCare(guarded=False)
    res = c.pay_bill(4000, INVOICE_IBAN, "Brightleaf Home Care")
    assert isinstance(res, str) and c.ledger        # sent, no hold


def test_sentinel_on_holds():
    c = HestiaCare(guarded=True)
    res = c.pay_bill(4000, INVOICE_IBAN, "Brightleaf Home Care")
    assert not isinstance(res, str) and c.ledger == []   # held, nothing sent


def test_sentinel_off_records_bill_without_flags():
    c = HestiaCare(guarded=False)
    b = c.record_bill("Brightleaf Home Care", 4000, INVOICE_IBAN, "BH-2231")
    assert b.flags == []          # no advocate detection when Sentinel is off


def test_sentinel_off_no_duplicate_detection():
    c = HestiaCare(guarded=False)
    c.record_bill("Brightleaf Home Care", 4000, INVOICE_IBAN, "BH-2231")
    dup = c.record_bill("Brightleaf Home Care", 4000, INVOICE_IBAN, "BH-2231")
    assert dup.flags == []        # duplicate detection is part of Sentinel
