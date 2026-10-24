# Copyright (C) 2022 Trevi Software (https://trevi.et)
# Copyright (C) 2013 Michael Telahun Makonnen <mmakonnen@gmail.com>.
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from datetime import date

from dateutil.relativedelta import relativedelta

from odoo import fields
from odoo.tests import common


class TestPayslipAmendment(common.TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        cls.Payslip = cls.env["hr.payslip"]
        cls.Amendment = cls.env["hr.payslip.amendment"]

        # A backdated version keeps the employee's "today" version from capping
        # the date_end of the versions created by the tests.
        cls.eeSally = cls.env["hr.employee"].create(
            {"name": "Sally", "date_version": date(2000, 1, 1)}
        )

        cls.rule_commision = cls.env["hr.salary.rule"].create(
            {
                "name": "Commission",
                "code": "COMM",
                "category_id": cls.env["hr.salary.rule.category"]
                .create({"name": "Allowance", "code": "ALW"})
                .id,
                "sequence": 17,
                "amount_select": "code",
                "amount_python_compute": "result = inputs.SALECOM.amount",
            }
        )
        cls.input_commision = cls.env["hr.rule.input"].create(
            {
                "name": "Sales Commission Input",
                "code": "SALECOM",
                "input_id": cls.rule_commision.id,
            }
        )

        cls.pay_struct = cls.env["hr.payroll.structure"].create(
            {"name": "Test Structure", "code": "TEST"}
        )
        cls.pay_struct.write({"rule_ids": [(4, cls.rule_commision.id)]})

    def create_contract(self, eid, start=None, end=None, trial_end=None):
        """Create an employee contract.

        In Odoo 19 ``hr_contract`` was merged into ``hr``: an ``hr.contract``
        is now an ``hr.version``. The old ``state`` / ``kanban_state`` state
        machine has no equivalent, so a contract is described by its
        ``contract_date_start`` / ``contract_date_end`` dates alone.
        """
        if start is None:
            start = date.today()
        return self.env["hr.version"].create(
            {
                "name": "Contract",
                "employee_id": eid,
                "wage": 1,
                "date_version": start,
                "contract_date_start": start,
                "trial_date_end": trial_end,
                "contract_date_end": end,
                "struct_id": self.pay_struct.id,
            }
        )

    def test_done_2_contracts(self):
        # Setup test
        #
        dstart = date(2021, 1, 1)
        dend = date(2021, 1, 31)
        dpsa = date(2021, 1, 1)
        cc1 = self.create_contract(
            self.eeSally.id, dstart, dstart + relativedelta(days=10)
        )
        cc2 = self.create_contract(self.eeSally.id, dstart + relativedelta(days=11))
        self.assertIn(self.rule_commision, cc1.struct_id.rule_ids)
        self.assertIn(self.rule_commision, cc2.struct_id.rule_ids)
        psa = self.Amendment.create(
            {
                "employee_id": self.eeSally.id,
                "input_id": self.input_commision.id,
                "amount": 50,
                "date": dpsa,
            }
        )
        psa.do_validate()

        # Create payslip. The structure is set up-front and contract_id is
        # deliberately left empty: payroll's onchange_employee() pins the
        # payslip to a single contract, and _get_employee_contracts() then
        # reports only that one, which hides the consecutive contracts the
        # employee owns.
        slip = self.Payslip.create(
            {
                "name": "A Payslip",
                "employee_id": self.eeSally.id,
                "date_from": dstart,
                "date_to": dend,
                "struct_id": self.pay_struct.id,
            }
        )
        slip.onchange_struct_id()

        input_lines = slip.input_line_ids.filtered(lambda self: self.code == "SALECOM")
        self.assertEqual(
            len(input_lines), 2, "There must be TWO payslip input lines for SALECOM"
        )

        _res1 = fields.Float.compare(input_lines[0].amount, 25.0, precision_digits=2)
        _res2 = fields.Float.compare(input_lines[1].amount, 25.0, precision_digits=2)
        self.assertEqual(
            _res1, 0, "The Input amount should be equal to HALF the payslip amendment"
        )
        self.assertEqual(
            fields.Float.compare(_res1, _res2, precision_digits=2),
            0,
            "The Input amounts should be equal to each other",
        )
        self.assertEqual(
            psa.state, "done", "The payslip amendment must be in 'done' state"
        )
