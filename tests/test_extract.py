"""tests/test_extract.py — uploaded-file text extraction (pdf / eml / txt)."""

from pathlib import Path

import pytest

from hestia.extract import extract_text

SAMPLES = Path(__file__).resolve().parents[1] / "sample_docs"


def test_txt():
    assert "hello" in extract_text("note.txt", b"hello there")


def test_eml_pulls_subject_and_body():
    eml = b"Subject: Invoice BH-2231\r\n\r\nAmount due EUR 4000, IBAN DE00 1234."
    out = extract_text("msg.eml", eml)
    assert "BH-2231" in out and "4000" in out


def test_pdf_extraction():
    pytest.importorskip("pypdf")
    pdf = SAMPLES / "invoice_brightleaf.pdf"
    if not pdf.exists():
        pytest.skip("sample pdf not present")
    text = extract_text(str(pdf), pdf.read_bytes())
    assert "Brightleaf" in text and "BH-2231" in text
