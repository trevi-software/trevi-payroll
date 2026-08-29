# Copyright (C) 2025 Trevi Software (https://trevi.et)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from psycopg2 import IntegrityError

from odoo.tests.common import TransactionCase


class TestPayrollSalaryCode(TransactionCase):
    def setUp(self):
        super().setUp()
        self.SalaryCode = self.env["payroll.salary.code"]

    def test_create_code(self):
        """A salary code can be created with code and description."""
        rec = self.SalaryCode.create(
            {
                "code": "TRA",
                "description": "Transport allowance",
            }
        )
        self.assertEqual(rec.code, "TRA")
        self.assertEqual(rec.description, "Transport allowance")

    def test_code_length_not_constrained(self):
        """Codes of any length are accepted (no 3-character constraint)."""
        for code in ("A", "AB", "ABCD", "LONGCODE12"):
            rec = self.SalaryCode.create({"code": code})
            self.assertEqual(rec.code, code)

    def test_code_required(self):
        """Creating a record without a code raises an error."""
        with self.assertRaises(Exception):  # noqa: B017
            self.SalaryCode.create({"description": "no code"})

    def test_code_unique(self):
        """Duplicate codes are rejected by the unique constraint."""
        self.SalaryCode.create({"code": "DUP"})
        with self.cr.savepoint():
            with self.assertRaises(IntegrityError):
                self.SalaryCode.create({"code": "DUP"})
                self.env.cr.flush()

    def test_order_by_code(self):
        """Records are ordered by code."""
        codes = ["ZZZ", "AAA", "MMM"]
        for code in codes:
            self.SalaryCode.create({"code": code})
        self.assertEqual(
            self.SalaryCode.search([("code", "in", codes)]).mapped("code"),
            ["AAA", "MMM", "ZZZ"],
        )
