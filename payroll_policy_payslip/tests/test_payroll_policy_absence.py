# Copyright (C) 2022 TREVI Software
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from datetime import date

from . import common


class TestAbsencePolicy(common.TestHrPayslip):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.LeaveType = cls.env["hr.leave.type"]
        cls.LeaveRequest = cls.env["hr.leave"]
        cls.AbsencePolicy = cls.env["hr.policy.absence"]
        cls.AbsencePolicyLine = cls.env["hr.policy.line.absence"]

        # Create salary rules for Absence tests and add it to the salary structure
        cls.absence_test_rule = cls.Rule.create(
            {
                "name": "Absence test rule",
                "code": "ABTEST",
                "category_id": cls.rule_category.id,
                "sequence": 6,
                "amount_select": "code",
                "amount_python_compute": "result = 0",
            }
        )
        cls.awol_test_rule = cls.Rule.create(
            {
                "name": "AWOL test rule",
                "code": "AWTEST",
                "category_id": cls.rule_category.id,
                "sequence": 6,
                "amount_select": "code",
                "amount_python_compute": "result = 0",
            }
        )
        cls.payroll_structure.write({"rule_ids": [(4, cls.absence_test_rule.id)]})
        cls.payroll_structure.write({"rule_ids": [(4, cls.awol_test_rule.id)]})

        # Create an AWOL leave type
        cls.awol_leave_type = cls.LeaveType.create(
            {
                "name": "Absent without Leave",
                "unpaid": True,
            }
        )

        # Create Leave types
        cls.sick_leave_type = cls.LeaveType.create(
            {
                "name": "Sick Leave",
                "requires_allocation": False,
                "leave_validation_type": "hr",
            }
        )
        cls.hourly_leave_type = cls.LeaveType.create(
            {
                "name": "Hourly Leave",
                "requires_allocation": False,
                "leave_validation_type": "hr",
                "request_unit": "hour",
            }
        )

        # Create an Absence Policy
        cls.absence_policy = cls.AbsencePolicy.create(
            {"name": "Absence Policy", "date": date(2000, 1, 1)}
        )
        cls.AbsencePolicyLine.create(
            {
                "name": "Line - Absent Without Leave",
                "code": "AWOL",
                "type": "dock",
                "rate": 1.0,
                "holiday_status_id": cls.awol_leave_type.id,
                "use_awol": True,
                "policy_id": cls.absence_policy.id,
            }
        )
        cls.AbsencePolicyLine.create(
            {
                "name": "Line - Sick Leave",
                "code": "SICK50",
                "type": "paid",
                "rate": 0.5,
                "holiday_status_id": cls.sick_leave_type.id,
                "policy_id": cls.absence_policy.id,
            }
        )
        cls.AbsencePolicyLine.create(
            {
                "name": "Line - Hourly Leave",
                "code": "HOURLY",
                "type": "dock",
                "rate": 1.0,
                "holiday_status_id": cls.hourly_leave_type.id,
                "policy_id": cls.absence_policy.id,
            }
        )

        # I put the absence policy in the policy group
        cls.default_policy_group.absence_policy_ids = [(4, cls.absence_policy.id)]

    def test_no_hours(self):
        # I set the test rule to detect the number of regular worked hours
        self.test_rule.amount_python_compute = (
            "result_rate = worked_days.PL1.rate * 100 \n"
            "result = worked_days.PL1.number_of_hours"
        )

        # I set the test rule to detect the number of AWOL hours
        self.absence_test_rule.amount_python_compute = (
            "result_rate = worked_days.AWOL.rate * 100 \n"
            "result = worked_days.AWOL.number_of_hours"
        )

        # I create a contract for "Richard"
        contract_start = date(2022, 1, 1)
        start = date(2022, 4, 1)
        end = date(2022, 4, 30)
        self.create_contract(contract_start, False, self.richard_emp, 5000.0)

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
            0.0,
            "There is no attenance",
        )

        line = richard_payslip.line_ids.filtered(lambda line: line.code == "ABTEST")
        self.assertEqual(len(line), 1, "I found the Absence Test line")
        self.assertEqual(
            line[0].amount,
            168.0,
            "There entire month of April is AWOL",
        )
        self.assertEqual(
            line[0].rate,
            -100,
            "AWOL hours are DOCKED 100%",
        )

    def test_public_holiday_absence(self):
        # Create a public holiday
        self.public_holiday = self.PublicHoliday.create(
            {
                "year": 2022,
                "line_ids": [
                    (0, 0, {"name": "Foo", "date": date(2022, 4, 5)}),
                ],
            }
        )

        # I check that public holidays exist
        ph = self.PublicHoliday.search([("year", "=", 2022)])
        self.assertTrue(ph, "There is a public holiday object")
        self.assertGreater(len(ph.line_ids), 0, "At least one public holiday")

        # I set the test rule to detect the number of regular worked hours
        self.test_rule.amount_python_compute = (
            "result_rate = worked_days.PL1.rate * 100 \n"
            "result = worked_days.PL1.number_of_hours"
        )

        # I set the test rule to detect the number of AWOL hours
        self.absence_test_rule.amount_python_compute = (
            "result_rate = worked_days.AWOL.rate * 100 \n"
            "result = worked_days.AWOL.number_of_hours"
        )

        # I create a contract for "Richard"
        contract_start = date(2022, 1, 1)
        start = date(2022, 4, 1)
        end = date(2022, 4, 30)
        self.create_contract(contract_start, False, self.richard_emp, 5000.0)

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
            0.0,
            "There is no attenance",
        )

        line = richard_payslip.line_ids.filtered(lambda line: line.code == "ABTEST")
        self.assertEqual(len(line), 1, "I found the Absence Test line")
        self.assertEqual(
            line[0].amount,
            160.0,
            "There entire month of April is AWOL minus the public holiday",
        )
        self.assertEqual(
            line[0].rate,
            -100,
            "AWOL hours are DOCKED 100%",
        )

    def test_leave_dock(self):
        # Set system parameter
        self.env["ir.config_parameter"].sudo().set_param(
            "payroll.leaves_positive", True
        )

        # Create a leave request
        lv = self.LeaveRequest.create(
            {
                "name": "Richard Sick Leave",
                "employee_id": self.richard_emp.id,
                "holiday_status_id": self.sick_leave_type.id,
                "request_date_from": date(2022, 4, 4),
                "request_date_to": date(2022, 4, 5),
            }
        )
        lv.action_approve()
        self.assertEqual(lv.state, "validate", "the leave is in validate state")

        # I set the test rule to detect the number of regular worked hours
        self.test_rule.amount_python_compute = (
            "result_rate = worked_days.PL1.rate * 100 \n"
            "result = worked_days.PL1.number_of_hours"
        )

        # I set the test rule to detect the number of leave hours
        self.absence_test_rule.amount_python_compute = (
            "result_rate = worked_days.SICK50.rate * 100 \n"
            "result = worked_days.SICK50.number_of_hours"
        )

        # I set the test rule to detect the number of awol hours
        self.awol_test_rule.amount_python_compute = (
            "result_rate = worked_days.AWOL.rate * 100 \n"
            "result = worked_days.AWOL.number_of_hours"
        )

        # I create a contract for "Richard"
        contract_start = date(2022, 1, 1)
        start = date(2022, 4, 1)
        end = date(2022, 4, 30)
        self.create_contract(contract_start, False, self.richard_emp, 5000.0)

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
            0.0,
            "There is no attenance",
        )

        line = richard_payslip.line_ids.filtered(lambda line: line.code == "ABTEST")
        self.assertEqual(len(line), 1, "I found the Absence Test line")
        self.assertEqual(
            line[0].amount,
            16.0,
            "The time of the sick leave is recorded in worked_days",
        )
        self.assertEqual(
            line[0].rate,
            50.0,
            "The time the employee was on sick leave is paid at 0.5x",
        )

        line = richard_payslip.line_ids.filtered(lambda line: line.code == "AWTEST")
        self.assertEqual(len(line), 1, "I found the AWOL Test line")
        self.assertEqual(
            line[0].amount,
            168.0 - (2 * 8.0),
            "The time of the sick leave is not marked as AWOL",
        )

    def test_leave_partial_awol(self):
        # Set system parameter
        self.env["ir.config_parameter"].sudo().set_param(
            "payroll.leaves_positive", True
        )

        # Create a leave request
        lv = self.LeaveRequest.create(
            {
                "name": "Richard Partial Leave",
                "employee_id": self.richard_emp.id,
                "holiday_status_id": self.hourly_leave_type.id,
                "request_date_from": date(2022, 4, 5),
                "request_date_to": date(2022, 4, 5),
                "request_unit_hours": True,
                "request_hour_from": "8",
                "request_hour_to": "12",
            }
        )
        lv._compute_date_from_to()
        lv.action_approve()
        self.assertEqual(lv.state, "validate", "the leave is in validate state")

        # I set the test rule to detect the number of regular worked hours
        self.test_rule.amount_python_compute = (
            "result_rate = worked_days.PL1.rate * 100 \n"
            "result = worked_days.PL1.number_of_hours"
        )

        # I set the test rule to detect the number of leave hours
        self.absence_test_rule.amount_python_compute = (
            "result_rate = worked_days.HOURLY.rate * 100 \n"
            "result = worked_days.HOURLY.number_of_hours"
        )

        # I set the test rule to detect the number of awol hours
        self.awol_test_rule.amount_python_compute = (
            "result_rate = worked_days.AWOL.rate * 100 \n"
            "result = worked_days.AWOL.number_of_hours"
        )

        # I create a contract for "Richard"
        contract_start = date(2022, 1, 1)
        start = date(2022, 4, 1)
        end = date(2022, 4, 30)
        self.create_contract(contract_start, False, self.richard_emp, 5000.0)

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
            0.0,
            "There is no attenance",
        )

        line = richard_payslip.line_ids.filtered(lambda line: line.code == "ABTEST")
        self.assertEqual(len(line), 1, "I found the Absence Test line")
        self.assertEqual(
            line[0].amount,
            4.0,
            "The time of the partial leave is only 1/2 day",
        )

        line = richard_payslip.line_ids.filtered(lambda line: line.code == "AWTEST")
        self.assertEqual(len(line), 1, "I found the AWOL Test line")
        self.assertEqual(
            line[0].amount,
            168.0 - 4.0,
            "The AWOL time for the other 1/2 day is recorded correctly",
        )

        wdl = richard_payslip.worked_days_line_ids.filtered(
            lambda line: line.code == "AWOL"
        )
        self.assertEqual(len(wdl), 1, "I found the AWOL worked days line")
        self.assertEqual(
            wdl[0].number_of_days,
            20.5,
            "In worked days line field 'number_of_days' 1/2 day is subtracted",
        )

    def test_absence_multiple_contracts(self):
        # Two contracts use the same policy group (both with AWOL). The second
        # contract must get its own AWOL worked-days line: matching the first
        # contract's line (which lives in ``super_res``) left the second
        # contract without an AWOL entry and raised a KeyError when the AWOL
        # hours were added.
        start = date(2022, 4, 1)
        end = date(2022, 4, 30)
        # 2022-04-01..15 has 11 working days, 2022-04-16..30 has 10.
        contract_a = self.create_contract(
            date(2022, 4, 1), date(2022, 4, 15), self.richard_emp, 5000.0, name="C-A"
        )
        contract_b = self.create_contract(
            date(2022, 4, 16), date(2022, 4, 30), self.richard_emp, 5000.0, name="C-B"
        )

        richard_payslip = self.create_payslip(
            start, end, self.richard_emp, user=self.payroll_user
        )
        lines = richard_payslip.get_worked_day_lines(
            contract_a | contract_b, start, end
        )

        awol_by_contract = {
            line["contract_id"]: line for line in lines if line["code"] == "AWOL"
        }
        self.assertEqual(
            len(awol_by_contract),
            2,
            "Each contract gets its own AWOL worked days line",
        )
        self.assertAlmostEqual(
            awol_by_contract[contract_a.id]["number_of_hours"],
            88.0,
            msg="Contract A is AWOL for 11 working days of 8 hours",
        )
        self.assertAlmostEqual(
            awol_by_contract[contract_b.id]["number_of_hours"],
            80.0,
            msg="Contract B is AWOL for 10 working days of 8 hours",
        )

    def test_absence_policy_change_mid_period(self):
        # The presence policy is replaced mid-period by one with a different
        # normal duration and a new code. The required hours must follow the
        # policy active on each day (8h before 2022-04-16, 6h after) instead of
        # accumulating to 14h, which would mark worked days as AWOL and inflate
        # MAX.
        policy2 = self.PresencePolicy.create(
            {"name": "POLICY2", "date": date(2022, 4, 16)}
        )
        self.PresencePolicyLine.create(
            {
                "name": "Presence Line - Normal 6h workday",
                "code": "PL2",
                "type": "normal",
                "active_after": 0.0,
                "duration": 6.0 * 60,
                "policy_id": policy2.id,
            }
        )
        self.default_policy_group.presence_policy_ids = [(4, policy2.id)]

        self.test_rule.amount_python_compute = (
            "result_rate = worked_days.PL1.rate * 100 \n"
            "result = worked_days.PL1.number_of_hours"
        )
        self.absence_test_rule.amount_python_compute = (
            "result_rate = worked_days.AWOL.rate * 100 \n"
            "result = worked_days.AWOL.number_of_hours"
        )

        start = date(2022, 4, 1)
        end = date(2022, 4, 30)
        self.create_contract(date(2022, 1, 1), False, self.richard_emp, 5000.0)

        richard_payslip = self.create_payslip(
            start, end, self.richard_emp, user=self.payroll_user
        )
        richard_payslip.onchange_employee()
        richard_payslip.compute_sheet()

        line = richard_payslip.line_ids.filtered(lambda line: line.code == "ABTEST")
        self.assertEqual(len(line), 1, "I found the Absence Test line")
        # 11 working days x 8h (01-15) + 10 working days x 6h (16-30)
        self.assertEqual(
            line[0].amount,
            148.0,
            "AWOL follows the policy active on each day (8h then 6h)",
        )
