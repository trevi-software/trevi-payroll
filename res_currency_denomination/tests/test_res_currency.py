# Copyright (C) 2021 Trevi Software (https://trevi.et)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestResCurrencyDenomination(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.usd = cls.env.ref("base.USD")
        cls.eur = cls.env.ref("base.EUR")

    def _total(self, breakdown):
        return sum(item["qty"] * item["name"] for item in breakdown)

    def test_get_denominations_from_amount_whole_quantities(self):
        """Coin/note quantities must be whole numbers and must not overshoot.

        Regression test: ``get_denominations_from_amount(0.75)`` used to return
        1.5 half-dollar coins plus a quarter, i.e. a breakdown worth 1.00 for a
        0.75 request (fractional coin counts were added to the remainder).
        """
        breakdown = self.usd.get_denominations_from_amount(0.75)
        for item in breakdown:
            self.assertEqual(
                item["qty"],
                int(item["qty"]),
                "Denomination quantity must be a whole number: %s" % item,
            )
        self.assertAlmostEqual(
            self._total(breakdown),
            0.75,
            2,
            "Breakdown must not be worth more than the requested amount",
        )

    def test_get_denominations_from_amount_totals(self):
        """The breakdown must always add up to the requested amount."""
        for amount in (0.01, 0.25, 0.5, 0.75, 0.99, 1.0, 2.75, 137.63):
            breakdown = self.usd.get_denominations_from_amount(amount)
            self.assertAlmostEqual(
                self._total(breakdown),
                amount,
                2,
                "Breakdown for %s must sum back to the amount" % amount,
            )

    def test_zero_value_denomination_is_rejected(self):
        """A zero (or negative) denomination value must not be saved.

        Regression test: a zero ``value`` made ``get_denominations_from_amount``
        hit a division by zero when building the cash breakdown.
        """
        with self.assertRaises(ValidationError):
            self.env["res.currency.denomination"].create(
                {"currency_id": self.usd.id, "value": 0.0, "ratio": 0.0}
            )
        with self.assertRaises(ValidationError):
            self.env["res.currency.denomination"].create(
                {"currency_id": self.usd.id, "value": -1.0, "ratio": -1.0}
            )

    def test_euro_50_cent_denomination_belongs_to_eur(self):
        """The euro 50-cent coin must be attached to the EUR currency."""
        denom = self.env.ref("res_currency_denomination.50eucent")
        self.assertEqual(denom.currency_id, self.eur)
        self.assertAlmostEqual(denom.value, 0.50, 6)
