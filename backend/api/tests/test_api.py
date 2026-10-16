import json
import os
from datetime import timedelta
from decimal import Decimal as D
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from api.models import Correction, Customer, Entry, Page

from .helpers import SAMPLE_ROWS, TempStorageTestCase, jpeg_bytes


def upload(client, name="page01.jpg"):
    return client.post("/api/pages/", {"image": SimpleUploadedFile(name, jpeg_bytes(), "image/jpeg")})


def post_json(client, url, body):
    return client.post(url, json.dumps(body), content_type="application/json")


FAKE = {"LEDGERLY_FAKE_EXTRACT": "1"}


class UploadTests(TempStorageTestCase):
    def test_fake_upload_returns_rows_and_creates_no_entries(self):
        Customer.objects.create(name="Babulal")
        with mock.patch.dict(os.environ, FAKE):
            r = upload(self.client)
        self.assertEqual(r.status_code, 201)
        d = r.json()
        self.assertEqual(len(d["rows"]), 3)
        self.assertEqual(d["seconds"], 12.5)
        self.assertEqual([x["row_index"] for x in d["rows"]], [0, 1, 2])
        self.assertEqual(d["rows"][0]["suggested_customer"]["name"], "Babulal")
        self.assertIsNone(d["rows"][2]["suggested_customer"])
        self.assertTrue(d["rows"][0]["date_valid"])
        self.assertTrue(any(s["code"] == "customer_near_match" for s in d["suggestions"]))
        self.assertEqual(Entry.objects.count(), 0)
        self.assertEqual(Page.objects.get().extracted_json["rows"][0]["name"], "Babula")

    def test_fake_matches_filename_stem_and_falls_back(self):
        with mock.patch.dict(os.environ, FAKE):
            self.assertEqual(len(upload(self.client, "page02.jpg").json()["rows"]), 1)
            self.assertEqual(len(upload(self.client, "IMG_1234.jpg").json()["rows"]), 3)

    def test_unparseable_date_is_flagged(self):
        page = Page.objects.create(extracted_json={"rows": [
            {**SAMPLE_ROWS[0], "date": "??"}], "page_total": None})
        d = self.client.get(f"/api/pages/{page.id}/").json()
        self.assertFalse(d["rows"][0]["date_valid"])
        self.assertTrue(any(s["code"] == "date_unparseable" for s in d["suggestions"]))

    def test_get_page_returns_same_payload(self):
        with mock.patch.dict(os.environ, FAKE):
            posted = upload(self.client).json()
        got = self.client.get(f"/api/pages/{posted['page_id']}/").json()
        self.assertEqual(got["rows"], posted["rows"])
        self.assertEqual(self.client.get("/api/pages/999/").status_code, 404)

    def test_missing_or_bad_image(self):
        self.assertEqual(self.client.post("/api/pages/", {}).status_code, 400)
        bad = SimpleUploadedFile("x.jpg", b"not an image", "image/jpeg")
        self.assertEqual(self.client.post("/api/pages/", {"image": bad}).status_code, 400)

    def test_real_path_passes_recent_rules_to_extractor(self):
        page = Page.objects.create()
        Correction.objects.create(page=page, row_index=0, field="struck_out",
                                  model_value="false", user_value="true")
        fake_mod = mock.Mock(MODEL="gemma-test")
        fake_mod.extract.return_value = (mock.Mock(model_dump=lambda: {"rows": [], "page_total": None}), 3.0)
        with mock.patch.dict(os.environ, {"LEDGERLY_FAKE_EXTRACT": ""}), \
                mock.patch("api.extractor.load", return_value=fake_mod):
            r = upload(self.client)
        self.assertEqual(r.status_code, 201)
        rules = fake_mod.extract.call_args.kwargs["extra_rules"]
        self.assertTrue(any("crossed-out" in x for x in rules))

    def test_extraction_error_returns_502_and_keeps_page(self):
        class ExtractionError(Exception):
            raw = "{broken json"
        fake_mod = mock.Mock()
        fake_mod.extract.side_effect = ExtractionError("bad schema")
        with mock.patch.dict(os.environ, {"LEDGERLY_FAKE_EXTRACT": ""}), \
                mock.patch("api.extractor.load", return_value=fake_mod), \
                self.assertLogs("api.views", "ERROR"):
            r = upload(self.client)
        self.assertEqual(r.status_code, 502)
        self.assertEqual(r.json()["raw"], "{broken json")
        page = Page.objects.get(pk=r.json()["page_id"])
        self.assertIn("bad schema", page.extraction_error)

    def test_ollama_down_is_also_502(self):
        with mock.patch.dict(os.environ, {"LEDGERLY_FAKE_EXTRACT": ""}), \
                mock.patch("api.extractor.load", side_effect=ConnectionError("refused")), \
                self.assertLogs("api.views", "ERROR"):
            r = upload(self.client)
        self.assertEqual(r.status_code, 502)
        self.assertIn("Ollama", r.json()["message"])


