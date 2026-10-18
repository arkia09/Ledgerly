"""Offline tests for the parts of the pipeline that need no Tinker key.  Run:  python -m unittest test_data"""
import json
import unittest

from PIL import Image

import common as c


class TargetAndParse(unittest.TestCase):
    ROWS = [{"date": "01/10", "name": "रमेश", "item": None, "amount": 100.0, "type": "payment", "struck_out": False},
            {"date": "02/10", "name": "Sunita", "item": "oil", "amount": 180.5, "type": "credit", "struck_out": True}]

    def test_round_trip_keeps_devanagari_and_amounts(self):
        text = c.target_json(self.ROWS)
        self.assertIn("रमेश", text)                       # not escaped to र...
        self.assertIn('"amount":100,', text)              # 100.0 -> 100
        page = c.parse_output(text)
        self.assertEqual([r["name"] for r in page["rows"]], ["रमेश", "Sunita"])
        self.assertEqual(page["rows"][1]["amount"], 180.5)
        self.assertTrue(page["rows"][1]["struck_out"])
        self.assertEqual(page["rows"][0]["raw_text"], "01/10 रमेश 100")

    def test_parse_tolerates_code_fences_and_chatter(self):
        text = "Here you go:\n```json\n" + c.target_json(self.ROWS) + "\n```"
        self.assertEqual(len(c.parse_output(text)["rows"]), 2)

    def test_parse_rejects_garbage(self):
        with self.assertRaises(ValueError):
            c.parse_output("I cannot read this page")
        with self.assertRaises(Exception):
            c.parse_output('{"rows":[{"name":"A","amount":1,"type":"gift"}]}')


class Augmentation(unittest.TestCase):
    def test_deterministic_and_changes_image(self):
        img = Image.new("RGB", (400, 300), (200, 180, 160))
        for x in range(0, 400, 20):
            for y in range(300):
                img.putpixel((x, y), (30, 30, 90))
        a, b = c.augment(img, 7), c.augment(img, 7)
        self.assertEqual(a.tobytes(), b.tobytes())
        self.assertNotEqual(a.tobytes(), c.augment(img, 8).tobytes())
        self.assertTrue(a.size[0] <= 400 and a.size[1] <= 300)


class GroundTruthMatchesTargets(unittest.TestCase):
    def test_every_ground_truth_page_produces_valid_target(self):
        stems = c.ground_truth_pages()
        self.assertTrue(stems)
        for stem in stems:
            gt = json.loads((c.GROUND_TRUTH / f"{stem}.json").read_text(encoding="utf-8"))
            page = c.parse_output(c.target_json(gt["rows"]))
            self.assertEqual(len(page["rows"]), len(gt["rows"]), stem)


if __name__ == "__main__":
    unittest.main()
