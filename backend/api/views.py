import logging
from pathlib import Path

from django.db import IntegrityError, transaction
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from PIL import Image

from . import extractor, services
from .confirm import ConfirmError, confirm_page, validate_rows
from .dateparse import parse_date_text
from .ledger import running_balances
from .matching import suggest_customer
from .models import Correction, Customer, Entry, Page
from .rules import build_rules
from .util import error, iso, jr, num, read_json, to_decimal

log = logging.getLogger(__name__)


# ---------- pages ----------

def page_payload(page: Page, request) -> dict:
    today = timezone.localdate()
    candidates = list(Customer.objects.values_list("id", "name"))
    extracted = page.extracted_json or {}
    rows, hints = [], [{
        "row_index": None, "field": "struck_out", "code": "check_struck_out",
        "message": "The model never detects crossed-out rows. Compare each row with the photo."}]

    for i, r in enumerate(extracted.get("rows", [])):
        parsed = parse_date_text(r.get("date"), today)
        row = {"row_index": i, **r,
               "date_iso": iso(parsed), "date_valid": parsed is not None,
               "suggested_customer": suggest_customer(r.get("name"), candidates)}
        rows.append(row)

        def hint(field, code, message, i=i):
            hints.append({"row_index": i, "field": field, "code": code, "message": message})

        if not row["date_valid"]:
            hint("date", "date_unparseable", f"Could not read the date {r.get('date')!r}. Please fix it.")
        if r.get("amount") is None:
            hint("amount", "amount_missing", "No amount was read for this row.")
        if r.get("type") == "unknown":
            hint("type", "type_unknown", "Credit or payment could not be decided.")
        if not r.get("name"):
            hint("name", "name_missing", "No name was read for this row.")
        sc = row["suggested_customer"]
        if sc and sc["score"] < 100:
            hint("name", "customer_near_match",
                 f"{r.get('name')!r} looks like existing customer {sc['name']!r} ({sc['score']}%).")

    return {
        "page_id": page.id, "status": page.status,
        "image_url": request.build_absolute_uri(page.image.url) if page.image else None,
        "uploaded_at": page.uploaded_at.isoformat(),
        "rows": rows, "page_total": extracted.get("page_total"),
        "seconds": None if page.extraction_seconds is None else round(page.extraction_seconds, 1),
        "model": page.model_name, "extraction_error": page.extraction_error,
        "suggestions": hints,
    }


@csrf_exempt
@require_POST
def pages(request):
    upload = request.FILES.get("image")
    if upload is None:
        return error("Send the photo as multipart form field 'image'.")
    try:
        Image.open(upload).verify()
    except Exception:
        return error("That file is not a readable image.")
    upload.seek(0)
    original_name = Path(upload.name).name

    rules = build_rules()
    page = Page.objects.create(image=upload)   # saved first so a failure keeps the photo
    try:
        data, seconds, model_name = extractor.run_extraction(page.image.path, original_name, rules)
    except Exception as e:  # never swallow: record, log and report it
        log.exception("Extraction failed for page %s", page.id)
        raw = getattr(e, "raw", "")
        if type(e).__name__ in ("ExtractionError", "TinkerExtractionError"):
            message = ("The model's answer was not valid ledger JSON. Try again, "
                       "or enter the rows by hand. Raw output is included.")
        elif extractor.backend_name() == "tinker":
            message = (f"Extraction could not run: {e}. Check TINKER_API_KEY, your Tinker "
                       "billing, and that ft/train.py has produced ft/last_model.json.")
        else:
            message = (f"Extraction could not run: {e}. Check that Ollama is running "
                       "('ollama list') and the model is pulled.")
        page.extraction_error = f"{message} [{type(e).__name__}: {e}]"
        page.save(update_fields=["extraction_error"])
        return error("extraction_failed", 502, message=message, detail=str(e), raw=raw,
                     page_id=page.id)

    page.extracted_json = data
    page.extraction_seconds = seconds
    page.model_name = model_name
    page.save(update_fields=["extracted_json", "extraction_seconds", "model_name"])
    return jr(page_payload(page, request), 201)


