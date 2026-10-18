"""Turn pages you confirmed in the app into labelled training examples for finetune/.

Each confirmed page already holds a photo plus rows you checked and corrected, so the review
screen doubles as the labelling tool. Writes data/pages/app_<id>.jpg and
data/ground_truth/app_<id>.json (same format finetune/ and extraction/score.py read).

Caveat: the label is the final customer name. If you merged "Ramesh" on the page into an existing
"Ramesh Kumar", the label says "Ramesh Kumar" while the photo says "Ramesh". Only export pages
where names match what is written, or fix the JSON by hand.
"""
import json
import shutil
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from api.models import Page


class Command(BaseCommand):
    help = "Export confirmed pages (photo + corrected rows) to data/pages and data/ground_truth."

    def handle(self, *args, **opts):
        pages_dir = Path(settings.LEDGERLY_PAGE_IMAGES_DIR)
        gt_dir = Path(settings.LEDGERLY_GROUND_TRUTH_DIR)
        pages_dir.mkdir(parents=True, exist_ok=True)
        gt_dir.mkdir(parents=True, exist_ok=True)
        done = 0
        pages = (Page.objects.filter(status=Page.CONFIRMED).exclude(model_name__startswith="demo:")
                 .prefetch_related("entries__customer").order_by("id"))
        for page in pages:
            entries = sorted(page.entries.all(), key=lambda e: e.id)
            if not page.image or not entries:
                continue
            stem = f"app_{page.id}"
            ext = Path(page.image.name).suffix.lower() or ".jpg"
            shutil.copyfile(page.image.path, pages_dir / f"{stem}{ext}")
            rows = [{"date": e.date_text, "name": e.customer.name, "item": e.item,
                     "amount": float(e.amount), "type": e.type, "struck_out": e.struck_out}
                    for e in entries]
            (gt_dir / f"{stem}.json").write_text(
                json.dumps({"page_type": "app", "source": "app", "rows": rows},
                           indent=2, ensure_ascii=False), encoding="utf-8")
            done += 1
        self.stdout.write(self.style.SUCCESS(f"Exported {done} confirmed pages to {gt_dir}"))
