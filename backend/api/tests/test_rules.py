from django.test import TestCase

from api.models import Correction, Page
from api.rules import MAX_RULE_LENGTH, build_rules


class BuildRulesTests(TestCase):
    def setUp(self):
        self.page = Page.objects.create()

    def add(self, field, model, user, raw="x"):
        return Correction.objects.create(page=self.page, row_index=0, field=field,
                                         model_value=model, user_value=user, raw_text=raw)

    def test_empty(self):
        self.assertEqual(build_rules(), [])

    def test_name_rule_text(self):
        self.add("name", "Honish", "Harish")
        self.assertEqual(build_rules(), ['A name was read as "Honish" but was actually "Harish".'])

    def test_type_and_struck_rules(self):
        self.add("type", "credit", "payment")
        self.add("struck_out", "false", "true")
        rules = build_rules()
        self.assertTrue(any(r.startswith("A payment row was read as credit.") for r in rules))
        self.assertTrue(any("crossed-out row was missed" in r for r in rules))

    def test_trivial_differences_skipped(self):
        self.add("name", "Ramesh ", "ramesh")
        self.add("date", "12/10", " 12/10")
        self.assertEqual(build_rules(), [])

    def test_dedupe(self):
        for _ in range(3):
            self.add("struck_out", "false", "true")
        self.assertEqual(len(build_rules()), 1)

    def test_limit_uses_most_recent_only(self):
        self.add("name", "Old", "Older")          # oldest: should fall outside the window
        for i in range(5):
            self.add("name", f"Wrong{i}", f"Right{i}")
        rules = build_rules(limit=5)
        self.assertEqual(len(rules), 5)
        self.assertFalse(any("Older" in r for r in rules))
        self.assertIn('A name was read as "Wrong4" but was actually "Right4".', rules)  # newest first

    def test_no_amounts_or_item_text_leak(self):
        self.add("amount", "240", "250", raw="01/10 Ramesh atta 240")
        self.add("item", "atta", "aata")
        rules = build_rules()
        self.assertEqual(len(rules), 1)
        self.assertNotIn("240", rules[0])
        self.assertNotIn("250", rules[0])

    def test_rule_length_and_quote_cleanup(self):
        self.add("name", 'A"' * 60, "B" * 100)
        rule = build_rules()[0]
        self.assertLessEqual(len(rule), MAX_RULE_LENGTH)
        self.assertNotIn('""', rule)
