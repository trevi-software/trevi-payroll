# Copyright (C) 2022 TREVI Software
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from datetime import date, datetime, timedelta

from . import common


class TestPresencePolicy(common.TestHrPayslip):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.LeaveType = cls.env["hr.leave.type"]
        cls.Accrual = cls.env["hr.accrual"]
        cls.AccrualPolicy = cls.env["hr.policy.accrual"]
        cls.AccrualPolicyLine = cls.env["hr.policy.line.accrual"]

        cls.lt = cls.LeaveType.create({"name": "Rest-day Compensatory"})
        cls.aa = cls.Accrual.create(
            {"name": "Compensatory Rest day", "holiday_status_id": cls.lt.id}
        )
        cls.policy = cls.AccrualPolicy.create(
            {
                "name": "Compensatory Restday",
                "date": date(2022, 1, 1),
            }
        )
        cls.pl = cls.AccrualPolicyLine.create(
            {
                "name": "Compensatory Rest",
                "code": "CRS",
                "type": "hour",
                "accrual_id": cls.aa.id,
                "policy_id": cls.policy.id,
                "accrual_rate_hour": 1.0,
            }
        )
        cls.restday_presence_line.accrual_policy_line_id = cls.pl
        cls.restday_presence_line.accrual_min = 8.0
        cls.restday_presence_line.accrual_max = 8.0

        # Create a salary rule for Accrual tests and add it to the salary structure
        cls.accrual_test_rule = cls.Rule.create(
            {
                "name": "Accrual test rule",
                "code": "ACRTEST",
                "category_id": cls.rule_category.id,
                "sequence": 6,
                "amount_select": "code",
                "amount_python_compute": "result = 0",
            }
        )
        cls.payroll_structure.write({"rule_ids": [(4, cls.accrual_test_rule.id)]})

        # Create a public holiday
        cls.public_holiday = cls.PublicHoliday.create(
            {
                "year": 2022,
                "line_ids": [
                    (0, 0, {"name": "Foo", "date": date(2022, 4, 2)}),
                ],
            }
        )

    def test_worked_hours(self):
        # I set the test rule to detect the number of regular worked hours
        self.test_rule.amount_python_compute = (
            "result_rate = worked_days.PL1.rate * 100 \n"
            "result = worked_days.PL1.number_of_hours"
        )

        # I create a contract for "Richard"
        contract_start = date(2022, 1, 1)
        start = date(2022, 4, 1)
        end = date(2022, 4, 30)
        self.create_contract(contract_start, False, self.richard_emp, 5000.0)

        # I create attendance for one day
        self.Attendance.create(
            {
                "employee_id": self.richard_emp.id,
                "check_in": datetime.combine(
                    start, datetime.strptime("08:00", "%H:%M").time()
                ),
                "check_out": datetime.combine(
                    start, datetime.strptime("16:00", "%H:%M").time()
                ),
            }
        )

        # I create an employee Payslip and process it
        richard_payslip = self.create_payslip(
            start, end, self.richard_emp, user=self.payroll_user
        )
        richard_payslip.onchange_employee()
        richard_payslip.compute_sheet()

        line = richard_payslip.line_ids.filtered(lambda line: line.code == "TEST")
        self.assertEqual(len(line), 1, "I found the Test line")
        self.assertEqual(
            line[0].amount,
            8.0,
            "The number of worked hours is 8",
        )
        self.assertEqual(
            line[0].rate,
            100,
            "Regular hours are paid at the normal rate",
        )

    def test_worked_holiday(self):
        # I check that public holidays exist
        ph = self.PublicHoliday.search([("year", "=", 2022)])
        self.assertTrue(ph, "There is a public holiday object")
        self.assertGreater(len(ph.line_ids), 0, "At least one public holiday")

        # I set the test rule to detect the number of holiday worked hours
        self.test_rule.amount_python_compute = (
            "result_rate = worked_days.HOL.rate * 100 \n"
            "result = worked_days.HOL.number_of_hours"
        )

        # I create a contract for "Richard"
        contract_start = date(2022, 1, 1)
        start = date(2022, 4, 1)
        end = date(2022, 4, 30)
        self.create_contract(contract_start, False, self.richard_emp, 5000.0)

        # I create attendance on a public holiday
        self.Attendance.create(
            {
                "employee_id": self.richard_emp.id,
                "check_in": datetime.combine(
                    start + timedelta(days=1),
                    datetime.strptime("08:00", "%H:%M").time(),
                ),
                "check_out": datetime.combine(
                    start + timedelta(days=1),
                    datetime.strptime("16:00", "%H:%M").time(),
                ),
            }
        )

        # I create an employee Payslip and process it
        richard_payslip = self.create_payslip(
            start, end, self.richard_emp, user=self.payroll_user
        )
        richard_payslip.onchange_employee()
        richard_payslip.compute_sheet()

        line = richard_payslip.line_ids.filtered(lambda line: line.code == "TEST")
        self.assertEqual(len(line), 1, "I found the Test line")
        self.assertEqual(
            line[0].amount,
            8.0,
            "The number of worked holiday hours is 8",
        )
        self.assertEqual(
            line[0].rate,
            200,
            "Holiday hours are paid double",
        )

    def test_worked_restday(self):
        # I set the test rule to detect the number of rest day worked hours
        self.test_rule.amount_python_compute = (
            "result_rate = worked_days.RST.rate * 100 \n"
            "result = worked_days.RST.number_of_hours"
        )
        # I set the test rule to detect the number of accruals added
        self.accrual_test_rule.amount_python_compute = (
            "result_rate = worked_days.CRS.rate * 100 \n"
            "result = worked_days.CRS.number_of_hours"
        )

        # I create a contract for "Richard"
        contract_start = date(2022, 1, 1)
        start = date(2022, 4, 1)
        end = date(2022, 4, 30)
        self.create_contract(contract_start, False, self.richard_emp, 5000.0)

        # I create attendance for seven days in a row
        monday = date(2022, 4, 4)
        for day in range(0, 7):
            self.Attendance.create(
                {
                    "employee_id": self.richard_emp.id,
                    "check_in": self.localize_dt(
                        datetime.combine(
                            monday + timedelta(days=day),
                            datetime.strptime("08:00", "%H:%M").time(),
                        ),
                        self.richard_emp.tz,
                        reverse=True,
                    ),
                    "check_out": self.localize_dt(
                        datetime.combine(
                            monday + timedelta(days=day),
                            datetime.strptime("16:00", "%H:%M").time(),
                        ),
                        self.richard_emp.tz,
                        reverse=True,
                    ),
                }
            )

        # I create an employee Payslip and process it
        richard_payslip = self.create_payslip(
            start, end, self.richard_emp, user=self.payroll_user
        )
        richard_payslip.onchange_employee()
        richard_payslip.compute_sheet()

        line = richard_payslip.line_ids.filtered(lambda line: line.code == "TEST")
        self.assertEqual(len(line), 1, "I found the Test line")
        self.assertEqual(
            line[0].amount,
            8.0,
            "The number of worked rest day hours is 8 (1 day)",
        )
        self.assertEqual(
            line[0].rate,
            100,
            "Rest day hours are accrued at the regular rate",
        )

        line = richard_payslip.line_ids.filtered(lambda line: line.code == "ACRTEST")
        self.assertEqual(len(line), 1, "I found the Accrual Test line")
        self.assertEqual(
            line[0].amount,
            8.0,
            "The number of accrued hours is 8",
        )
        self.assertEqual(
            line[0].rate,
            100,
            "Rest day hours are accrued at a 1:1 rate",
        )

    def test_worked_restday_weekend(self):
        # I set the weekly working days to 5
        self.presence_policy.work_days_per_week = 5

        # I adjust the accrual multiple to 2:1
        self.pl.accrual_rate_hour = 2.0

        # I set the test rule to detect the number of rest day worked hours
        self.test_rule.amount_python_compute = (
            "result_rate = worked_days.RST.rate * 100 \n"
            "result = worked_days.RST.number_of_hours"
        )
        # I set the test rule to detect the number of accruals added
        self.accrual_test_rule.amount_python_compute = (
            "result_rate = worked_days.CRS.rate * 100 \n"
            "result = worked_days.CRS.number_of_hours"
        )

        # I create a contract for "Richard"
        contract_start = date(2022, 1, 1)
        start = date(2022, 4, 1)
        end = date(2022, 4, 30)
        self.create_contract(contract_start, False, self.richard_emp, 5000.0)

        # I create attendance for eight days in a row
        monday = date(2022, 4, 4)
        for day in range(0, 8):
            self.Attendance.create(
                {
                    "employee_id": self.richard_emp.id,
                    "check_in": self.localize_dt(
                        datetime.combine(
                            monday + timedelta(days=day),
                            datetime.strptime("08:00", "%H:%M").time(),
                        ),
                        self.richard_emp.tz,
                        reverse=True,
                    ),
                    "check_out": self.localize_dt(
                        datetime.combine(
                            monday + timedelta(days=day),
                            datetime.strptime("16:00", "%H:%M").time(),
                        ),
                        self.richard_emp.tz,
                        reverse=True,
                    ),
                }
            )

        # I create an employee Payslip and process it
        richard_payslip = self.create_payslip(
            start, end, self.richard_emp, user=self.payroll_user
        )
        richard_payslip.onchange_employee()
        richard_payslip.compute_sheet()

        line = richard_payslip.line_ids.filtered(lambda line: line.code == "TEST")
        self.assertEqual(len(line), 1, "I found the Test line")
        self.assertEqual(
            line[0].amount,
            16.0,
            "The number of worked rest day hours is 16 (2 days)",
        )
        self.assertEqual(
            line[0].rate,
            100,
            "Rest day hours are accrued at the regular rate",
        )

        line = richard_payslip.line_ids.filtered(lambda line: line.code == "ACRTEST")
        self.assertEqual(len(line), 1, "I found the Accrual Test line")
        self.assertEqual(
            line[0].amount,
            16.0,
            "The number of accrued hours is 16",
        )
        self.assertEqual(
            line[0].rate,
            200,
            "Rest day hours are accrued at a 2:1 rate",
        )

    def test_presence_policy_per_contract(self):
        # A payslip can cover several contracts, each with its own policy
        # group. Each contract must be resolved against its own policies: the
        # caches resolved for the first contract must not leak into the second.
        #
        # Policy group B uses a 6 hour normal workday, group A (the default)
        # an 8 hour one.
        group_b = self.PolicyGroup.create({"name": "policy group B"})
        policy_b = self.PresencePolicy.create(
            {"name": "POLICY2", "date": date(2000, 1, 1)}
        )
        self.PresencePolicyLine.create(
            {
                "name": "Presence Line - Normal 6h workday",
                "code": "PL2",
                "type": "normal",
                "active_after": 0.0,
                "duration": 6.0 * 60,
                "policy_id": policy_b.id,
            }
        )
        group_b.presence_policy_ids = [(4, policy_b.id)]

        start = date(2022, 4, 1)
        end = date(2022, 4, 30)
        # 2022-04-01..15 has 11 working days, 2022-04-16..30 has 10.
        contract_a = self.create_contract(
            date(2022, 4, 1), date(2022, 4, 15), self.richard_emp, 5000.0, name="C-A"
        )
        contract_b = self.create_contract(
            date(2022, 4, 16),
            date(2022, 4, 30),
            self.richard_emp,
            5000.0,
            name="C-B",
            policy_group=group_b,
        )

        richard_payslip = self.create_payslip(
            start, end, self.richard_emp, user=self.payroll_user
        )
        lines = richard_payslip.get_worked_day_lines(
            contract_a | contract_b, start, end
        )

        max_by_contract = {
            line["contract_id"]: line for line in lines if line["code"] == "MAX"
        }
        self.assertEqual(
            max_by_contract[contract_a.id]["number_of_hours"],
            88.0,
            "Contract A requires 11 working days of 8 hours",
        )
        self.assertEqual(
            max_by_contract[contract_b.id]["number_of_hours"],
            60.0,
            "Contract B requires 10 working days of 6 hours (its own policy)",
        )
