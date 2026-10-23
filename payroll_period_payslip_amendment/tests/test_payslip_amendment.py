# Copyright (C) 2022 Trevi Software (https://trevi.et)
# Copyright (C) 2013 Michael Telahun Makonnen <mmakonnen@gmail.com>.
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from datetime import date, datetime

from odoo import fields
from odoo.tests import Form, common


class TestPayslipAmendment(common.TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        cls.Period = cls.env["hr.payroll.period"]
        cls.Schedule = cls.env["hr.payroll.period.schedule"]
        cls.Run = cls.env["hr.payslip.run"]
        cls.Payslip = cls.env["hr.payslip"]
        cls.Amendment = cls.env["hr.payslip.amendment"]

        # A backdated version keeps the employee's "today" version from capping
        # the date_end of the versions the tests create.
        cls.eeSally = cls.env["hr.employee"].create(
            {"name": "Sally", "date_version": date(2000, 1, 1)}
        )

        cls.category_allowance = cls.env["hr.salary.rule.category"].create(
            {"name": "Allowance", "code": "ALW"}
        )
        cls.rule_commision = cls.env["hr.salary.rule"].create(
            {
                "name": "Commission",
                "code": "COMM",
                "category_id": cls.category_allowance.id,
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

    def create_payroll_schedule(self, stype=False, initial_date=False):
        return self.Schedule.create(
            {
                "name": "PPS",
                "tz": "Africa/Addis_Ababa",
                "type": stype,
                "initial_period_date": initial_date,
            }
        )

    def create_payroll_period(self, sched_id, start, end):
        return self.Period.create(
            {
                "name": "Period 1",
                "schedule_id": sched_id,
                "date_start": start,
                "date_end": end,
            }
        )

    def create_contract(
        self,
        eid,
        start=None,
        end=None,
        trial_end=None,
        pps_id=None,
    ):
        # hr_contract was merged into hr: a contract is now an hr.version.
        # state/kanban_state no longer exist; the version's dates and the
        # is_current/is_past/is_future computed flags express the same thing.
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
                "pps_id": pps_id,
            }
        )

    def test_amendment_in_period(self):
        # Create Payroll Period
        #
        start = datetime(2021, 1, 1)
        end = datetime(2021, 1, 31, 23, 59, 59)
        pps = self.create_payroll_schedule("manual", start.date())
        pp = self.create_payroll_period(pps.id, start, end)
        run = self.Run.create(
            {
                "name": "Run A",
                "date_start": start.date(),
                "date_end": end.date(),
                "period_id": pp.id,
            }
        )

        # Create Contract
        self.create_contract(self.eeSally.id, start.date(), end.date(), pps_id=pps.id)

        # Create Payslip Amendment
        psa = self.Amendment.create(
            {
                "employee_id": self.eeSally.id,
                "input_id": self.input_commision.id,
                "amount": 500,
                "period_id": pp.id,
            }
        )
        psa._onchange_period_id()
        psa.do_validate()

        # Create Payslip
        slip = pp.create_payslip(self.eeSally.id, run_id=run.id)

        input_lines = slip.input_line_ids.filtered(lambda self: self.code == "SALECOM")
        self.assertEqual(
            len(input_lines), 1, "There must be ONE payslip input line for SALECOM"
        )

        _res1 = fields.Float.compare(input_lines[0].amount, 500.0, precision_digits=2)
        self.assertEqual(_res1, 0, "The Input amount should be equal to 500.00")
        self.assertEqual(
            psa.state, "done", "The payslip amendment must be in 'done' state"
        )

    def test_amendment_not_in_period(self):
        # Create Payroll Period
        #
        start = datetime(2021, 1, 1)
        end = datetime(2021, 1, 31, 23, 59, 59)
        start2 = datetime(2021, 2, 1)
        end2 = datetime(2021, 2, 28, 23, 59, 59)
        pps = self.create_payroll_schedule("manual", start.date())
        pp = self.create_payroll_period(pps.id, start, end)
        pp2 = self.create_payroll_period(pps.id, start2, end2)
        run = self.Run.create(
            {
                "name": "Run A",
                "date_start": start.date(),
                "date_end": end.date(),
                "period_id": pp.id,
            }
        )

        # Create Contract
        self.create_contract(self.eeSally.id, start.date(), end.date(), pps_id=pps.id)

        # Create Payslip Amendment
        psa = self.Amendment.create(
            {
                "employee_id": self.eeSally.id,
                "input_id": self.input_commision.id,
                "amount": 500,
                "period_id": pp2.id,
            }
        )
        psa._onchange_period_id()
        psa.do_validate()

        # Create Payslip
        slip = pp.create_payslip(self.eeSally.id, run_id=run.id)

        input_lines = slip.input_line_ids.filtered(lambda self: self.code == "SALECOM")
        self.assertEqual(
            len(input_lines), 1, "There must be ONE payslip input line for SALECOM"
        )

        _res1 = fields.Float.compare(input_lines[0].amount, 0.0, precision_digits=2)
        self.assertEqual(_res1, 0, "The paylip amendment should NOT have been applied")

    def test_amendment_in_period2(self):
        """
        The amendment should be applied even when the employee contract is
        less than payroll period.
        """

        # Create Payroll Period
        #
        start = datetime(2021, 1, 1)
        end = datetime(2021, 1, 31, 23, 59, 59)
        cstart = datetime(2021, 1, 10)
        cend = datetime(2021, 1, 21, 23, 59, 59)
        pps = self.create_payroll_schedule("manual", start.date())
        pp = self.create_payroll_period(pps.id, start, end)
        run = self.Run.create(
            {
                "name": "Run A",
                "date_start": start.date(),
                "date_end": end.date(),
                "period_id": pp.id,
            }
        )

        # Create Contract
        self.create_contract(
            self.eeSally.id,
            cstart.date(),
            cend.date(),
            pps_id=pps.id,
        )

        # Create Payslip Amendment
        psa = self.Amendment.create(
            {
                "employee_id": self.eeSally.id,
                "input_id": self.input_commision.id,
                "amount": 500,
                "period_id": pp.id,
            }
        )
        psa._onchange_period_id()
        psa.do_validate()

        # Create Payslip
        slip = pp.create_payslip(self.eeSally.id, run_id=run.id)

        input_lines = slip.input_line_ids.filtered(lambda self: self.code == "SALECOM")
        self.assertEqual(
            len(input_lines), 1, "There must be ONE payslip input line for SALECOM"
        )

        _res1 = fields.Float.compare(input_lines[0].amount, 500.0, precision_digits=2)
        self.assertEqual(_res1, 0, "The Input amount should be equal to 500.00")
        self.assertEqual(
            psa.state, "done", "The payslip amendment must be in 'done' state"
        )

    def test_onchange_amendment(self):
        # Create Payroll Period
        #
        start = datetime(2021, 1, 1)
        end = datetime(2021, 1, 31, 23, 59, 59)
        pps = self.create_payroll_schedule("manual", start.date())
        pp = self.create_payroll_period(pps.id, start, end)

        # Create Contract
        self.create_contract(self.eeSally.id, start.date(), end.date(), pps_id=pps.id)

        # Create Payslip Amendment
        f = Form(self.Amendment)
        f.employee_id = self.eeSally
        f.input_id = self.input_commision
        f.amount = 10.00
        f.period_id = pp

        self.assertEqual(
            f.date,
            end.date(),
            "The date field is automatically set when the period is set",
        )

        f.save()

    def test_amendment_other_schedule_period(self):
        """
        The period used to widen the amendment date range must belong to the
        contract's payroll schedule. Several schedules can define overlapping
        periods; picking a period from another schedule would use the wrong
        dates and drop an amendment dated at the end of the real period.
        """

        start = datetime(2021, 1, 1)
        end = datetime(2021, 1, 31, 23, 59, 59)
        pps = self.create_payroll_schedule("manual", start.date())
        pp = self.create_payroll_period(pps.id, start, end)

        # A second schedule whose period overlaps the January monthly period
        # but starts earlier, so it is picked first when periods are not
        # filtered by schedule.
        pps_other = self.create_payroll_schedule(
            "manual", datetime(2020, 12, 16).date()
        )
        self.create_payroll_period(
            pps_other.id,
            datetime(2020, 12, 16),
            datetime(2021, 1, 15, 23, 59, 59),
        )

        run = self.Run.create(
            {
                "name": "Run A",
                "date_start": start.date(),
                "date_end": end.date(),
                "period_id": pp.id,
            }
        )

        # The contract belongs to the January monthly schedule only.
        self.create_contract(self.eeSally.id, start.date(), end.date(), pps_id=pps.id)

        # Amendment dated at the end of the January period.
        psa = self.Amendment.create(
            {
                "employee_id": self.eeSally.id,
                "input_id": self.input_commision.id,
                "amount": 500,
                "period_id": pp.id,
            }
        )
        psa._onchange_period_id()
        psa.do_validate()
        self.assertEqual(psa.date, end.date())

        slip = pp.create_payslip(self.eeSally.id, run_id=run.id)

        input_lines = slip.input_line_ids.filtered(lambda self: self.code == "SALECOM")
        self.assertEqual(
            len(input_lines), 1, "There must be ONE payslip input line for SALECOM"
        )

        _res1 = fields.Float.compare(input_lines[0].amount, 500.0, precision_digits=2)
        self.assertEqual(
            _res1,
            0,
            "The amendment must use the contract's schedule period, not another "
            "schedule's overlapping period",
        )
        self.assertEqual(
            psa.state, "done", "The payslip amendment must be in 'done' state"
        )
