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
        wiz = (
            self.Wizard.with_user(self.userPM)
            .with_context(active_id=reg.id)
            .create({"department_ids": [(6, 0, [self.dept1.id])]})
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

    def test_exact_change_multiple_registers(self):
        """
        ``exact_change`` is computed per register, never accumulated across
        records. Reading two registers in a single compute pass must return
        each register's own total, not a running sum: a shared accumulator
        would leak one register's amount into the next one.
        """

        self.setUpCommon()
        reg1 = self.Register.create(
            {
                "name": "Register A",
                "date_start": self.start,
                "date_end": self.end,
                "currency_id": self.env.ref("base.USD").id,
            }
        )
        reg2 = self.Register.create(
            {
                "name": "Register B",
                "date_start": self.start,
                "date_end": self.end,
                "currency_id": self.env.ref("base.USD").id,
            }
        )
        self.env["hr.payroll.register.denominations"].create(
            [
                {"register_id": reg1.id, "denomination": 100, "denomination_qty": 2},
                {"register_id": reg1.id, "denomination": 5, "denomination_qty": 3},
                {"register_id": reg2.id, "denomination": 50, "denomination_qty": 1},
            ]
        )

        regs = reg1 | reg2
        regs.invalidate_recordset(["exact_change"])
        # mapped() triggers a single multi-record compute pass.
        self.assertEqual(regs.mapped("exact_change"), [215.0, 50.0])

    def test_set_denominations_clears_empty_register(self):
        """
        Re-calculating a register that no longer has any batches must clear
        the stale denomination rows and the net amount, not keep showing them.
        """

        reg = self.Register.create(
            {
                "name": "Empty Register",
                "date_start": self.start,
                "date_end": self.end,
                "currency_id": self.env.ref("base.USD").id,
            }
        )
        self.env["hr.payroll.register.denominations"].create(
            {"register_id": reg.id, "denomination": 100, "denomination_qty": 9}
        )
        self.assertTrue(reg.denomination_ids)

        reg.set_denominations()

        self.assertFalse(reg.denomination_ids)
        self.assertEqual(reg.exact_change, 0)

    def test_delete_runs_clears_denominations(self):
        """
        Removing every batch of a register must also drop its denomination
        rows, so the old cash totals are no longer displayed.
        """

        self.setUpCommon()
        reg = self.Register.create(
            {
                "name": "Register To Delete",
                "date_start": self.start,
                "date_end": self.end,
                "currency_id": self.env.ref("base.USD").id,
            }
        )
        self.env["hr.payslip.run"].create(
            {
                "name": "Batch A",
                "date_start": self.start.date(),
                "date_end": self.end.date(),
                "register_id": reg.id,
            }
        )
        self.env["hr.payroll.register.denominations"].create(
            {"register_id": reg.id, "denomination": 100, "denomination_qty": 9}
        )
        self.assertTrue(reg.run_ids)
        self.assertTrue(reg.denomination_ids)

        reg.action_delete_runs()

        self.assertFalse(reg.run_ids)
        self.assertFalse(reg.denomination_ids)
        self.assertEqual(reg.exact_change, 0)
