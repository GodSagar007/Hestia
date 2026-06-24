"""
demo/hestia_demo.py - Hestia (the care concierge) running on the Sentinel spine.

Keyless: shows the product mechanics end to end without an API key.
  1. Schedule two reminders (reversible -> flow straight through).
  2. Export a calendar (.ics).
  3. Attempt to pay a (fraudulent) care invoice -> Sentinel HOLDS it -> it becomes
     a caregiver approval with the advocate's evidence attached.
  4. Show the caregiver's daily briefing.
  5. Caregiver denies the suspicious payment -> money never moves.

Run:  python -m demo.hestia_demo
"""

from __future__ import annotations

from datetime import datetime, timedelta

from hestia.care import HestiaCare
from hestia.reminders import Reminder


def run() -> None:
    care = HestiaCare()
    soon = datetime.now() + timedelta(days=1)

    print("1) Schedule reminders (reversible -> allowed)")
    care.schedule_reminder(Reminder(title="Take blood-pressure medication", when=soon.replace(hour=8, minute=0), kind="medication"))
    care.schedule_reminder(Reminder(title="Dr. Mercer follow-up", when=soon.replace(hour=14, minute=30), kind="appointment", notes="Bring current medication list"))
    for r in care.reminders.all():
        print(f"   - {r.when:%a %d %b %H:%M}  {r.title}")

    print("\n2) Export calendar (.ics)")
    ics = care.export_calendar()
    print("   " + ics.splitlines()[0] + " ...  (" + str(len(ics.splitlines())) + " lines)")

    print("\n3) Pay a care invoice -> Sentinel decides")
    pa = care.pay_bill(4000.0, "DE00 1234 5678 9012 3456 00", "Brightleaf Home Care")
    print(f"   {pa.summary}")
    print(f"   -> {pa.status.upper()}: {pa.reason}")
    print("   advocate findings:")
    for e in pa.evidence:
        print(f"     - {e}")

    print("\n4) Caregiver daily briefing")
    b = care.daily_briefing()
    print(f"   reminders: {len(b['upcoming_reminders'])} upcoming")
    print(f"   needs your approval: {len(b['needs_your_approval'])}")

    print("\n5) Caregiver reviews and DENIES the suspicious payment")
    care.approvals.deny(pa.id)
    print(f"   payment status: {care.approvals._items[pa.id].status}")
    print(f"   money moved: {care.ledger or 'none'}")


if __name__ == "__main__":
    run()
