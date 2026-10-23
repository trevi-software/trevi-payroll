# Copyright (C) 2021 Trevi Software (https://trevi.et)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from datetime import datetime

from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import common, new_test_user


class TestPayrollRegister(common.TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        cls.Wizard = cls.env["hr.payroll.register.run"]
        cls.Register = cls.env["hr.payroll.register"]

        cls.start = datetime(2021, 1, 1)
        cls.end = datetime(2021, 1, 31)
        cls.dept1 = cls.env["hr.department"].create({"name": "Dept A"})
        cls.job = cls.env["hr.job"].create(
            {"name": "Test Job", "department_id": cls.dept1.id}
        )
        cls.eeJohn = cls.env["hr.employee"].create(
            {
                "name": "John Smith",
                "department_id": cls.dept1.id,
                "job_id": cls.job.id,
            }
        )
        # Demo data is not installed in Odoo 19, so build the salary
        # structure the contract needs: a single NET rule paying the wage.
        cls.pay_struct = cls.env["hr.payroll.structure"].create(
            {"name": "Test Structure", "code": "TEST"}
        )
        net_rule = cls.env["hr.salary.rule"].create(
            {
                "name": "Net Salary",
                "code": "NET",
                "sequence": 100,
                "condition_select": "none",
                "amount_select": "code",
                "amount_python_compute": "result = contract.wage",
            }
        )
        cls.pay_struct.write({"rule_ids": [(6, 0, [net_rule.id])]})
        # Payroll Manager user
        cls.userPM = new_test_user(
            cls.env,
            login="hel",
            groups="base.group_user,payroll.group_payroll_manager",
            name="Payroll manager",
            email="ric@example.com",
        )

    def create_contract(self, eid, start, end=None, trial_end=None):
        # hr.contract is gone in Odoo 19: a contract is now an hr.version.
        # The employee already owns a version dated today, so the new one is
        # pinned to its own (backdated) date_version to avoid the unique
        # (employee_id, date_version) index.
        return self.env["hr.version"].create(
            {
                "employee_id": eid,
                "job_id": self.job.id,
                "department_id": self.dept1.id,
                "date_version": start,
                "contract_date_start": start,
                "contract_date_end": end,
                "wage": 989.92,
                "trial_date_end": trial_end,
                "struct_id": self.pay_struct.id,
            }
        )

    def check_denominations(self, reg, d):
        for den in reg.denomination_ids:
            key = fields.Float.round(den.denomination, 2)
            self.assertEqual(
                0,
                fields.Float.compare(d[key], den.denomination_qty, 2),
                f"Denomination key: {key}",
            )

    def setUpCommon(self):
        self.create_contract(self.eeJohn.id, self.start.date())

    def test_no_active_id(self):
        """If 'active_id' is not in the context raise an error"""

        self.setUpCommon()
        wiz = self.Wizard.create({"department_ids": [(6, 0, [self.dept1.id])]})
        with self.assertRaises(ValidationError):
            wiz.create_payslip_runs()

    def test_no_departments(self):
        """If no departments were selected raise an error"""

        self.setUpCommon()
        reg = self.Register.create(
            {
                "date_start": self.start,
                "date_end": self.end,
            }
        )
        wiz = self.Wizard.with_context(active_id=reg.id).create({})
        with self.assertRaises(UserError):
            wiz.create_payslip_runs()

    def test_payroll_register_wizard(self):
        """
        Running the wizard with one department should create a payroll
        register containing a payslip run for that department.
        """

        self.setUpCommon()
        reg = self.Register.with_user(self.userPM).create(
            {
                "date_start": self.start,
                "date_end": self.end,
            }
        )
        wiz = self.Wizard.with_context(active_id=reg.id).create(
            {"department_ids": [(6, 0, [self.dept1.id])]}
        )
        wiz.create_payslip_runs()

        self.assertEqual(1, len(reg.run_ids))
        self.assertEqual(self.dept1.complete_name, reg.run_ids[0].name)

    def test_payroll_register_denominations(self):
        """When the wizard is run it should also create the denominations"""

        self.setUpCommon()
        reg = self.Register.create(
            {
                "date_start": self.start,
                "date_end": self.end,
                "currency_id": self.env.ref("base.USD").id,
            }
        )
        wiz = self.Wizard.with_context(active_id=reg.id).create(
            {"department_ids": [(6, 0, [self.dept1.id])]}
        )
        wiz.create_payslip_runs()

        res = {
            0.01: 2,
            0.05: 1,
            0.10: 1,
            0.25: 1,
            0.50: 1,
            1: 4,
            5: 1,
            10: 1,
            20: 1,
            50: 1,
            100: 9,
        }
        self.assertGreater(len(reg.denomination_ids), 0)
        self.check_denominations(reg, res)
