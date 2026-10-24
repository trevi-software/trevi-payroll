# Copyright (C) 2022 Trevi Software (https://trevi.et)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from datetime import datetime, time

from dateutil.relativedelta import relativedelta

from odoo.addons.payroll.tests.common import TestPayslipBase


class TestHrPayslip(TestPayslipBase):
    def setUp(self):
        super().setUp()

        self.Contract = self.env["hr.version"]
        self.HrPayslip = self.env["hr.payslip"]
        self.Rule = self.env["hr.salary.rule"]
        self.Requests = self.env["hr.leave"]
        self.HolidaysStatus = self.env["hr.leave.type"]

        # create holiday type
        self.holiday_type = self.HolidaysStatus.create(
            {
                "name": "TestLeaveType",
                "code": "TESTLV",
                "company_id": self.env.company.id,
                "requires_allocation": False,
                "leave_validation_type": "no_validation",
            }
        )

        # 19.0: 'payroll.hr_rule_basic' and 'payroll.structure_base' only exist
        # in payroll's demo data, which is no longer installed by default.
        # TestPayslipBase already builds the basic rule and the structure.
        self.mock_rule = self.Rule.create(
            {
                "name": "Leave Salary Rule",
                "code": "TESTLV",
                "sequence": 5,
                "category_id": self.categ_alw.id,
                "condition_select": "python",
                "condition_python": "result = 0",
                "amount_select": "code",
                "amount_python_compute": "result = 1000.0",
            }
        )
        self.developer_pay_structure.write({"rule_ids": [(4, self.mock_rule.id)]})

        self.resource_calendar_std = self.env.ref("resource.resource_calendar_std")
        contracts = self.Contract.search([("employee_id", "=", self.richard_emp.id)])
        contracts[0].resource_calendar_id = self.resource_calendar_std
        # 19.0: hr.contract is gone, hr.version is the contract record. The
        # contract start is a stored field now; date_start is computed from it.
        contracts[0].contract_date_start = datetime(2022, 1, 1)
        contracts[0].contract_date_end = False

    def test_holiday_type_code(self):
        # The rule must consume the code this module supplies (the leave type's
        # own code), not an arbitrary placeholder, otherwise the test would pass
        # even if the module stopped rewriting the worked-days line code.
        self.mock_rule.condition_python = "result = worked_days.TESTLV"
        self.mock_rule.amount_python_compute = (
            "result = worked_days.TESTLV.number_of_days"
        )

        self.apply_contract_cron()
        # hr.contract.state ('open'/'trial') has no equivalent in 19.0; the
        # contract is simply the employee's current hr.version.
        contract = self.richard_emp.version_id
        self.assertTrue(contract.is_current, "Contract is the current version")

        # Set system parameter
        self.env["ir.config_parameter"].sudo().set_param(
            "payroll.leaves_positive", True
        )

        # Create a leave request
        lv_from = datetime.combine(datetime.today(), time.min)
        lv_to = datetime.combine(datetime.today(), time.max)
        while lv_from.date().weekday() in [5, 6]:
            lv_from -= relativedelta(days=1)
        while lv_to.date().weekday() in [5, 6]:
            lv_to -= relativedelta(days=1)
        leave = self.Requests.create(
            {
                "name": "Hol11",
                "employee_id": self.richard_emp.id,
                "holiday_status_id": self.holiday_type.id,
                "request_date_from": lv_from.date(),
                "request_date_to": lv_to.date(),
            }
        )
        self.assertEqual(
            leave.state, "validate", "newly created leave request is in validate state"
        )

        # I create an employee Payslip and process it
        richard_payslip = self.env["hr.payslip"].create(
            {"name": "Payslip of Richard", "employee_id": self.richard_emp.id}
        )
        richard_payslip.onchange_employee()
        richard_payslip.compute_sheet()

        worked_days_line = richard_payslip.worked_days_line_ids.filtered(
            lambda line: line.code == "TESTLV"
        )
        self.assertEqual(
            len(worked_days_line), 1, "There is a worked_days_line for the leave"
        )
        self.assertEqual(
            worked_days_line.number_of_days,
            1.0,
            "The number of days for the leave is the same as the holiday request",
        )
        self.assertEqual(
            len(
                richard_payslip.worked_days_line_ids.filtered(
                    lambda line: line.code == "WORK100"
                )
            ),
            1,
            "The 'WORK100' worked days line is still there",
        )

        # The salary rule reads worked_days.TESTLV, so its condition is met and
        # it must produce a salary line whose amount equals the number of days
        # supplied by the leave worked-days line.
        salary_line = richard_payslip.line_ids.filtered(
            lambda line: line.code == "TESTLV"
        )
        self.assertEqual(len(salary_line), 1, "The salary rule computed a salary line")
        self.assertEqual(
            salary_line.total,
            1.0,
            "The salary line amount equals the leave's worked days",
        )