@require_GET
def page_detail(request, pk):
    page = Page.objects.filter(pk=pk).first()
    if page is None:
        return error("Page not found.", 404)
    return jr(page_payload(page, request))


@csrf_exempt
@require_POST
def page_confirm(request, pk):
    page = Page.objects.filter(pk=pk).first()
    if page is None:
        return error("Page not found.", 404)
    if page.status == Page.CONFIRMED:
        return error("This page was already confirmed.", 409)
    try:
        body = read_json(request)
        raw_rows = body.get("rows") if isinstance(body, dict) else None
    except (ValueError, UnicodeDecodeError):
        return error("Body must be JSON: {\"rows\": [...]}.")
    try:
        count = len((page.extracted_json or {}).get("rows", []))
        rows = validate_rows(raw_rows, count)
        result = confirm_page(page.id, rows)
    except ConfirmError as e:
        return error(str(e), e.status, details=e.details)
    return jr(result, 201)


# ---------- customers and manual ledger entries ----------

def _clean_name(body):
    """Normalised customer name from a JSON body, or (None, error response)."""
    name = " ".join(str(body.get("name", "")).split()) if isinstance(body, dict) else ""
    if not name:
        return None, error("Customer name is required.")
    if len(name) > 200:
        return None, error("Customer name must be 200 characters or fewer.")
    return name, None


@csrf_exempt
@require_POST
def customer_create(request):
    try:
        body = read_json(request)
    except (ValueError, UnicodeDecodeError):
        return error("Body must be valid JSON.")
    name, err = _clean_name(body)
    if err:
        return err
    try:
        customer = Customer.objects.create(name=name)
    except IntegrityError:
        return error("A customer with this name already exists (ignoring case and extra spaces).", 409)
    return jr({"id": customer.id, "name": customer.name, "balance": 0,
               "last_activity": None, "oldest_unpaid_days": None}, 201)


@csrf_exempt
@require_POST
def customer_update(request, pk):
    customer = Customer.objects.filter(pk=pk).first()
    if customer is None:
        return error("Customer not found.", 404)
    try:
        body = read_json(request)
    except (ValueError, UnicodeDecodeError):
        return error("Body must be valid JSON.")
    name, err = _clean_name(body)
    if err:
        return err
    if Customer.objects.exclude(pk=customer.pk).filter(name__iexact=name).exists():
        return error("A customer with this name already exists (ignoring case).", 409)
    customer.name = name
    try:
        customer.save(update_fields=["name"])
    except IntegrityError:
        return error("A customer with this name already exists.", 409)
    return jr({"id": customer.id, "name": customer.name})


@csrf_exempt
@require_POST
def customer_delete(request, pk):
    """Delete a customer and all of their entries. Pages and corrections are kept, so the
    training data you built by confirming pages is not affected."""
    customer = Customer.objects.filter(pk=pk).first()
    if customer is None:
        return error("Customer not found.", 404)
    with transaction.atomic():
        entries = customer.entries.count()
        name = customer.name
        customer.delete()
    return jr({"deleted": pk, "name": name, "entries_deleted": entries})


