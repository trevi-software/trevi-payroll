# Copyright (C) 2021 Trevi Software (https://trevi.et)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from datetime import date

from odoo.addons.payroll.tests.common import TestPayslipBase


class TestPayslip(TestPayslipBase):
    def test_get_categories_dict(self):
        # I create an employee Payslip. Create it directly rather than through a
        # Form: payroll_account, when installed alongside, makes journal_id a
        # required field on the payslip form, and it is only ever filled in from
        # the contract.
        #
        # Odoo 19: hr.contract is gone and a contract is now an hr.version
        # carrying contract dates - there is no draft/approved contract state
        # any more. The "no approved contract" case is therefore an employee
        # whose version carries no contract dates at all.
        emp_no_contract = self.env["hr.employee"].create(
            {"name": "No Contract", "date_version": date(2000, 1, 1)}
        )
        no_contract_payslip = self.Payslip.create({"employee_id": emp_no_contract.id})
        no_contract_payslip.onchange_employee()
        no_contract_payslip.compute_sheet()
        no_contract_payslip.write({"number": "SLIP/1000"})

        categories = no_contract_payslip.get_categories_dict()
        self.assertEqual(
            categories,
            {},
            "Salary rule categories dictionary is empty because "
            "no contracts have been approved yet",
        )
