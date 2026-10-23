# Copyright (C) 2022 Trevi Software (https://trevi.et)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo.addons.payroll.tests.common import TestPayslipBase


def get_payroll_dict_mock(*args, **kwargs):
    return {"mock": True}


def get_current_contract_dict_mock(*args, **kwargs):
    return {"my_mock_value": True}


class TestPayslip(TestPayslipBase):
    def setUp(self):
        super().setUp()

        self.Contract = self.env["hr.version"]
        self.HrPayslip = self.env["hr.payslip"]
        self.Rule = self.env["hr.salary.rule"]

        self.mock_rule = self.Rule.create(
            {
                "name": "Mock Salary Rule",
                "code": "MOCK",
                "sequence": 5,
                "category_id": self.categ_alw.id,
                "amount_select": "code",
                "amount_python_compute": (
                    "result = (payroll.mock is True) and 1.0 or 0.0"
                ),
            }
        )
        self.developer_pay_structure.write({"rule_ids": [(4, self.mock_rule.id)]})

        self.apply_contract_cron()

    def test_payroll_dict(self):
        # I create an employee Payslip
        richard_payslip = self.env["hr.payslip"].create(
            {"name": "Payslip of Richard", "employee_id": self.richard_emp.id}
        )

        # I patch the get_payroll_dict() method to return my own dictionary
        self.patch(type(richard_payslip), "get_payroll_dict", get_payroll_dict_mock)
        richard_payslip.compute_sheet()

        mock_payslip_line = False
        for line in richard_payslip.line_ids:
            if line.code == "MOCK":
                mock_payslip_line = line
        self.assertTrue(mock_payslip_line, "The mock payslip rule was processed")
        self.assertEqual(
            mock_payslip_line.amount, 1.0, "The mock payslip rule was evaluated"
        )

    def test_contractdict(self):
        self.mock_rule.amount_python_compute = (
            "result = (current_contract.my_mock_value is True) and 1.0 or 0.0"
        )

        # I create an employee Payslip
        richard_payslip = self.env["hr.payslip"].create(
            {"name": "Payslip of Richard", "employee_id": self.richard_emp.id}
        )

        # I patch the get_current_contract_dict() method to return my own
        # dictionary
        self.patch(
            type(richard_payslip),
            "get_current_contract_dict",
            get_current_contract_dict_mock,
        )
        richard_payslip.compute_sheet()

        mock_payslip_line = False
        for line in richard_payslip.line_ids:
            if line.code == "MOCK":
                mock_payslip_line = line
        self.assertTrue(
            mock_payslip_line, "The mock payslip contract rule was processed"
        )
        self.assertEqual(
            mock_payslip_line.amount,
            1.0,
            "The mock payslip contract rule was evaluated",
        )
