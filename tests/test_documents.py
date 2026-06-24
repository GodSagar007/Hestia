"""tests/test_documents.py — the deterministic concierge fallback reader."""

from hestia.care import HestiaCare
from hestia.documents import SAMPLE_DOCS, SAMPLE_EMAILS, apply


def test_invoice_is_recorded_and_flagged():
    c = HestiaCare()
    r = apply(SAMPLE_DOCS["Care invoice (Brightleaf)"], c)
    assert r["recorded_bill"] and c.ledger == []
    assert any("different IBAN" in f for f in r["bill_flags"])


def test_appointment_is_scheduled():
    c = HestiaCare()
    r = apply(SAMPLE_DOCS["Appointment letter"], c)
    assert r["created_reminders"] and len(c.reminders.all()) == 1


def test_inbox_scan_detects_duplicate():
    c = HestiaCare()
    apply(SAMPLE_DOCS["Care invoice (Brightleaf)"], c)   # first invoice
    for e in SAMPLE_EMAILS:
        apply(e, c)
    dup = [b for b in c.bills.all() if any("double billing" in f.lower() for f in b.flags)]
    assert dup                                            # the emailed invoice is caught


def test_unknown_document_is_safe():
    c = HestiaCare()
    r = apply("Just saying hello, nothing to do.", c)
    assert not r["created_reminders"] and not r["recorded_bill"]


def test_prescription_sets_recurring_and_refill():
    from hestia.care import HestiaCare
    c = HestiaCare()
    r = apply(SAMPLE_DOCS["Prescription (dosage)"], c)
    rems = c.reminders.all()
    assert any(x.repeat == "daily" for x in rems)        # recurring dosage
    assert any("Refill" in x.title for x in rems)        # refill reminder
    assert len(r["created_reminders"]) >= 2


def test_double_billing_of_paid_is_caught_with_advice():
    from hestia.care import HestiaCare
    c = HestiaCare()
    apply(SAMPLE_DOCS["Routine bill (verified)"], c)      # auto-paid
    apply(SAMPLE_DOCS["Routine bill (verified)"], c)      # re-billed
    dup = [b for b in c.bills.all() if b.status == "due"][0]
    assert any("double billing" in f.lower() for f in dup.flags)
    assert any(f.startswith("Advice:") and "dispute" in f.lower() for f in dup.flags)



def test_poisoned_doc_flagged_when_guarded_clean_when_off():
    from hestia.care import HestiaCare
    on = HestiaCare(guarded=True)
    apply(SAMPLE_DOCS["Poisoned invoice (injection)"], on)
    assert any("injected" in f.lower() for f in on.bills.all()[-1].flags)   # detected
    off = HestiaCare(guarded=False)
    apply(SAMPLE_DOCS["Poisoned invoice (injection)"], off)
    assert off.bills.all()[-1].flags == []                                  # no detection when off


def test_injection_doc_never_auto_pays():
    from hestia.care import HestiaCare
    c = HestiaCare(guarded=True)
    apply(SAMPLE_DOCS["Poisoned invoice (injection)"], c)
    assert c.ledger == []          # held, not paid — architectural guarantee
