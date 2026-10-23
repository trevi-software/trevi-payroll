# Copyright (C) 2021 Trevi Software (https://trevi.et)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from datetime import date, datetime

from dateutil.relativedelta import relativedelta
from pytz import timezone, utc

from odoo.exceptions import ValidationError
from odoo.tests import common, new_test_user


class TestSchedule(common.TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.Period = cls.env["hr.payroll.period"]
        cls.Schedule = cls.env["hr.payroll.period.schedule"]
        cls.Run = cls.env["hr.payslip.run"]
        cls.Payslip = cls.env["hr.payslip"]
        cls.Exception = cls.env["hr.payslip.exception"]
        cls.exRuleCrit = cls.env.ref("payroll_periods.payslip_exception_third")
        # Odoo 19: every employee owns an hr.version dated today; backdate it so
        # the versions created by the tests are not capped by a "today" version.
        cls.eeJohn = cls.env["hr.employee"].create(
            {"name": "EE John", "date_version": date(2000, 1, 1)}
        )
        cls.eeSally = cls.env["hr.employee"].create(
            {"name": "EE Sally", "date_version": date(2000, 1, 1)}
        )
        # Payroll Manager user
        cls.userPM = new_test_user(
            cls.env,
            login="hel",
            groups="base.group_user,payroll.group_payroll_manager",
            name="Payroll manager",
            email="ric@example.com",
        )

        # Odoo 19 does not install demo data, so 'payroll.ALW' and
        # 'payroll.structure_base' do not exist. Build the salary structure the
        # contracts need: a NET rule that pays the wage, plus the commission
        # rule that carries the payslip input line under test.
        cls.cat_alw = cls.env["hr.salary.rule.category"].create(
            {"name": "Allowance", "code": "ALW"}
        )
        cls.cat_net = cls.env["hr.salary.rule.category"].create(
            {"name": "Net", "code": "NET"}
        )
        cls.rule_commision = cls.env["hr.salary.rule"].create(
            {
                "name": "Commission",
                "code": "COMM",
                "category_id": cls.cat_alw.id,
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
        cls.rule_net = cls.env["hr.salary.rule"].create(
            {
                "name": "Net Salary",
                "code": "NET",
                "category_id": cls.cat_net.id,
                "sequence": 100,
                "condition_select": "none",
                "amount_select": "code",
                "amount_python_compute": "result = contract.wage",
            }
        )

        cls.pay_struct = cls.env["hr.payroll.structure"].create(
            {
                "name": "Test Structure",
                "code": "TEST",
                "rule_ids": [(6, 0, [cls.rule_commision.id, cls.rule_net.id])],
            }
        )

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

    def create_contract(self, eid, start, end=None, trial_end=None, pps_id=None):
        # Odoo 19: hr.contract is gone; a contract is an hr.version with
        # contract dates. date_version is unique per employee, so it is pinned
        # to the contract start date.
        return self.env["hr.version"].create(
            {
                "name": "Contract",
                "employee_id": eid,
                "wage": 1,
                "date_version": start,
                "contract_date_start": start,
                "contract_date_end": end,
                "trial_date_end": trial_end,
                "struct_id": self.pay_struct.id,
                "pps_id": pps_id,
            }
        )

    def apply_end_cron(self):
        # Odoo 19: method_direct_trigger() runs the job through the scheduler
        # (separate transaction), so its writes are invisible to the test. Run
        # the underlying server action inside the test transaction instead.
        self.env.ref(
            "payroll_periods.hr_payroll_period_ended_cron"
        ).ir_actions_server_id.run()

    def test_newly_created_period(self):
        """Newly created period should be in 'open' state"""

        pps = self.create_payroll_schedule("monthly", date.today())
        for pp in pps.pay_period_ids:
            self.assertEqual("open", pp.state)

    def test_state_ended(self):
        """Ended state should have state: ended"""

        start = datetime(2021, 1, 1)
        end = datetime(2021, 1, 31, 23, 59, 59)
        pps = self.create_payroll_schedule("manual", start.date())
        pp = self.create_payroll_period(pps.id, start, end)

        pp.set_state_ended()
        self.assertEqual("ended", pp.state)

    def test_cron_set_ended(self):
        """Set periods past their end date to state: ended"""

        # relativedelta(year=1) sets the year to 1 (absolute), which blew up in
        # pytz; -years=1 is what the test means.
        d = date.today() - relativedelta(years=1)
        start = datetime(d.year, 1, 1)
        pps = self.create_payroll_schedule("monthly", start.date())
        # Creating a schedule does not create its periods; add the (past)
        # periods so the cron has something to end.
        pps.button_add_pay_periods()
        self.assertTrue(pps.pay_period_ids)

        self.apply_end_cron()

        for pp in pps.pay_period_ids:
            self.assertEqual("ended", pp.state)

    def test_is_ended(self):
        """If period is past date_end + max roll-over hours it is ended"""

        dt = datetime.now()
        dtStart = dt - relativedelta(days=10)
        dtEnd = dt - relativedelta(hours=6, seconds=1)
        pps = self.create_payroll_schedule("manual", dtStart.date())
        pp = self.create_payroll_period(pps.id, dtStart, dtEnd)

        self.assertTrue(pp.is_ended())

    def test_is_not_ended(self):
        """If period is *NOT* past date_end + max roll-over hours it has not ended"""

        dt = datetime.now()
        dtStart = dt - relativedelta(days=10)
        dtEnd = dt - relativedelta(hours=5, seconds=55)
        pps = self.create_payroll_schedule("manual", dtStart.date())
        pp = self.create_payroll_period(pps.id, dtStart, dtEnd)

        self.assertFalse(pp.is_ended())

    def test_state_payment(self):
        """Periods in payment stage should have state: ended"""

        start = datetime(2021, 1, 1)
        end = datetime(2021, 1, 31, 23, 59, 59)
        pps = self.create_payroll_schedule("manual", start.date())
        pp = self.create_payroll_period(pps.id, start, end)

        pp.set_state_payment()
        self.assertEqual("payment", pp.state)

    def test_state_payment_with_unignored_exceptions(self):
        """Periods going to payment stage with *UN*-ignored exceptions should *fail*"""

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
        slip = self.Payslip.create(
            {
                "name": "A Payslip",
                "employee_id": self.eeJohn.id,
                "payslip_run_id": run.id,
            }
        )
        self.Exception.create(
            {
                "name": "Net salary less than 1/3 of GROSS",
                "rule_id": self.exRuleCrit.id,
                "slip_id": slip.id,
            }
        )

        self.assertEqual(1, len(pp.exception_ids))
        with self.assertRaises(ValidationError):
            pp.set_state_payment()

    def test_state_payment_with_ignored_exceptions(self):
        """Periods going to payment stage with ignored exceptions should *succeed*"""

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
        slip = self.Payslip.create(
            {
                "name": "A Payslip",
                "employee_id": self.eeJohn.id,
                "payslip_run_id": run.id,
            }
        )
        self.Exception.create(
            {
                "name": "Net salary less than 1/3 of GROSS",
                "rule_id": self.exRuleCrit.id,
                "slip_id": slip.id,
                "ignore": True,
            }
        )

        self.assertEqual(1, len(pp.exception_ids))
        try:
            pp.set_state_payment()
        except ValidationError:
            self.fail("An unexpected Exception was raised")
        self.assertEqual("payment", pp.state)

    def test_create_payslip_dates(self):
        """Payslip date_from -> date_to = same as payroll period adj. for tz"""

        start = datetime(2021, 1, 1)
        end = datetime(2021, 1, 31, 23, 59, 59)
        self.create_contract(self.eeJohn.id, start)
        pps = self.create_payroll_schedule("manual", start.date())
        tz_local = timezone(pps.tz)
        tz_start = tz_local.localize(start, is_dst=False)
        tz_end = tz_local.localize(end, is_dst=False)
        utc_start = tz_start.astimezone(utc)
        utc_end = tz_end.astimezone(utc)
        pp = self.create_payroll_period(
            pps.id, utc_start.replace(tzinfo=None), utc_end.replace(tzinfo=None)
        )

        run = self.Run.create(
            {
                "name": "Run A",
                "date_start": start.date(),
                "date_end": end.date(),
                "period_id": pp.id,
            }
        )
        slip = pp.create_payslip(self.eeJohn.id, run_id=run.id)

        self.assertEqual(pp.date_start.date(), date(2020, 12, 31))
        self.assertEqual(pp.date_end.date(), date(2021, 1, 31))
        self.assertEqual(slip.date_from, date(2021, 1, 1))
        self.assertEqual(slip.date_to, date(2021, 1, 31))

    def test_create_payslip_dates_two_contract(self):
        """Payslip with 2 contracts: date_from -> date_to = sum of both"""

        start = datetime(2021, 1, 1)
        end = datetime(2021, 1, 31, 23, 59, 59)
        c2End = start + relativedelta(days=20)
        self.create_contract(self.eeJohn.id, start, start + relativedelta(days=10))
        self.create_contract(self.eeJohn.id, start + relativedelta(days=11), c2End)
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
        slip = pp.create_payslip(self.eeJohn.id, run_id=run.id)

        self.assertEqual(pp.date_start.date(), slip.date_from)
        self.assertEqual(c2End.date(), slip.date_to)

    def test_payslip_input_line(self):
        """After creation the payslip contains configured input lines"""

        start = datetime(2021, 1, 1)
        end = datetime(2021, 1, 31, 23, 59, 59)
        pps = self.create_payroll_schedule("manual", start.date())
        cc = self.create_contract(self.eeJohn.id, start.date(), pps_id=pps.id)
        pp = self.create_payroll_period(pps.id, start, end)
        run = self.Run.create(
            {
                "name": "Run A",
                "date_start": start.date(),
                "date_end": end.date(),
                "period_id": pp.id,
            }
        )
        # Odoo 19: contracts have no draft/approved state; a version carrying
        # contract dates is in force and is picked up by the period.
        self.assertTrue(cc.is_in_contract)
        self.assertIn(self.rule_commision, cc.struct_id.rule_ids)
        slip = pp.create_payslip(self.eeJohn.id, run_id=run.id)

        payslip_input = self.env["hr.payslip.input"].search(
            [("payslip_id", "=", slip.id)]
        )
        self.assertEqual(cc, slip.contract_id)
        self.assertEqual(1, len(payslip_input))
        self.assertIn("SALECOM", slip.input_line_ids.mapped("code"))

    def test_rerun_payslip(self):
        """Re-running the payslip should create a new payslip and re-compute it"""

        start = datetime(2021, 1, 1)
        end = datetime(2021, 1, 31, 23, 59, 59)
        pps = self.create_payroll_schedule("manual", start.date())
        self.create_contract(self.eeJohn.id, start.date(), pps_id=pps.id)
        pp = self.create_payroll_period(pps.id, start, end)
        run = self.Run.create(
            {
                "name": "Run A",
                "date_start": start.date(),
                "date_end": end.date(),
                "period_id": pp.id,
            }
        )
        slip = pp.create_payslip(self.eeJohn.id, run_id=run.id)
        slip.compute_sheet()
        id_old = slip.id
        self.assertEqual(1, slip.get_salary_line_total("NET"))

        slip.action_payslip_cancel()
        slip = pp.rerun_payslip(slip)

        self.assertEqual(1, slip.get_salary_line_total("NET"))
        self.assertNotEqual(id_old, slip.id)

    def test_run_multiple_payslips(self):
        """Running more than one payslip at a time"""

        start = datetime(2021, 1, 1)
        end = datetime(2021, 1, 31, 23, 59, 59)
        pps = self.create_payroll_schedule("manual", start.date())
        self.create_contract(self.eeJohn.id, start.date(), pps_id=pps.id)
        self.create_contract(self.eeSally.id, start.date(), pps_id=pps.id)
        pp = self.create_payroll_period(pps.id, start, end)
        run = self.Run.create(
            {
                "name": "Run A",
                "date_start": start.date(),
                "date_end": end.date(),
                "period_id": pp.id,
            }
        )
        slip = pp.create_payslip(self.eeJohn.id, run_id=run.id)
        slip2 = pp.create_payslip(self.eeSally.id, run_id=run.id)
        slips = slip + slip2
        slips.compute_sheet()

        self.assertEqual(1, slip.get_salary_line_total("NET"))
        self.assertEqual(1, slip2.get_salary_line_total("NET"))
