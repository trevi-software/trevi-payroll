# Copyright (C) 2021 TREVI Software
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from datetime import date, datetime, timedelta

from dateutil.relativedelta import relativedelta

from odoo import fields
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
