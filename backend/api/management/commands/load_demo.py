"""Load the hand-written ground-truth pages as confirmed demo data. Safe to run twice."""
import json
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from api.dateparse import parse_date_text
from api.matching import normalize_name
from api.models import Customer, Entry, Page


class Command(BaseCommand):
    help = "Create demo customers/entries from data/ground_truth/*.json (idempotent)."

    def handle(self, *args, **opts):
        gt_dir = Path(settings.LEDGERLY_GROUND_TRUTH_DIR)
        files = sorted(p for p in gt_dir.glob("*.json") if not p.name.startswith("_"))
        if not files:
            self.stderr.write(f"No ground-truth files in {gt_dir}")
            return
        today = timezone.localdate()
        made_pages = made_entries = 0
        for f in files:
            tag = f"demo:{f.stem}"
            if Page.objects.filter(model_name=tag).exists():
                self.stdout.write(f"skip {f.name} (already loaded)")
                continue
            rows = json.loads(f.read_text(encoding="utf-8"))["rows"]
            with transaction.atomic():
                model_rows = [{
                    "raw_text": " ".join(str(x) for x in (r["date"], r["name"], r.get("item"),
                                                          r["amount"]) if x),
                    "date": r["date"], "name": r["name"], "item": r.get("item"),
                    "amount": r["amount"], "type": r["type"],
                    "struck_out": r["struck_out"], "confidence": 1.0} for r in rows]
                page = Page(model_name=tag, status=Page.CONFIRMED, extraction_seconds=0,
                            extracted_json={"rows": model_rows, "page_total": None})
                img = Path(settings.LEDGERLY_PAGE_IMAGES_DIR) / f"{f.stem}.jpg"
                if img.exists():
                    page.image.save(img.name, ContentFile(img.read_bytes()), save=False)
                page.save()
                for r in rows:
                    customer = Customer.objects.filter(
                        name_key=normalize_name(r["name"])).first()
                    if customer is None:
                        customer = Customer.objects.create(name=r["name"])
                    Entry.objects.create(
                        customer=customer, page=page, date=parse_date_text(r["date"], today),
                        date_text=r["date"], item=r.get("item"), amount=r["amount"],
                        type=r["type"], struck_out=r["struck_out"])
                    made_entries += 1
            made_pages += 1
            self.stdout.write(f"loaded {f.name}: {len(rows)} entries")
        self.stdout.write(self.style.SUCCESS(
            f"Done: {made_pages} pages, {made_entries} entries, "
            f"{Customer.objects.count()} customers total."))
