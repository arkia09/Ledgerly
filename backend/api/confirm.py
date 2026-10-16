"""Confirming a reviewed page: validate rows, create entries, record corrections."""
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from .dateparse import parse_date_text
from .matching import normalize_name
from .models import Correction, Customer, Entry, Page
from .util import to_decimal


class ConfirmError(Exception):
    def __init__(self, message, status=400, details=None):
        super().__init__(message)
        self.status = status
        self.details = details or []


def _opt_str(v):
    return None if v is None else str(v).strip()


def validate_rows(raw_rows, extracted_count: int) -> list[dict]:
    """Return cleaned rows or raise ConfirmError(400) listing every problem found."""
    if not isinstance(raw_rows, list):
        raise ConfirmError("'rows' must be a list.")
    customers = {c.id: c for c in Customer.objects.all()}
    known_keys = {c.name_key for c in customers.values()}
    seen_idx, errors, clean = set(), [], []

    for i, r in enumerate(raw_rows):
        def bad(field, msg, i=i):
            errors.append({"row": i, "field": field, "message": msg})

        if not isinstance(r, dict):
            bad("row", "Each row must be an object.")
            continue

        idx = r.get("row_index")
        if idx is not None:
            if isinstance(idx, bool) or not isinstance(idx, int) or not 0 <= idx < extracted_count:
                bad("row_index", f"Must be null or an integer from 0 to {extracted_count - 1}.")
                idx = None
            elif idx in seen_idx:
                bad("row_index", "Duplicate row_index.")
            else:
                seen_idx.add(idx)

        cid = r.get("customer_id")
        customer = None
        if cid is not None:
            customer = customers.get(cid) if isinstance(cid, int) and not isinstance(cid, bool) else None
            if customer is None:
                bad("customer_id", "No customer with that id.")

        name = _opt_str(r.get("name")) or ""
        create_new = r.get("create_new_customer", False)
        if not isinstance(create_new, bool):
            bad("create_new_customer", "Must be true or false.")
            create_new = False
        if customer is None and cid is None:
            if not name:
                bad("name", "Required when customer_id is null.")
            else:
                key = normalize_name(name)
                if key not in known_keys:
                    if create_new:
                        known_keys.add(key)
                    else:
                        bad("customer_id", "No customer with this name exists. "
                            "Pick one, or set create_new_customer to true.")

        amount = to_decimal(r.get("amount"))
        if amount is None:
            bad("amount", "Must be a number greater than 0.")

        typ = r.get("type")
        if typ not in ("credit", "payment"):
            bad("type", "Must be 'credit' or 'payment'.")

        struck = r.get("struck_out", False)
        if not isinstance(struck, bool):
            bad("struck_out", "Must be true or false.")
            struck = False

        clean.append({"row_index": idx, "date_text": _opt_str(r.get("date_text")) or "",
                      "name": name, "item": _opt_str(r.get("item")) or None,
                      "amount": amount, "type": typ, "struck_out": struck,
                      "customer": customer, "create_new": create_new})
    if errors:
        raise ConfirmError("Some rows are invalid.", 400, errors)
    return clean


def _text(v) -> str:
    return "" if v is None else str(v)


def _amount_text(d: Decimal) -> str:
    return format(d.normalize(), "f")


def _model_amount(v) -> Decimal | None:
    try:
        return None if v is None else Decimal(str(v)).quantize(Decimal("0.01"))
    except Exception:
        return None


def diff_row(model: dict, final: dict) -> list[tuple[str, str, str]]:
    """(field, model_value, user_value) for each real change. Trivial case/space edits are ignored."""
    changes = []
    for f, mk in (("name", "name"), ("item", "item"), ("date", "date")):
        before = _text(model.get(mk))
        after = final[f]
        if normalize_name(before) != normalize_name(after):
            changes.append((f, before.strip(), after))
    m_amt = _model_amount(model.get("amount"))
    if m_amt is None or m_amt != final["amount"]:
        changes.append(("amount", "" if m_amt is None else _amount_text(m_amt),
                        _amount_text(final["amount"])))
    if _text(model.get("type")).strip().lower() != final["type"]:
        changes.append(("type", _text(model.get("type")), final["type"]))
    if bool(model.get("struck_out")) != final["struck_out"]:
        changes.append(("struck_out", str(bool(model.get("struck_out"))).lower(),
                        str(final["struck_out"]).lower()))
    return changes


@transaction.atomic
def confirm_page(page_id: int, rows: list[dict]) -> dict:
    page = Page.objects.select_for_update().get(pk=page_id)
    if page.status == Page.CONFIRMED:
        raise ConfirmError("This page was already confirmed.", 409)
    model_rows = (page.extracted_json or {}).get("rows", [])
    today = timezone.localdate()

    entries_made, corrections, created_customers, unparsed = 0, [], 0, []
    for r in rows:
        customer = r["customer"]
        if customer is None:
            customer = Customer.objects.filter(name_key=normalize_name(r["name"])).first()
            if customer is None:
                customer = Customer.objects.create(name=r["name"])
                created_customers += 1
        parsed = parse_date_text(r["date_text"], today)
        entry = Entry.objects.create(
            customer=customer, page=page, date=parsed, date_text=r["date_text"],
            item=r["item"], amount=r["amount"], type=r["type"], struck_out=r["struck_out"])
        entries_made += 1
        if r["date_text"] and parsed is None:
            unparsed.append(entry.id)

        if r["row_index"] is not None:
            model = model_rows[r["row_index"]]
            # When an existing customer was picked, that customer's name is the final name.
            final = {"name": customer.name, "item": r["item"] or "", "date": r["date_text"],
                     "amount": r["amount"], "type": r["type"], "struck_out": r["struck_out"]}
            for f, before, after in diff_row(model, final):
                corrections.append(Correction(page=page, row_index=r["row_index"], field=f,
                                              model_value=before, user_value=after,
                                              raw_text=_text(model.get("raw_text"))))

    kept = {r["row_index"] for r in rows if r["row_index"] is not None}
    for idx, model in enumerate(model_rows):
        if idx not in kept:
            raw = _text(model.get("raw_text"))
            corrections.append(Correction(page=page, row_index=idx, field="row_deleted",
                                          model_value=raw, user_value="", raw_text=raw))

    Correction.objects.bulk_create(corrections)
    page.status = Page.CONFIRMED
    page.save(update_fields=["status"])
    return {"page_id": page.id, "status": page.status, "entries_created": entries_made,
            "corrections_created": len(corrections), "customers_created": created_customers,
            "entries_with_unparsed_date": unparsed}
