"""
hestia/web/server.py — the Hestia caregiver console (local web app).

The document/inbox pipeline runs the real concierge AGENT when a Gemini key is
present (HESTIA_USE_LLM=1); otherwise it falls back to the deterministic reader so
the product always works. Everything else — the ledger, reminders, approvals — is
keyless. Run:
    pip install -e ".[web,adk]"
    python -m hestia.web.server          # http://127.0.0.1:8123
"""

from __future__ import annotations

import os
from pathlib import Path

try:                                  # let config live in a .env file
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

from datetime import date, datetime

from fastapi import FastAPI, File, UploadFile
from fastapi.responses import HTMLResponse, Response

from hestia import runtime
from hestia.care import HestiaCare

app = FastAPI(title="Hestia Care Concierge")
HERE = Path(__file__).parent
MODEL = os.environ.get("SENTINEL_MODEL", "gemini-3.5-flash")
CARE = HestiaCare()


def seed() -> None:
    """Fresh, empty session. The caregiver populates it by handing Hestia documents
    or scanning the inbox — that's what makes the agent's work visible."""
    global CARE
    CARE = HestiaCare()
    runtime.set_care(CARE)


seed()


def _agent_enabled() -> bool:
    return os.environ.get("HESTIA_USE_LLM") == "1" and bool(
        os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY"))


async def _process_one(text: str) -> dict:
    """Run one document/email through the agent (if enabled) or the deterministic
    reader. The agent decides which tools to call; the reader applies fixed rules.
    Either way, actions go through the same care service and Sentinel."""
    if not text.strip():
        return {"summary": "Nothing to read.", "mode": "none"}
    runtime.set_care(CARE)
    if _agent_enabled():
        try:
            from hestia.concierge import run_concierge
            summary = await run_concierge(MODEL, text, date.today().isoformat())
            return {"summary": summary, "mode": "agent"}
        except Exception:
            pass  # graceful degradation -> deterministic reader
    from hestia.documents import apply
    return {"summary": apply(text, CARE)["summary"], "mode": "rules"}


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return (HERE / "console.html").read_text(encoding="utf-8")


@app.get("/api/state")
def state() -> dict:
    return {
        "mode": "agent" if _agent_enabled() else "rules",
        "reminders": [
            {"id": r.id, "title": r.title, "when": r.when.strftime("%a %d %b · %H:%M"),
             "kind": r.kind, "notes": r.notes, "done": r.done, "overdue": r.overdue(), "repeat": r.repeat,
             "iso": r.when.isoformat(), "past_due": (not r.done) and r.when < datetime.now(), "conflict": r.conflict}
            for r in CARE.reminders.all()
        ],
        "bills": [
            {"id": b.id, "payee": b.payee, "amount": b.amount_eur, "iban": b.iban,
             "status": b.status, "flags": b.flags}
            for b in CARE.bills.all()
        ],
        "approvals": [p.model_dump() for p in CARE.approvals.pending()],
        "ledger": CARE.ledger,
        "sentinel_on": CARE.guarded,
    }


@app.post("/api/process_document")
async def process_document(payload: dict) -> dict:
    return await _process_one((payload or {}).get("text", ""))


@app.post("/api/process_upload")
async def process_upload(file: UploadFile = File(...)) -> dict:
    from hestia.extract import extract_text
    text = extract_text(file.filename, await file.read())
    result = await _process_one(text)
    result["filename"] = file.filename
    return result


@app.post("/api/scan_inbox")
async def scan_inbox() -> dict:
    from hestia.inbox import fetch_inbox
    box = fetch_inbox()
    results = [await _process_one(e) for e in box["emails"]]
    return {"count": len(results), "source": box["source"],
            "summaries": [r["summary"] for r in results],
            "mode": results[0]["mode"] if results else "none"}


@app.get("/api/samples")
def samples() -> dict:
    from hestia.documents import SAMPLE_DOCS
    return SAMPLE_DOCS


@app.post("/api/complete/{rid}")
def complete(rid: int) -> dict:
    r = CARE.complete_reminder(rid)
    return {"ok": bool(r), "done": bool(r and r.done)}


@app.post("/api/pay_bill/{bid}")
def pay_bill(bid: int) -> dict:
    b = CARE.bills.get(bid)
    if not b:
        return {"ok": False, "error": "no such bill"}
    res = CARE.pay_bill(b.amount_eur, b.iban, b.payee, bill_id=b.id)
    if isinstance(res, str):
        return {"ok": True, "held": False, "result": res}
    return {"ok": True, "held": True, "approval_id": res.id}


@app.post("/api/approve/{pid}")
def approve(pid: int) -> dict:
    return CARE.approvals.approve(pid).model_dump()


@app.post("/api/deny/{pid}")
def deny(pid: int) -> dict:
    return CARE.deny_payment(pid).model_dump()


@app.post("/api/sentinel")
def sentinel_toggle(payload: dict) -> dict:
    CARE.guarded = bool((payload or {}).get("on", True))
    return {"guarded": CARE.guarded}


@app.post("/api/ask")
def ask(payload: dict) -> dict:
    from hestia.ask import answer_question
    q = (payload or {}).get("question", "")
    if not q.strip():
        return {"answer": "Ask me about meds, bills, or appointments."}
    return {"answer": answer_question(CARE, q)}


@app.post("/api/seed")
def reseed() -> dict:
    seed()
    return {"ok": True}


@app.get("/api/calendar.ics")
def calendar() -> Response:
    return Response(CARE.export_calendar(), media_type="text/calendar",
                    headers={"Content-Disposition": "attachment; filename=hestia-reminders.ics"})


@app.get("/api/calendar/{rid}.ics")
def calendar_one(rid: int) -> Response:
    from hestia.reminders import to_ics
    r = CARE.reminders.get(rid)
    return Response(to_ics([r] if r else []), media_type="text/calendar",
                    headers={"Content-Disposition": f"attachment; filename=hestia-reminder-{rid}.ics"})


def main() -> None:
    import uvicorn
    port = int(os.environ.get("PORT", "8123"))
    print(f"\n  Hestia console -> http://127.0.0.1:{port}\n")
    uvicorn.run(app, host="127.0.0.1", port=port)


if __name__ == "__main__":
    main()
