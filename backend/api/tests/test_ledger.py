from datetime import date, timedelta
from decimal import Decimal as D

from django.test import SimpleTestCase

from api.ledger import Item, balance, bucket_for_age, compute_aging, running_balances

TODAY = date(2026, 10, 15)


def ago(days):
    return TODAY - timedelta(days=days)


def credit(days, amt, struck=False):
    return Item(None if days is None else ago(days), "credit", D(amt), struck)


def pay(days, amt, struck=False):
    return Item(None if days is None else ago(days), "payment", D(amt), struck)


class BalanceTests(SimpleTestCase):
    def test_balance(self):
        self.assertEqual(balance([credit(5, 100), credit(3, 50), pay(1, 30)]), D(120))

    def test_struck_out_excluded(self):
        self.assertEqual(balance([credit(5, 100), credit(3, 999, struck=True),
                                  pay(1, 500, struck=True)]), D(100))

    def test_negative_and_empty(self):
        self.assertEqual(balance([credit(5, 10), pay(1, 25)]), D(-15))
        self.assertEqual(balance([]), D(0))

    def test_decimals_are_exact(self):
        self.assertEqual(balance([credit(1, "0.10"), credit(1, "0.20")]), D("0.30"))

    def test_running_balances(self):
        items = [credit(9, 100), credit(8, 50, struck=True), pay(7, 30), credit(6, 10)]
        self.assertEqual(running_balances(items), [D(100), D(100), D(70), D(80)])


class AgingTests(SimpleTestCase):
    def test_buckets_boundaries(self):
        self.assertEqual([bucket_for_age(a) for a in (-3, 0, 30, 31, 60, 61, 400)],
                         ["0-30", "0-30", "0-30", "31-60", "31-60", "61+", "61+"])

    def test_no_payments(self):
        a = compute_aging([credit(10, 100), credit(45, 200), credit(90, 300)], TODAY)
        self.assertEqual(a.buckets, {"0-30": D(100), "31-60": D(200), "61+": D(300), "unknown": D(0)})
        self.assertEqual(a.oldest_unpaid_days, 90)

    def test_fifo_partial_payment_hits_oldest_first(self):
        a = compute_aging([credit(90, 300), credit(45, 200), credit(10, 100), pay(1, 350)], TODAY)
        # 300 clears the 90-day credit, 50 more comes off the 45-day one.
        self.assertEqual(a.buckets["61+"], D(0))
        self.assertEqual(a.buckets["31-60"], D(150))
        self.assertEqual(a.buckets["0-30"], D(100))
        self.assertEqual(a.oldest_unpaid_days, 45)

    def test_fully_paid(self):
        a = compute_aging([credit(40, 100), pay(1, 100)], TODAY)
        self.assertEqual(a.total, D(0))
        self.assertIsNone(a.oldest_unpaid_days)

    def test_overpayment(self):
        a = compute_aging([credit(40, 100), pay(1, 250)], TODAY)
        self.assertEqual(a.total, D(0))
        self.assertIsNone(a.oldest_unpaid_days)

    def test_struck_out_excluded(self):
        a = compute_aging([credit(90, 300, struck=True), credit(10, 100),
                           pay(1, 999, struck=True)], TODAY)
        self.assertEqual(a.buckets["0-30"], D(100))
        self.assertEqual(a.total, D(100))

    def test_unknown_dates_go_last_and_bucket_separately(self):
        a = compute_aging([credit(None, 100), credit(40, 100), pay(1, 100)], TODAY)
        # payment clears the dated credit first; the undated one stays unpaid
        self.assertEqual(a.buckets["unknown"], D(100))
        self.assertEqual(a.buckets["31-60"], D(0))
        self.assertIsNone(a.oldest_unpaid_days)

    def test_total_matches_balance_when_owing(self):
        items = [credit(70, 120), credit(35, 80), credit(None, 40), credit(2, 60),
                 pay(5, 130), pay(None, 20)]
        self.assertEqual(compute_aging(items, TODAY).total, balance(items))

    def test_same_day_credits_keep_input_order(self):
        a = compute_aging([credit(10, 100), credit(10, 100), pay(1, 100)], TODAY)
        self.assertEqual(a.buckets["0-30"], D(100))

    def test_future_dated_credit_counts_as_zero_days(self):
        a = compute_aging([Item(TODAY + timedelta(days=3), "credit", D(50))], TODAY)
        self.assertEqual(a.buckets["0-30"], D(50))
        self.assertEqual(a.oldest_unpaid_days, 0)
