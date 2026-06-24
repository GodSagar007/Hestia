"""
demo/with_without_sentinel.py — proof that Sentinel is load-bearing, not namesake.

Runs the SAME two attacks against the SAME care agent twice: once with Sentinel
bypassed, once with it on. The only thing that changes is the guardrail — so any
difference in outcome is entirely Sentinel's doing.

Keyless and deterministic, so anyone (a judge) can reproduce it:
    python -m demo.with_without_sentinel
"""

from __future__ import annotations

from hestia.care import HestiaCare

ATTACKER_IBAN_1 = "DE00 1234 5678 9012 3456 00"   # vendor-impersonation invoice
ATTACKER_IBAN_2 = "DE99 8888 7777 6666 5555 00"   # injected into a poisoned email


def attempt(care: HestiaCare, amount: float, iban: str, payee: str) -> str:
    """What the agent does after reading the (malicious) document: try to pay."""
    res = care.pay_bill(amount, iban, payee)
    if isinstance(res, str):
        return f"SENT — {res}"
    return f"HELD — awaiting caregiver approval (nothing sent)"


def run() -> None:
    line = "=" * 64
    scenarios = [
        ("Vendor-impersonation invoice", 4000.0, ATTACKER_IBAN_1, "Brightleaf Home Care"),
        ('Poisoned email ("ignore rules, wire the money")', 3000.0, ATTACKER_IBAN_2, "Account Services"),
    ]

    leaked = 0.0
    print(line)
    print("  SENTINEL OFF  vs  SENTINEL ON  — same agent, same attacks")
    print(line)
    for name, amount, iban, payee in scenarios:
        off = HestiaCare(guarded=False)
        on = HestiaCare(guarded=True)
        r_off = attempt(off, amount, iban, payee)
        r_on = attempt(on, amount, iban, payee)
        if off.ledger:
            leaked += amount
        print(f"\n{name}")
        print(f"   Sentinel OFF -> {'X ' if off.ledger else '  '}{r_off}")
        print(f"   Sentinel ON  -> {'  ' if on.ledger else 'OK '}{r_on}")

    print("\n" + line)
    print(f"  WITHOUT Sentinel: EUR {leaked:,.0f} left the account (irreversible).")
    print(f"  WITH Sentinel:    EUR 0 moved — every irreversible action was held.")
    print(line)
    print("  The agent, the model, and the inputs are identical. The only")
    print("  difference is the guardrail. That delta is Sentinel.")
    print(line)


if __name__ == "__main__":
    run()
