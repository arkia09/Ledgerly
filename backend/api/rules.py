"""Turn recent user Corrections into short 'mistakes to avoid' rules for the model prompt.

Rules are generic. They never contain amounts or other customer data. Names appear only
for name corrections (e.g. 'read as "Honish" but was "Harish"'), which is what teaches the model.
"""
from .matching import normalize_name
from .models import Correction

MAX_RULE_LENGTH = 120
MAX_NAME_LENGTH = 30


def _clean(value: str) -> str:
    """Single line, no double quotes, bounded length."""
    text = " ".join((value or "").replace('"', "").split())
    return text[:MAX_NAME_LENGTH]


def rule_for(c: Correction) -> str | None:
    """One rule for one Correction, or None if it is trivial or not worth a rule."""
    if c.field == "name":
        if normalize_name(c.model_value) == normalize_name(c.user_value):
            return None
        if not normalize_name(c.model_value):
            return "A customer name was missed; read the name written on every row."
        return f'A name was read as "{_clean(c.model_value)}" but was actually "{_clean(c.user_value)}".'

    if c.field == "amount":
        if not c.model_value.strip():
            return "An amount was missed; every row has an amount in the Udhaar or Jama column."
        return "An amount was misread; read each digit of the amount carefully."

    if c.field == "date":
        if normalize_name(c.model_value) == normalize_name(c.user_value):
            return None
        return "A date was misread; copy each row's own date exactly as written."

    if c.field == "type":
        before, after = c.model_value.strip().lower(), c.user_value.strip().lower()
        if before == after:
            return None
        if before == "unknown":
            return "A row type was left unknown. Use the column (Udhaar or Jama) that holds the amount."
        return (f"A {after} row was read as {before}. "
                "Check which column (Udhaar or Jama) holds the amount.")

    if c.field == "struck_out":
        if c.user_value.strip().lower() == "true":
            return "A crossed-out row was missed; check every row for a strike-through line."
        return "A row was marked crossed-out by mistake; only mark rows with a visible line through them."

    if c.field == "row_deleted":
        return "A row was extracted that is not a ledger row; ignore headers, totals and margin notes."

    return None  # "item" and anything else: free text, not worth a rule


def build_rules(limit: int = 5) -> list[str]:
    """Rules from the `limit` most recent Corrections: deduplicated, newest first."""
    recent = Correction.objects.order_by("-created_at", "-id")[:limit]
    rules: list[str] = []
    for c in recent:
        rule = rule_for(c)
        if rule and len(rule) <= MAX_RULE_LENGTH and rule not in rules:
            rules.append(rule)
    return rules
