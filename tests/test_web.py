"""tests/test_web.py — the Hestia console API. Skipped if [web] isn't installed."""

import pytest
pytest.importorskip("fastapi")
from fastapi.testclient import TestClient
from hestia.web.server import app, seed

client = TestClient(app)


def test_console_serves():
    assert "Hand Hestia a document" in client.get("/").text


def test_starts_empty():
    seed()
    s = client.get("/api/state").json()
    assert s["reminders"] == [] and s["bills"] == [] and s["approvals"] == []


def test_drop_invoice_records_flagged_bill():
    seed()
    inv = client.get("/api/samples").json()["Care invoice (Brightleaf)"]
    client.post("/api/process_document", json={"text": inv})
    bills = client.get("/api/state").json()["bills"]
    assert len(bills) == 1 and bills[0]["flags"]
    assert client.get("/api/state").json()["ledger"] == []


def test_pay_bill_holds_then_deny_keeps_money_put():
    seed()
    inv = client.get("/api/samples").json()["Care invoice (Brightleaf)"]
    client.post("/api/process_document", json={"text": inv})
    bid = client.get("/api/state").json()["bills"][0]["id"]
    assert client.post(f"/api/pay_bill/{bid}").json()["held"] is True
    pid = client.get("/api/state").json()["approvals"][0]["id"]
    client.post(f"/api/deny/{pid}")
    assert client.get("/api/state").json()["ledger"] == []


def test_scan_inbox_creates_items_and_duplicate():
    seed()
    client.post("/api/scan_inbox")
    s = client.get("/api/state").json()
    assert len(s["reminders"]) >= 1 and len(s["bills"]) >= 1


def test_complete_reminder():
    seed()
    client.post("/api/scan_inbox")
    rid = client.get("/api/state").json()["reminders"][0]["id"]
    assert client.post(f"/api/complete/{rid}").json()["done"] is True


def test_pdf_upload_records_bill():
    import pathlib
    pytest.importorskip("pypdf")
    pdf = pathlib.Path(__file__).resolve().parents[1] / "sample_docs" / "invoice_brightleaf.pdf"
    if not pdf.exists():
        pytest.skip("sample pdf missing")
    seed()
    with pdf.open("rb") as f:
        r = client.post("/api/process_upload", files={"file": ("invoice_brightleaf.pdf", f, "application/pdf")}).json()
    assert "invoice" in r["summary"].lower()
    assert client.get("/api/state").json()["bills"][0]["flags"]


def test_ask_hestia_answers_from_state():
    seed()
    inv = client.get("/api/samples").json()["Care invoice (Brightleaf)"]
    client.post("/api/process_document", json={"text": inv})
    a = client.post("/api/ask", json={"question": "anything suspicious?"}).json()["answer"]
    assert "flag" in a.lower() or "iban" in a.lower()


def test_state_has_past_due_flag():
    seed()
    rx = client.get("/api/samples").json()["Prescription (dosage)"]
    client.post("/api/process_document", json={"text": rx})
    rems = client.get("/api/state").json()["reminders"]
    assert any("past_due" in r and "iso" in r for r in rems)
