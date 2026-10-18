import json
from io import StringIO

from django.core.files.base import ContentFile
from django.core.management import call_command
from django.test import override_settings

from api.models import Customer, Entry, Page

from .helpers import TempStorageTestCase, jpeg_bytes


class ExportTrainingDataTests(TempStorageTestCase):
    def test_exports_confirmed_pages_only(self):
        page = Page(status=Page.CONFIRMED, model_name="m")
        page.image.save("p.jpg", ContentFile(jpeg_bytes()), save=False)
        page.save()
        draft = Page.objects.create(status=Page.EXTRACTED)
        demo = Page(status=Page.CONFIRMED, model_name="demo:page01")
        demo.image.save("d.jpg", ContentFile(jpeg_bytes()), save=False)
        demo.save()
        c = Customer.objects.create(name="Ramesh")
        for p, amt in ((page, 240), (demo, 1)):
            Entry.objects.create(customer=c, page=p, date_text="01/10", item="atta", amount=amt, type="credit")
        Entry.objects.create(customer=c, page=draft, date_text="x", amount=1, type="credit")

        pages, gt = self.tmp / "pages", self.tmp / "gt"
        with override_settings(LEDGERLY_PAGE_IMAGES_DIR=pages, LEDGERLY_GROUND_TRUTH_DIR=gt):
            call_command("export_training_data", stdout=StringIO())
        self.assertEqual([p.name for p in gt.glob("*.json")], [f"app_{page.id}.json"])
        data = json.loads((gt / f"app_{page.id}.json").read_text(encoding="utf-8"))
        self.assertEqual(data["rows"], [{"date": "01/10", "name": "Ramesh", "item": "atta",
                                         "amount": 240.0, "type": "credit", "struck_out": False}])
        self.assertTrue((pages / f"app_{page.id}.jpg").exists())
