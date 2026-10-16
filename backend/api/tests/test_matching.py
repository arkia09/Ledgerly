from django.test import SimpleTestCase, override_settings

from api.matching import normalize_name, suggest_customer

CUSTOMERS = [(1, "Babulal"), (2, "Ramesh Kumar"), (3, "रमेश कुमार"), (4, "शकुंतला देवी")]


class MatchingTests(SimpleTestCase):
    def test_normalize(self):
        self.assertEqual(normalize_name("  RAMESH   kumar "), "ramesh kumar")
        self.assertEqual(normalize_name(None), "")

    def test_exact_match_is_100_ignoring_case_and_spacing(self):
        s = suggest_customer("  ramesh  KUMAR", CUSTOMERS)
        self.assertEqual((s["id"], s["score"]), (2, 100.0))

    def test_near_match_babula(self):
        s = suggest_customer("Babula", CUSTOMERS)
        self.assertEqual(s["id"], 1)
        self.assertGreaterEqual(s["score"], 85)
        self.assertLess(s["score"], 100)

    def test_devanagari_exact_and_near(self):
        self.assertEqual(suggest_customer("रमेश कुमार", CUSTOMERS)["score"], 100.0)
        near = suggest_customer("शकुंतला देव", CUSTOMERS)   # missing final vowel sign
        self.assertEqual(near["id"], 4)

    def test_below_threshold_returns_none(self):
        self.assertIsNone(suggest_customer("Sunita", CUSTOMERS))
        self.assertIsNone(suggest_customer("Ramesh", CUSTOMERS))  # 'Ramesh' vs 'Ramesh Kumar' < 85

    def test_empty_inputs(self):
        self.assertIsNone(suggest_customer("", CUSTOMERS))
        self.assertIsNone(suggest_customer(None, CUSTOMERS))
        self.assertIsNone(suggest_customer("Babulal", []))

    @override_settings(LEDGERLY_MATCH_THRESHOLD=95)
    def test_threshold_is_a_setting(self):
        self.assertIsNone(suggest_customer("Babula", CUSTOMERS))