@csrf_exempt
@require_POST
def customer_sale(request, pk):
    customer = Customer.objects.filter(pk=pk).first()
    if customer is None:
        return error("Customer not found.", 404)
    try:
        body = read_json(request)
    except (ValueError, UnicodeDecodeError):
        return error("Body must be valid JSON.")
    if not isinstance(body, dict):
        return error("Body must be a JSON object.")

    item = " ".join(str(body.get("item", "")).split())
    date_text = " ".join(str(body.get("date_text", "")).split())
    total = to_decimal(body.get("total_amount"))
    paid = to_decimal(body.get("paid_amount") or "0", allow_zero=True)   # 0 = fully on credit
    if total is None:
        return error("Total amount must be greater than zero and a valid monetary amount.")
    if paid is None or paid > total:
        return error("Amount paid must be between zero and the total amount.")
    if len(item) > 200:
        return error("Item description must be 200 characters or fewer.")
    parsed_date = parse_date_text(date_text) if date_text else timezone.localdate()
    if date_text and parsed_date is None:
        return error("Date could not be parsed. Use a date such as 12/10 or 21 Sep.")

    with transaction.atomic():
        credit = Entry.objects.create(customer=customer, date=parsed_date,
            date_text=date_text or parsed_date.strftime("%d/%m/%Y"), item=item or None,
            amount=total, type=Entry.CREDIT)
        payment = None
        if paid > 0:
            payment = Entry.objects.create(customer=customer, date=parsed_date,
                date_text=date_text or parsed_date.strftime("%d/%m/%Y"), item="Payment for sale",
                amount=paid, type=Entry.PAYMENT)
    return jr({"customer_id": customer.id, "entries_created": 1 + int(payment is not None),
               "credit_entry_id": credit.id, "payment_entry_id": payment.id if payment else None,
               "total_amount": num(total), "paid_amount": num(paid),
               "remaining_due": num(total - paid)}, 201)


@csrf_exempt
@require_POST
def customer_payment(request, pk):
    customer = Customer.objects.filter(pk=pk).first()
    if customer is None:
        return error("Customer not found.", 404)
    try:
        body = read_json(request)
    except (ValueError, UnicodeDecodeError):
        return error("Body must be valid JSON.")
    if not isinstance(body, dict):
        return error("Body must be a JSON object.")
    amount = to_decimal(body.get("amount"))
    if amount is None:
        return error("Payment amount must be greater than zero.")
    date_text = " ".join(str(body.get("date_text", "")).split())
    parsed_date = parse_date_text(date_text) if date_text else timezone.localdate()
    if date_text and parsed_date is None:
        return error("Date could not be parsed. Use a date such as 12/10 or 21 Sep.")
    entry = Entry.objects.create(customer=customer, date=parsed_date,
        date_text=date_text or parsed_date.strftime("%d/%m/%Y"),
        item="Payment received", amount=amount, type=Entry.PAYMENT)
    return jr({"entry_id": entry.id, "amount": num(amount)}, 201)


# ---------- customers ----------

@require_GET
def customer_list(request):
    return jr([{"id": s.customer.id, "name": s.customer.name, "balance": num(s.balance),
                "last_activity": iso(s.last_activity),
                "oldest_unpaid_days": s.oldest_unpaid_days}
               for s in services.customer_summaries()])


@require_GET
def customer_detail(request, pk):
    customer = Customer.objects.filter(pk=pk).first()
    if customer is None:
        return error("Customer not found.", 404)
    s = next(x for x in services.customer_summaries() if x.customer.id == customer.id)
    entries = sorted(customer.entries.all(),
                     key=lambda e: (e.date is None, e.date or timezone.localdate(), e.id))
    running = running_balances(services.to_items(entries))
    return jr({
        "id": customer.id, "name": customer.name, "balance": num(s.balance),
        "last_activity": iso(s.last_activity), "oldest_unpaid_days": s.oldest_unpaid_days,
        "entries": [{"id": e.id, "date": iso(e.date), "date_text": e.date_text, "item": e.item,
                     "amount": num(e.amount), "type": e.type, "struck_out": e.struck_out,
                     "page_id": e.page_id, "running_balance": num(rb)}
                    for e, rb in zip(entries, running)],
    })


# ---------- reports ----------

@require_GET
def report_balances(request):
    r = services.balances_report()
    return jr({"total_outstanding": num(r["total_outstanding"]),
               "customers": [{**c, "balance": num(c["balance"]),
                              "last_activity": iso(c["last_activity"])} for c in r["customers"]]})


def _aging_json(r):
    return {"buckets": {k: num(v) for k, v in r["buckets"].items()},
            "customers": [{k: (num(v) if k not in ("id", "name") else v) for k, v in c.items()}
                          for c in r["customers"]]}


@require_GET
def report_aging(request):
    return jr(_aging_json(services.aging_report()))


# ---------- debug helper ----------

@require_GET
def rules(request):
    return jr({"rules": build_rules(), "corrections_considered": min(5, Correction.objects.count())})
