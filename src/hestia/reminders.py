"""hestia/reminders.py — reminders you can tick off, with overdue detection."""

from __future__ import annotations

import itertools
from datetime import datetime

from pydantic import BaseModel, Field


class Reminder(BaseModel):
    id: int = 0
    title: str
    when: datetime
    notes: str = ""
    kind: str = "general"   # medication | appointment | bill | general
    done: bool = False
    repeat: str = ""        # "", "daily" — recurring dosage reminders
    conflict: str = ""      # set when an appointment clashes with another

    def overdue(self, now: datetime | None = None) -> bool:
        # recurring reminders don't go "overdue" — they just recur
        return (not self.done) and (not self.repeat) and self.when < (now or datetime.now())


class ReminderStore:
    def __init__(self) -> None:
        self._ids = itertools.count(1)
        self._items: dict[int, Reminder] = {}

    def add(self, reminder: Reminder) -> Reminder:
        reminder.id = next(self._ids)
        self._items[reminder.id] = reminder
        return reminder

    def all(self) -> list[Reminder]:
        return sorted(self._items.values(), key=lambda r: r.when)

    def get(self, rid: int) -> Reminder | None:
        return self._items.get(rid)

    def upcoming(self, now: datetime | None = None) -> list[Reminder]:
        now = now or datetime.now()
        return [r for r in self.all() if r.when >= now and not r.done]

    def overdue(self, now: datetime | None = None) -> list[Reminder]:
        return [r for r in self.all() if r.overdue(now)]

    def complete(self, rid: int) -> Reminder | None:
        r = self._items.get(rid)
        if r:
            r.done = True
        return r


def _ics_dt(dt: datetime) -> str:
    return dt.strftime("%Y%m%dT%H%M%S")


def to_ics(reminders: list[Reminder]) -> str:
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Hestia//Care Concierge//EN"]
    for r in reminders:
        ev = [
            "BEGIN:VEVENT",
            f"UID:hestia-{r.id}-{_ics_dt(r.when)}@hestia.local",
            f"DTSTAMP:{_ics_dt(datetime.now())}",
            f"DTSTART:{_ics_dt(r.when)}",
            f"SUMMARY:{r.title}",
            f"DESCRIPTION:{r.notes}".replace("\n", " "),
            f"CATEGORIES:{r.kind.upper()}",
        ]
        if r.repeat == "daily":
            ev.append("RRULE:FREQ=DAILY")
        ev.append("END:VEVENT")
        lines += ev
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"
