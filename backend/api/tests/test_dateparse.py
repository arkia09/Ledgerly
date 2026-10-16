from datetime import date

from django.test import SimpleTestCase

from api.dateparse import parse_date_text

TODAY = date(2026, 10, 15)


class ParseDateTests(SimpleTestCase):
    def test_numeric_formats_are_day_first(self):
        for text, want in [("12/10", date(2026, 10, 12)), ("12-10", date(2026, 10, 12)),
                           ("12.10", date(2026, 10, 12)), ("21/9", date(2026, 9, 21)),
                           ("01/10", date(2026, 10, 1)), (" 12 / 10 ", date(2026, 10, 12))]:
            with self.subTest(text):
                self.assertEqual(parse_date_text(text, TODAY), want)

    def test_month_names(self):
        for text in ["21 Sep", "21 September", "Sep 21", "sep 21", "21st Sep", "21Sep",
                     "21 Sept", "September 21", "21 SEP"]:
            with self.subTest(text):
                self.assertEqual(parse_date_text(text, TODAY), date(2026, 9, 21))

    def test_devanagari_digits(self):
        self.assertEqual(parse_date_text("२१/९", TODAY), date(2026, 9, 21))

    def test_explicit_year(self):
        self.assertEqual(parse_date_text("21/09/2025", TODAY), date(2025, 9, 21))
        self.assertEqual(parse_date_text("21/9/25", TODAY), date(2025, 9, 21))
        self.assertEqual(parse_date_text("2025-09-21", TODAY), date(2025, 9, 21))
        self.assertEqual(parse_date_text("21 Sep 2025", TODAY), date(2025, 9, 21))

    def test_failures_return_none(self):
        for text in [None, "", "  ", "abc", "32/10", "12/13", "31/4", "0/10", "21 Foo",
                     "Sep 2026", "1/2/3", "10/21"]:
            with self.subTest(text):
                self.assertIsNone(parse_date_text(text, TODAY))

    def test_year_rollover(self):
        jan3 = date(2026, 1, 3)
        self.assertEqual(parse_date_text("30/12", jan3), date(2025, 12, 30))  # far future -> last year
        self.assertEqual(parse_date_text("05/01", jan3), date(2026, 1, 5))    # 2 days ahead is fine
        self.assertEqual(parse_date_text("10/01", jan3), date(2026, 1, 10))   # exactly 7 days ahead
        self.assertEqual(parse_date_text("11/01", jan3), date(2025, 1, 11))   # 8 days ahead -> last year

    def test_leap_day(self):
        self.assertEqual(parse_date_text("29/02", date(2028, 3, 1)), date(2028, 2, 29))
        self.assertIsNone(parse_date_text("29/02", date(2026, 3, 1)))
