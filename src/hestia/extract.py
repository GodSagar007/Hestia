"""hestia/extract.py — pull plain text out of an uploaded file (pdf, eml, txt).

So the caregiver can hand Hestia a real document, not just paste text. PDFs use
pypdf; emails use the stdlib email parser; anything else is decoded as text.
"""

from __future__ import annotations

import io


def extract_text(filename: str, data: bytes) -> str:
    name = (filename or "").lower()
    if name.endswith(".pdf"):
        try:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(data))
            return "\n".join((p.extract_text() or "") for p in reader.pages).strip()
        except Exception:
            return ""
    if name.endswith(".eml"):
        import email
        msg = email.message_from_bytes(data)
        parts: list[str] = []
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    parts.append((part.get_payload(decode=True) or b"").decode(errors="ignore"))
        else:
            parts.append((msg.get_payload(decode=True) or b"").decode(errors="ignore"))
        return (f"Subject: {msg.get('subject', '')}\n" + "\n".join(parts)).strip()
    return data.decode("utf-8", errors="ignore")
