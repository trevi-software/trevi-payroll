# Copyright (C) 2021 TREVI Software
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from datetime import date, datetime, timedelta

from dateutil.relativedelta import relativedelta

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import common


class TestAccrualPolicy(common.TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        cls.PolicyGroup = cls.env["hr.policy.group"]
        cls.Policy = cls.env["hr.policy.accrual"]
        cls.PolicyLine = cls.env["hr.policy.line.accrual"]
        cls.AccrualJob = cls.env["hr.policy.line.accrual.job"]
        cls.Accrual = cls.env["hr.accrual"]
        cls.Employee = cls.env["hr.employee"]
        cls.LeaveType = cls.env["hr.leave.type"]
        cls.LeaveAlloction = cls.env["hr.leave.allocation"]

    def create_employee(self, name):
        """Create an employee with a back-dated initial version.

        In Odoo 19 an employee always owns an ``hr.version`` dated today and
        the ``(employee_id, date_version)`` pair is unique, so the employee is
        created with a back-dated ``date_version``. That leaves the contract
        start date free for the version created by :meth:`create_contract`.
        """
        return self.Employee.create({"name": name, "date_version": "2000-01-01"})

    def create_contract(self, eid, start, end=None, trial_end=None):
        """Create the ``hr.version`` record that represents a contract.

        Odoo 19 merged ``hr_contract`` into ``hr``: a contract is an
        ``hr.version`` and its dates live in ``contract_date_start`` /
        ``contract_date_end``. The ``state``/``kanban_state`` selection is gone.
        """
        return self.env["hr.version"].create(
            {
                "name": "Contract",
                "employee_id": eid,
                "date_version": start,
                "contract_date_start": start,
                "wage": 1,
                "trial_date_end": trial_end,
                "contract_date_end": end,
            }
        )

    def apply_cron(self):
        # Odoo 19's ``ir.cron.method_direct_trigger()`` runs the job in its own
        # cursor/transaction, so the records created by the test are not
        # visible to it. Run the cron's server action instead: it executes the
        # very same code, in the current transaction.
        cron = self.env.ref("payroll_policy_accrual.hr_accrual_policy_cron")
        cron.ir_actions_server_id.run()

    def test_get_latest_policy(self):
        """Latest policy at given date should be returned"""

        pMarch = self.Policy.create({"name": "P1", "date": date(2020, 3, 1)})
        pDec = self.Policy.create({"name": "P1", "date": date(2020, 12, 1)})
        pJan = self.Policy.create({"name": "P1", "date": date(2020, 1, 1)})
        pg = self.PolicyGroup.create(
            {
                "name": "PGroup",
                "accr_policy_ids": [(6, 0, [pMarch.id, pDec.id, pJan.id])],
            }
        )
        ap = self.Policy.get_latest_policy(pg, date.today())

        self.assertEqual(pDec, ap)

    def test_get_latest_policy_with_future(self):
        """Latest policy must not be in the future"""

        pastDate = date.today() - relativedelta(days=5)
        futureDate = date.today() + relativedelta(days=1)
        pFuture = self.Policy.create({"name": "PF", "date": futureDate})
        pPast = self.Policy.create({"name": "PP", "date": pastDate})
        pg = self.PolicyGroup.create(
            {
                "name": "PGroup",
                "accr_policy_ids": [(6, 0, [pFuture.id, pPast.id])],
            }
        )
        ap = self.Policy.get_latest_policy(pg, date.today())

        self.assertEqual(pPast, ap)

    def test_constraint_employed_days(self):
        """Verify correctly wheter an employee falls within employed days constraint"""

        # Setup Employee past minimum days
        start = date.today() - timedelta(days=100)
        ee = self.create_employee("John")
        self.create_contract(ee.id, start)
        # Setup Employee still in minimum days
        start = date.today()
        ee2 = self.create_employee("Paul")
        self.create_contract(ee2.id, start)

        # Create policy with minimum employed days = 30
        aa = self.Accrual.create({"name": "ACCR"})
        line = self.PolicyLine.create(
            {
                "name": "A",
                "code": "A",
                "accrual_id": aa.id,
                "type": "standard",
                "minimum_employed_days": 30,
            }
        )

        # past min. days
        self.assertTrue(line.pass_constraints(ee))
        # still hasn't completed min days
        self.assertFalse(line.pass_constraints(ee2))

    def test_annual_accrual(self):
        """Accrual created for employee after first month"""

        # Setup Employee
        start = date.today() - relativedelta(months=1)
        dLastRun = date.today() - relativedelta(days=4)
        dtLastRun = datetime.combine(dLastRun, datetime.min.time())
        ee = self.create_employee("John")
        cc = self.create_contract(ee.id, start)

        # Create policy that accrues 24 days/year
        # hr_leave_type_unique (pulled in via trevi-hr deps in CI) adds a
        # required 'code' field on hr.leave.type
        lt_vals = {"name": "Leave type"}
        if "code" in self.LeaveType._fields:
            lt_vals["code"] = "LT"
        lt = self.LeaveType.create(lt_vals)
        aa = self.Accrual.create({"name": "24 ANNUAL ACCR", "holiday_status_id": lt.id})
        policy = self.Policy.create(
            {
                "name": "Annual leave",
                "date": date.today(),
            }
        )
        pl = self.PolicyLine.create(
            {
                "name": "Fixed",
                "code": "FIX",
                "accrual_id": aa.id,
                "policy_id": policy.id,
                "calculation_frequency": "monthly",
                "frequency_on_hire_date": True,
                "accrual_rate": 24,
            }
        )
        pg = self.PolicyGroup.create(
            {"name": "PG", "accr_policy_ids": [(6, 0, [policy.id])]}
        )
        cc.policy_group_id = pg.id

        self.AccrualJob.create(
            {"name": dLastRun, "execution_time": dtLastRun, "policy_line_id": pl.id}
        )
        self.assertEqual(0, len(aa.line_ids))

        self.apply_cron()

        self.assertEqual(1, len(aa.line_ids))
        self.assertEqual(date.today(), aa.line_ids[0].date)
        self.assertEqual(ee, aa.line_ids[0].employee_id)
        self.assertEqual(
            0, fields.Float.compare(aa.line_ids[0].amount, 2.0, precision_digits=2)
        )
        lva = self.LeaveAlloction.search(
            [("employee_id", "=", ee.id), ("from_accrual", "=", True)]
        )
        self.assertEqual(1, len(lva))
        self.assertEqual(
            0,
            fields.Float.compare(
                aa.line_ids[0].amount, lva[0].number_of_days, precision_digits=2
            ),
        )
        job = pl.job_ids.filtered(lambda j: j.name == start + relativedelta(months=1))
        self.assertEqual(5, len(pl.job_ids))
        self.assertEqual(1, len(job.accrual_line_ids))
        self.assertEqual(1, len(job.holiday_ids))
        self.assertEqual(job.holiday_ids[0], lva[0])
        self.assertIn(job.holiday_ids[0].state, ["validate", "validate1"])
        self.assertTrue(job.execution_time)
        self.assertTrue(job.end_time)
        self.assertGreater(job.end_time, pl.job_ids[0].execution_time)

    def test_weekly_selected_week_day(self):
        """A weekly rule selected by day of week must match that day.

        The selection value is stored (and returned) as a string while
        ``date.weekday()`` is an integer, so the comparison used to never
        match and weekly rules never accrued.
        """

        start = date.today() - timedelta(days=100)
        ee = self.create_employee("Weekly")
        self.create_contract(ee.id, start)
        aa = self.Accrual.create({"name": "W"})
        line = self.PolicyLine.create(
            {
                "name": "W",
                "code": "W",
                "accrual_id": aa.id,
                "type": "calendar",
                "calculation_frequency": "weekly",
                "frequency_week_day": str(date.today().weekday()),
                "accrual_rate": 52,
            }
        )

        self.assertAlmostEqual(1.0, line.do_calculation(ee, date.today()), places=5)
        # the previous day has a different weekday -> no accrual
        self.assertIs(False, line.do_calculation(ee, date.today() - timedelta(days=1)))

    def test_monthly_selected_month_day(self):
        """A monthly rule must match its selected day, including month end.

        On the last day of a 30 day month a rule set to the 31st must fall
        back to the 30th instead of raising ``TypeError`` on ``str > int``.
        """

        ee = self.create_employee("Monthly")
        self.create_contract(ee.id, date(2020, 1, 1))
        aa = self.Accrual.create({"name": "M"})
        line = self.PolicyLine.create(
            {
                "name": "M",
                "code": "M",
                "accrual_id": aa.id,
                "type": "calendar",
                "calculation_frequency": "monthly",
                "frequency_month_day": "31",
                "accrual_rate": 12,
            }
        )

        # 2023-04-30 is the last day of a 30 day month
        self.assertAlmostEqual(
            1.0, line.do_calculation(ee, date(2023, 4, 30)), places=5
        )
        # neither the selected day nor month end
        self.assertIs(False, line.do_calculation(ee, date(2023, 4, 29)))

    def test_annual_requires_month_and_day(self):
        """An annual rule pays only when month *and* day both match."""

        ee = self.create_employee("Annual")
        self.create_contract(ee.id, date(2020, 1, 1))
        aa = self.Accrual.create({"name": "A"})
        line = self.PolicyLine.create(
            {
                "name": "A",
                "code": "A",
                "accrual_id": aa.id,
                "type": "calendar",
                "calculation_frequency": "annual",
                "frequency_annual_month": "6",
                "frequency_annual_day": "15",
                "accrual_rate": 24,
            }
        )

        self.assertAlmostEqual(
            24.0, line.do_calculation(ee, date(2023, 6, 15)), places=5
        )
        # matching month, different day
        self.assertIs(False, line.do_calculation(ee, date(2023, 6, 16)))
        # matching day, different month
        self.assertIs(False, line.do_calculation(ee, date(2023, 7, 15)))

    def test_leap_february_monthly_hire_date(self):
        """A monthly hire-date rule must not skip February in a leap year."""

        ee = self.create_employee("Leap")
        self.create_contract(ee.id, date(2020, 1, 31))
        aa = self.Accrual.create({"name": "L"})
        line = self.PolicyLine.create(
            {
                "name": "L",
                "code": "L",
                "accrual_id": aa.id,
                "type": "calendar",
                "calculation_frequency": "monthly",
                "frequency_on_hire_date": True,
                "accrual_rate": 12,
            }
        )

        # leap year: the accrual falls on the 29th
        self.assertAlmostEqual(
            1.0, line.do_calculation(ee, date(2024, 2, 29)), places=5
        )
        self.assertIs(False, line.do_calculation(ee, date(2024, 2, 28)))
        # non leap year: the accrual falls on the 28th
        self.assertAlmostEqual(
            1.0, line.do_calculation(ee, date(2023, 2, 28)), places=5
        )
        self.assertIs(False, line.do_calculation(ee, date(2023, 2, 27)))

    def test_premium_default_milestone_does_not_crash(self):
        """The default (zero) premium milestone must not stop the job."""

        ee = self.create_employee("Premium")
        self.create_contract(ee.id, date(2020, 1, 1))
        aa = self.Accrual.create({"name": "P"})
        line = self.PolicyLine.create(
            {
                "name": "P",
                "code": "P",
                "accrual_id": aa.id,
                "type": "calendar",
                "calculation_frequency": "monthly",
                "frequency_month_day": "1",
                "accrual_rate": 12,
            }
        )

        # the employee has more than the default 12 months of service and the
        # default premium milestone is 0: the premium must be zero rather than
        # a ZeroDivisionError.
        self.assertAlmostEqual(1.0, line.do_calculation(ee, date(2023, 1, 1)), places=5)

    def test_premium_with_milestone(self):
        """A configured premium is still applied."""

        ee = self.create_employee("Premium2")
        self.create_contract(ee.id, date(2020, 1, 1))
        aa = self.Accrual.create({"name": "P2"})
        line = self.PolicyLine.create(
            {
                "name": "P2",
                "code": "P2",
                "accrual_id": aa.id,
                "type": "calendar",
                "calculation_frequency": "monthly",
                "frequency_month_day": "1",
                "accrual_rate": 12,
                "accrual_rate_premium": 6,
                "accrual_rate_premium_minimum": 12,
                "accrual_rate_premium_milestone": 12,
            }
        )

        # 36 months of service: (36 - 12 + 12) // 12 * 6 / 12 = 1.5
        self.assertAlmostEqual(2.5, line.do_calculation(ee, date(2023, 1, 1)), places=5)

    def test_premium_milestone_constraint(self):
        """A premium rate without a positive milestone is rejected."""

        aa = self.Accrual.create({"name": "P3"})
        with self.assertRaises(ValidationError):
            self.PolicyLine.create(
                {
                    "name": "P3",
                    "code": "P3",
                    "accrual_id": aa.id,
                    "type": "calendar",
                    "accrual_rate_premium": 6,
                    "accrual_rate_premium_milestone": 0,
                }
            )

    def test_catch_up_deposit_uses_missed_date(self):
        """A catch-up accrual is deposited on the date it is calculated for."""

        ee = self.create_employee("CatchUp")
        self.create_contract(ee.id, date(2020, 1, 31))
        aa = self.Accrual.create({"name": "CU"})
        line = self.PolicyLine.create(
            {
                "name": "CU",
                "code": "CU",
                "accrual_id": aa.id,
                "type": "calendar",
                "calculation_frequency": "monthly",
                "frequency_on_hire_date": True,
                "accrual_rate": 12,
            }
        )

        dJob = date(2023, 1, 31)
        line.calculate_and_deposit(ee, d_today=dJob)

        self.assertEqual(1, len(aa.line_ids))
        self.assertEqual(dJob, aa.line_ids[0].date)

    def test_shared_policy_across_groups(self):
        """Two policy groups sharing a policy both receive accruals."""

        today = date.today()
        start = date(today.year - 1, today.month, today.day)

        ee1 = self.create_employee("Shared1")
        c1 = self.create_contract(ee1.id, start)
        ee2 = self.create_employee("Shared2")
        c2 = self.create_contract(ee2.id, start)

        aa = self.Accrual.create({"name": "SHARED"})
        lt_vals = {"name": "Shared leave type"}
        if "code" in self.LeaveType._fields:
            lt_vals["code"] = "SLT"
        lt = self.LeaveType.create(lt_vals)
        aa.holiday_status_id = lt.id
        policy = self.Policy.create({"name": "Shared", "date": start})
        self.PolicyLine.create(
            {
                "name": "S",
                "code": "S",
                "accrual_id": aa.id,
                "policy_id": policy.id,
                "type": "calendar",
                "calculation_frequency": "monthly",
                "frequency_on_hire_date": True,
                "accrual_rate": 12,
            }
        )
        pg1 = self.PolicyGroup.create(
            {"name": "PG1", "accr_policy_ids": [(6, 0, [policy.id])]}
        )
        pg2 = self.PolicyGroup.create(
            {"name": "PG2", "accr_policy_ids": [(6, 0, [policy.id])]}
        )
        c1.policy_group_id = pg1.id
        c2.policy_group_id = pg2.id

        self.apply_cron()

        self.assertEqual(2, len(aa.line_ids))
        self.assertEqual({ee1.id, ee2.id}, set(aa.line_ids.mapped("employee_id").ids))