class ConfirmTests(TempStorageTestCase):
    def setUp(self):
        super().setUp()
        with mock.patch.dict(os.environ, FAKE):
            self.page_id = upload(self.client).json()["page_id"]
        self.url = f"/api/pages/{self.page_id}/confirm/"

    def row(self, **kw):
        base = {"row_index": 0, "date_text": "01/10", "name": "Babula", "item": "atta",
                "amount": 240, "type": "credit", "struck_out": False,
                "customer_id": None, "create_new_customer": True}
        base.update(kw)
        return base

    def unchanged_rows(self):
        return [self.row(),
                self.row(row_index=1, date_text="02/10", name="Ramesh", item=None, amount=100,
                         type="credit"),
                self.row(row_index=2, date_text="03/10", name="Geeta", item="tea", amount=120)]

    def test_unchanged_page_creates_entries_and_no_corrections(self):
        r = post_json(self.client, self.url, {"rows": self.unchanged_rows()})
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()["entries_created"], 3)
        self.assertEqual(r.json()["corrections_created"], 0)
        self.assertEqual(Page.objects.get(pk=self.page_id).status, "confirmed")
        self.assertEqual(Customer.objects.count(), 3)
        self.assertEqual(Entry.objects.get(customer__name="Geeta").amount, D("120.00"))

    def test_changes_are_stored_as_corrections(self):
        rows = self.unchanged_rows()
        rows[0]["name"] = "Babulal"                       # name fix
        rows[1].update(type="payment")                     # type fix
        rows[2].update(name=" geeta ", amount="120.0")     # trivial/equal: no correction
        r = post_json(self.client, self.url, {"rows": rows})
        self.assertEqual(r.json()["corrections_created"], 2)
        fields = set(Correction.objects.values_list("field", flat=True))
        self.assertEqual(fields, {"name", "type"})
        c = Correction.objects.get(field="name")
        self.assertEqual((c.model_value, c.user_value, c.row_index), ("Babula", "Babulal", 0))
        self.assertEqual(c.raw_text, "01/10 Babula atta 240")

    def test_picking_existing_customer_records_name_correction(self):
        existing = Customer.objects.create(name="Babulal")
        rows = self.unchanged_rows()
        rows[0].update(customer_id=existing.id, name="Babula", create_new_customer=False)
        r = post_json(self.client, self.url, {"rows": rows})
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(Entry.objects.filter(customer=existing).count(), 1)
        c = Correction.objects.get(field="name")
        self.assertEqual(c.user_value, "Babulal")

    def test_amount_compared_numerically(self):
        rows = self.unchanged_rows()
        rows[0]["amount"] = "240.00"
        rows[2]["amount"] = 125
        r = post_json(self.client, self.url, {"rows": rows})
        self.assertEqual(r.json()["corrections_created"], 1)
        self.assertEqual(Correction.objects.get().field, "amount")

    def test_second_confirm_is_409(self):
        post_json(self.client, self.url, {"rows": self.unchanged_rows()})
        r = post_json(self.client, self.url, {"rows": self.unchanged_rows()})
        self.assertEqual(r.status_code, 409)
        self.assertEqual(Entry.objects.count(), 3)

    def test_deleted_row_and_user_added_row(self):
        rows = [self.row(), self.row(row_index=1, date_text="02/10", name="Ramesh", item=None, amount=100),
                self.row(row_index=None, name="Newperson", item="soap", amount=30)]  # row 2 deleted
        rows[1]["type"] = "credit"
        r = post_json(self.client, self.url, {"rows": rows})
        self.assertEqual(r.json()["entries_created"], 3)
        deleted = Correction.objects.get(field="row_deleted")
        self.assertEqual(deleted.row_index, 2)
        self.assertEqual(deleted.raw_text, "03/10 Geeta tea 120")
        self.assertEqual(Correction.objects.count(), 1)   # added rows create no corrections
        self.assertFalse(Customer.objects.filter(name="Geeta").exists())

    def test_unparseable_date_stored_as_null_and_flagged(self):
        rows = self.unchanged_rows()
        rows[0]["date_text"] = "garbage"
        r = post_json(self.client, self.url, {"rows": rows}).json()
        self.assertEqual(len(r["entries_with_unparsed_date"]), 1)
        e = Entry.objects.get(date_text="garbage")
        self.assertIsNone(e.date)

    def test_validation_errors_write_nothing(self):
        rows = self.unchanged_rows()
        rows[0]["amount"] = -5
        rows[1]["type"] = "unknown"
        rows[2].update(create_new_customer=False)  # no such customer exists
        r = post_json(self.client, self.url, {"rows": rows})
        self.assertEqual(r.status_code, 400)
        self.assertEqual({d["field"] for d in r.json()["details"]}, {"amount", "type", "customer_id"})
        self.assertEqual(Entry.objects.count(), 0)
        self.assertEqual(Page.objects.get(pk=self.page_id).status, "extracted")

    def test_bad_body_and_unknown_page(self):
        self.assertEqual(self.client.post(self.url, "nope", content_type="application/json").status_code, 400)
        self.assertEqual(post_json(self.client, "/api/pages/999/confirm/", {"rows": []}).status_code, 404)

    def test_struck_out_row_stored_but_not_counted(self):
        rows = self.unchanged_rows()
        rows[0]["struck_out"] = True
        post_json(self.client, self.url, {"rows": rows})
        self.assertEqual(Entry.objects.filter(struck_out=True).count(), 1)
        names = [c["name"] for c in self.client.get("/api/customers/").json()]
        self.assertIn("Babula", names)
        babula = next(c for c in self.client.get("/api/customers/").json() if c["name"] == "Babula")
        self.assertEqual(babula["balance"], 0.0)

    def test_rules_endpoint_reflects_corrections(self):
        rows = self.unchanged_rows()
        rows[0]["name"] = "Babulal"
        post_json(self.client, self.url, {"rows": rows})
        rules = self.client.get("/api/rules/").json()["rules"]
        self.assertEqual(rules, ['A name was read as "Babula" but was actually "Babulal".'])


