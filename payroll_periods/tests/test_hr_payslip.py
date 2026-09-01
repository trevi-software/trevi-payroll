# Copyright (C) 2021 Trevi Software (https://trevi.et)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).


from odoo.addons.payroll.tests.common import TestPayslipBase


class TestPayslip(TestPayslipBase):
    def test_get_categories_dict(self):
        # I create an employee Payslip. Create it directly rather than through a
        # Form: payroll_account, when installed alongside, makes journal_id a
        # required field on the payslip form, and it is only ever filled in from
        # the contract.
        richard_payslip = self.Payslip.create({"employee_id": self.richard_emp.id})
        richard_payslip.onchange_employee()
        richard_payslip.compute_sheet()
        richard_payslip.write({"number": "SLIP/1000"})

        categories = richard_payslip.get_categories_dict()
        self.assertEqual(
            categories,
            {},
            "Salary rule categories dictionary is empty because "
            "no contracts have been approved yet",
        )
