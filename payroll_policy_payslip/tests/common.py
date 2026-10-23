# Copyright (C) 2022 Trevi Software (https://trevi.et)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from datetime import date

from pytz import timezone, utc

from odoo.tests import common, new_test_user


class TestHrPayslip(common.TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.Contract = cls.env["hr.version"]
        cls.HrPayslip = cls.env["hr.payslip"]
        cls.Rule = cls.env["hr.salary.rule"]
        cls.PolicyGroup = cls.env["hr.policy.group"]
        cls.Attendance = cls.env["hr.attendance"]
        cls.PublicHoliday = cls.env["calendar.public.holiday"]
        cls.PresencePolicy = cls.env["hr.policy.presence"]
        cls.PresencePolicyLine = cls.env["hr.policy.line.presence"]

        cls.resource_calendar_std = cls.env.ref("resource.resource_calendar_std")

        # ``payroll.structure_base`` and the ``ALW`` category only exist in the
        # ``payroll`` demo data, which is not installed by default, so build
        # the minimal structure the tests need.
        cls.rule_category = cls.env["hr.salary.rule.category"].create(
            {"name": "Allowance", "code": "ALW"}
        )
        cls.payroll_structure = cls.env["hr.payroll.structure"].create(
            {"name": "Base for new structures", "code": "BASE"}
        )

        # Create a new employee "Richard"
        cls.richard_emp = cls.env["hr.employee"].create(
            {
                "name": "Richard",
                "birthday": "1984-05-01",
                "country_id": cls.env.ref("base.be").id,
                "resource_calendar_id": cls.resource_calendar_std.id,
                "tz": "Africa/Addis_Ababa",
            }
        )

        # Create a salary rule for our tests and add it to the salary structure
        cls.test_rule = cls.Rule.create(
            {
                "name": "Test rule",
                "code": "TEST",
                "category_id": cls.rule_category.id,
                "sequence": 5,
                "amount_select": "code",
                "amount_python_compute": "result=contract.wage",
            }
        )
        cls.payroll_structure.write({"rule_ids": [(4, cls.test_rule.id)]})

        # Payroll user
        cls.payroll_user = new_test_user(
            cls.env,
            login="pu",
            groups="base.group_user,payroll.group_payroll_user",
            name="Payroll User",
            email="pu@example.com",
        )

        # Creaet a policy group
        cls.default_policy_group = cls.PolicyGroup.create(
            {"name": "default policy group"}
        )

        # Create a Presence Policy
        cls.presence_policy = cls.PresencePolicy.create(
            {"name": "POLICY1", "date": date(2000, 1, 1)}
        )
        cls.PresencePolicyLine.create(
            {
                "name": "Presence Line - Normal workday",
                "code": "PL1",
                "type": "normal",
                "active_after": 0.0,
                "duration": 8.0 * 60,
                "policy_id": cls.presence_policy.id,
            }
        )
        cls.PresencePolicyLine.create(
            {
                "name": "Presence Line - Holiday",
                "code": "HOL",
                "type": "holiday",
                "active_after": 0.0,
                "duration": 8.0 * 60,
                "rate": 2.0,
                "policy_id": cls.presence_policy.id,
            }
        )
        cls.restday_presence_line = cls.PresencePolicyLine.create(
            {
                "name": "Presence Line - Rest day",
                "code": "RST",
                "type": "restday",
                "active_after": 0.0,
                "duration": 8.0 * 60,
                "rate": 1.0,
                "policy_id": cls.presence_policy.id,
            }
        )

        # I put the presence policy in the policy group
        cls.default_policy_group.presence_policy_ids = [(4, cls.presence_policy.id)]

    def create_contract(self, start, end, employee, wage, name=False):
        # Odoo 19 replaced ``hr.contract`` with ``hr.version``. Every employee
        # owns a version dated today, so the test contract is created with a
        # backdated ``date_version`` (unique per employee) and its own start
        # date; otherwise the computed ``date_end`` would be capped by the
        # employee's default version and the contract would look historical.
        return self.Contract.create(
            {
                "name": name if name else f"Contract for {employee.name}",
                "employee_id": employee.id,
                "date_version": start,
                "contract_date_start": start,
                "contract_date_end": end,
                "wage": wage,
                "struct_id": self.payroll_structure.id,
                "resource_calendar_id": self.resource_calendar_std.id,
                "policy_group_id": self.default_policy_group.id,
            }
        )

    def create_payslip(self, start, end, employee, user=False):
        if user is not False:
            Payslip = self.HrPayslip.with_user(user)
        else:
            Payslip = self.HrPayslip

        return Payslip.create(
            {
                "name": f"Payslip of {employee.name}",
                "employee_id": employee.id,
                "date_from": start,
                "date_to": end,
            }
        )

    def localize_dt(self, dt, tz, reverse=False):
        """
        Localize naive dt from database (UTC) to timzezone tz. If reverse is True
        a naive dt that is in timezone tz is converted to naive dt for storage in db.
        """

        local_tz = timezone(tz)
        if not reverse:
            res = utc.localize(dt, is_dst=False).astimezone(local_tz)
        else:
            res = (
                local_tz.localize(dt, is_dst=False).astimezone(utc).replace(tzinfo=None)
            )
        return res
