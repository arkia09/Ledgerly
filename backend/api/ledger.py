"""Pure ledger maths: balances, running balances and FIFO aging.

No Django imports on purpose, so this is easy to test and hard to get subtly wrong.
Amounts are Decimal. Struck-out entries are ignored everywhere.
"""
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

ZERO = Decimal("0")
BUCKETS = ("0-30", "31-60", "61+", "unknown")


@dataclass(frozen=True)
class Item:
    date: date | None
    type: str            # "credit" or "payment"
    amount: Decimal
    struck_out: bool = False


@dataclass
class Aging:
    buckets: dict = field(default_factory=lambda: {b: ZERO for b in BUCKETS})
    oldest_unpaid_days: int | None = None

    @property
    def total(self) -> Decimal:
        return sum(self.buckets.values(), ZERO)


def balance(items) -> Decimal:
    """credit minus payment, struck-out excluded."""
    total = ZERO
    for it in items:
        if it.struck_out:
            continue
        total += it.amount if it.type == "credit" else -it.amount
    return total


def running_balances(items) -> list[Decimal]:
    """Running balance after each item, in the order given. A struck-out item adds nothing."""
    out, total = [], ZERO
    for it in items:
        if not it.struck_out:
            total += it.amount if it.type == "credit" else -it.amount
        out.append(total)
    return out


def bucket_for_age(age_days: int) -> str:
    if age_days <= 30:       # includes future-dated (negative age)
        return "0-30"
    if age_days <= 60:
        return "31-60"
    return "61+"


def compute_aging(items, today: date) -> Aging:
    """FIFO: all payments are applied to the oldest credits first.

    Whatever credit is left unpaid is bucketed by its age in days. Credits with no
    date sort last (so payments clear dated credits first) and land in "unknown".
    Payment dates are ignored: only the total paid matters. Ties keep input order.
    """
    active = [i for i in items if not i.struck_out]
    credits = sorted((i for i in active if i.type == "credit"),
                     key=lambda i: (i.date is None, i.date or date.min))
    paid = sum((i.amount for i in active if i.type == "payment"), ZERO)

    result = Aging()
    for c in credits:
        remaining = c.amount
        if paid > 0:
            used = min(paid, remaining)
            paid -= used
            remaining -= used
        if remaining <= 0:
            continue
        if c.date is None:
            result.buckets["unknown"] += remaining
            continue
        age = max((today - c.date).days, 0)
        result.buckets[bucket_for_age(age)] += remaining
        if result.oldest_unpaid_days is None or age > result.oldest_unpaid_days:
            result.oldest_unpaid_days = age
    return result
