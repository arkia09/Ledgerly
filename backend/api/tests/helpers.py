import io
import json
import shutil
import tempfile
from pathlib import Path

from django.test import TestCase, override_settings
from PIL import Image


def jpeg_bytes():
    buf = io.BytesIO()
    Image.new("RGB", (40, 30), "white").save(buf, "JPEG")
    return buf.getvalue()


def model_row(raw, date, name, item, amount, typ, struck=False):
    return {"raw_text": raw, "date": date, "name": name, "item": item, "amount": amount,
            "type": typ, "struck_out": struck, "confidence": 0.9}


SAMPLE_ROWS = [
    model_row("01/10 Babula atta 240", "01/10", "Babula", "atta", 240.0, "credit"),
    model_row("02/10 Ramesh 100", "02/10", "Ramesh", None, 100.0, "credit"),   # really a payment
    model_row("03/10 Geeta tea 120", "03/10", "Geeta", "tea", 120.0, "credit"),
]


class TempStorageTestCase(TestCase):
    """Isolated media folder and a tiny fake-extraction output folder."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        out = self.tmp / "outputs"
        out.mkdir()
        (out / "page01.json").write_text(json.dumps(
            {"model": "m", "seconds": 12.5, "page": {"rows": SAMPLE_ROWS, "page_total": None}}),
            encoding="utf-8")
        (out / "page02.json").write_text(json.dumps(
            {"model": "m", "seconds": 1.0, "page": {"rows": SAMPLE_ROWS[:1], "page_total": 5}}),
            encoding="utf-8")
        ctx = override_settings(MEDIA_ROOT=self.tmp / "media", LEDGERLY_FAKE_OUTPUT_DIR=out)
        ctx.enable()
        self.addCleanup(ctx.disable)
        self.addCleanup(shutil.rmtree, self.tmp, True)
