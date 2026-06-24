"""
hestia/inbox.py — read real email so Hestia works on a live inbox.

If Gmail/IMAP credentials are configured, this pulls the most recent messages
from a real inbox; otherwise it returns the mock emails so the product still runs
and demos with no setup. Either way, each email is handed to the agent as
UNTRUSTED DATA through Sentinel — a poisoned email cannot make the agent pay.

Configure (use a DEDICATED throwaway Gmail, not your personal one):
    1. Gmail -> Settings -> Forwarding and POP/IMAP -> enable IMAP.
    2. Google Account -> Security -> 2-Step Verification -> App passwords ->
       create one for "Mail". Use that 16-char password below (not your login).
    3. Set environment variables:
         set IMAP_HOST=imap.gmail.com
         set IMAP_USER=youraddress@gmail.com
         set IMAP_PASS=your-16-char-app-password
"""

from __future__ import annotations

import os

from .documents import SAMPLE_EMAILS
from .extract import extract_text


def _configured() -> bool:
    return all(os.environ.get(k) for k in ("IMAP_HOST", "IMAP_USER", "IMAP_PASS"))


def fetch_inbox(limit: int = 5) -> dict:
    """Return {'source': 'gmail'|'mock', 'emails': [text, ...]} — newest first."""
    if not _configured():
        return {"source": "mock", "emails": list(SAMPLE_EMAILS)}

    import imaplib

    host, user, pw = os.environ["IMAP_HOST"], os.environ["IMAP_USER"], os.environ["IMAP_PASS"]
    mailbox = os.environ.get("IMAP_MAILBOX", "INBOX")
    emails: list[str] = []
    conn = imaplib.IMAP4_SSL(host)
    try:
        conn.login(user, pw)
        conn.select(mailbox)
        _, data = conn.search(None, "ALL")
        ids = data[0].split()[-limit:]
        for mid in reversed(ids):                 # newest first
            _, msg = conn.fetch(mid, "(RFC822)")
            raw = msg[0][1]
            emails.append(extract_text("message.eml", raw))
    finally:
        try:
            conn.logout()
        except Exception:
            pass
    return {"source": "gmail", "emails": emails}
