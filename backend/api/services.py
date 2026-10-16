"""Customer summaries and report data, built on the pure functions in ledger.py."""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.utils import timezone

from .ledger import BUCKETS, ZERO, Aging, Item, balance, compute_aging
from .models import Customer


@dataclass
class CustomerSummary:
    customer: Customer
    balance: Decimal
    last_activity: date | None
    aging: Aging

    @property
    def oldest_unpaid_days(self):
        return self.aging.oldest_unpaid_days if self.balance > 0 else None


def to_items(entries) -> list[Item]:
    return [Item(e.date, e.type, e.amount, e.struck_out) for e in entries]


def customer_summaries(today: date | None = None) -> list[CustomerSummary]:
    """All customers, sorted by balance descending (then name)."""
    today = today or timezone.localdate()
    out = []
    for c in Customer.objects.prefetch_related("entries"):
        entries = sorted(c.entries.all(), key=lambda e: e.id)
        out.append(CustomerSummary(
            customer=c,
            balance=balance(to_items(entries)),
            last_activity=max((e.date for e in entries if e.date and not e.struck_out),
                              default=None),
            aging=compute_aging(to_items(entries), today),
        ))
    out.sort(key=lambda s: (-s.balance, s.customer.name.casefold()))
    return out


def owing(summaries):
    return [s for s in summaries if s.balance > 0]


def balances_report(today=None) -> dict:
    rows = owing(customer_summaries(today))
    return {
        "total_outstanding": sum((s.balance for s in rows), ZERO),
        "customers": [{"id": s.customer.id, "name": s.customer.name,
                       "balance": s.balance, "last_activity": s.last_activity} for s in rows],
    }


def aging_report(today=None) -> dict:
    rows = owing(customer_summaries(today))
    rows.sort(key=lambda s: (-s.aging.total, s.customer.name.casefold()))
    buckets = {b: ZERO for b in BUCKETS}
    customers = []
    for s in rows:
        for b in BUCKETS:
            buckets[b] += s.aging.buckets[b]
        customers.append({"id": s.customer.id, "name": s.customer.name,
                          **s.aging.buckets, "total": s.aging.total})
    return {"buckets": buckets, "customers": customers}