class CustomerAndReportTests(TempStorageTestCase):
    def setUp(self):
        super().setUp()
        t = timezone.localdate()
        self.ramesh = Customer.objects.create(name="Ramesh")
        self.geeta = Customer.objects.create(name="गीता")
        self.paid = Customer.objects.create(name="Paid Up")
        def e(c, days, amt, typ, struck=False):
            Entry.objects.create(customer=c, date=t - timedelta(days=days), date_text="x",
                                 amount=D(amt), type=typ, struck_out=struck)
        e(self.ramesh, 80, 300, "credit"); e(self.ramesh, 10, 100, "credit")
        e(self.ramesh, 5, 120, "payment"); e(self.ramesh, 3, 999, "credit", struck=True)
        e(self.geeta, 40, 50, "credit")
        e(self.paid, 20, 70, "credit"); e(self.paid, 2, 70, "payment")

    def test_customer_list_sorted_by_balance(self):
        d = self.client.get("/api/customers/").json()
        self.assertEqual([c["name"] for c in d], ["Ramesh", "गीता", "Paid Up"])
        self.assertEqual([c["balance"] for c in d], [280.0, 50.0, 0.0])
        self.assertEqual(d[0]["oldest_unpaid_days"], 80)    # payment of 120 eats the 300 credit first
        self.assertIsNone(d[2]["oldest_unpaid_days"])

    def test_customer_detail_running_balance(self):
        d = self.client.get(f"/api/customers/{self.ramesh.id}/").json()
        self.assertEqual([e["running_balance"] for e in d["entries"]], [300.0, 400.0, 280.0, 280.0])
        self.assertEqual(d["balance"], 280.0)
        self.assertEqual(self.client.get("/api/customers/999/").status_code, 404)

    def test_reports_shapes_and_values(self):
        b = self.client.get("/api/reports/balances/").json()
        self.assertEqual(b["total_outstanding"], 330.0)
        self.assertEqual([c["name"] for c in b["customers"]], ["Ramesh", "गीता"])
        self.assertEqual(set(b["customers"][0]), {"id", "name", "balance", "last_activity"})
        a = self.client.get("/api/reports/aging/").json()
        self.assertEqual(set(a["buckets"]), {"0-30", "31-60", "61+", "unknown"})
        self.assertEqual(a["buckets"], {"0-30": 100.0, "31-60": 50.0, "61+": 180.0, "unknown": 0.0})
        self.assertEqual(set(a["customers"][0]), {"id", "name", "0-30", "31-60", "61+", "unknown", "total"})
        self.assertEqual(a["customers"][0]["total"], 280.0)

    def test_png_endpoints_with_data(self):
        for u in ("/api/reports/balances.png", "/api/reports/aging.png"):
            r = self.client.get(u)
            self.assertEqual((r.status_code, r["Content-Type"]), (200, "image/png"))
            self.assertTrue(r.content.startswith(b"\x89PNG"))

    def test_png_endpoints_empty_database(self):
        Customer.objects.all().delete()
        for u in ("/api/reports/balances.png", "/api/reports/aging.png"):
            r = self.client.get(u)
            self.assertEqual(r.status_code, 200)
            self.assertTrue(r.content.startswith(b"\x89PNG"))
        self.assertEqual(self.client.get("/api/reports/balances/").json(),
                         {"total_outstanding": 0.0, "customers": []})


