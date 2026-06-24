"""tests/test_inbox.py — inbox falls back to mock when no IMAP creds are set."""

import os

from hestia.inbox import fetch_inbox


def test_mock_fallback_without_creds(monkeypatch):
    for k in ("IMAP_HOST", "IMAP_USER", "IMAP_PASS"):
        monkeypatch.delenv(k, raising=False)
    box = fetch_inbox()
    assert box["source"] == "mock" and len(box["emails"]) >= 1