class CustomerModelTests(TempStorageTestCase):
    def test_name_unique_case_insensitive(self):
        from django.db import IntegrityError, transaction
        Customer.objects.create(name="Ramesh Kumar")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Customer.objects.create(name="  ramesh   KUMAR ")


class ManualCustomerEntryTests(TempStorageTestCase):
    def test_create_customer_and_reject_duplicate_case_insensitively(self):
        created = post_json(self.client, "/api/customers/create/", {"name": "  Priya   Sharma "})
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.json()["name"], "Priya Sharma")
        duplicate = post_json(self.client, "/api/customers/create/", {"name": "priya sharma"})
        self.assertEqual(duplicate.status_code, 409)

    def test_sale_tracks_full_partial_and_zero_payment(self):
        customer = Customer.objects.create(name="Manual customer")
        sale = post_json(self.client, f"/api/customers/{customer.id}/sales/", {
            "item": "Rice", "date_text": "2026-10-16", "total_amount": "500.00", "paid_amount": "200.00"
        })
        self.assertEqual(sale.status_code, 201)
        self.assertEqual(sale.json()["remaining_due"], 300.0)
        self.assertEqual(customer.entries.count(), 2)
        full = post_json(self.client, f"/api/customers/{customer.id}/sales/", {
            "item": "Oil", "date_text": "2026-10-16", "total_amount": "100", "paid_amount": "100"
        })
        self.assertEqual(full.status_code, 201)
        unpaid = post_json(self.client, f"/api/customers/{customer.id}/sales/", {
            "item": "Sugar", "date_text": "2026-10-16", "total_amount": "50", "paid_amount": "0"
        })
        self.assertEqual(unpaid.status_code, 201)
        self.assertEqual(unpaid.json()["remaining_due"], 50.0)

    def test_separate_payment_updates_balance(self):
        customer = Customer.objects.create(name="Payment customer")
        Entry.objects.create(customer=customer, amount=D("300.00"), type=Entry.CREDIT,
                             date=timezone.localdate(), date_text="today", item="Groceries")
        response = post_json(self.client, f"/api/customers/{customer.id}/payments/", {
            "amount": "125.00", "date_text": timezone.localdate().isoformat()
        })
        self.assertEqual(response.status_code, 201)
        detail = self.client.get(f"/api/customers/{customer.id}/").json()
        self.assertEqual(detail["balance"], 175.0)
