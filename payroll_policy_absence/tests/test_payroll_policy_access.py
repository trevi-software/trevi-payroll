# Copyright (C) 2021 TREVI Software
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from datetime import date

from odoo.exceptions import AccessError
from odoo.tests import Form
from odoo.tests.common import TransactionCase, new_test_user


class TestPolicyAccess(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.Policy = cls.env["hr.policy.absence"]
        cls.PolicyLine = cls.env["hr.policy.line.absence"]
        cls.LeaveType = cls.env["hr.leave.type"]
        cls.leave_type = cls.env.ref("hr_holidays.leave_type_paid_time_off")
        cls.policy = cls.Policy.create({"name": "POLICY1", "date": date.today()})
        cls.line = cls.PolicyLine.create(
            {
                "name": "Line1",
                "code": "L1",
                "type": "paid",
                "holiday_status_id": cls.leave_type.id,
                "policy_id": cls.policy.id,
            }
        )
        # Payroll Manager user
        cls.userPM = new_test_user(
            cls.env,
            login="pm",
            groups="base.group_user,payroll.group_payroll_manager",
            name="Payroll manager",
            email="pm@example.com",
        )
        # Payroll user
        cls.userPU = new_test_user(
            cls.env,
            login="pu",
            groups="base.group_user,payroll.group_payroll_user",
            name="Payroll manager",
            email="pu@example.com",
        )
        # HR Manager
        cls.userHRM = new_test_user(
            cls.env,
            login="hrm",
            groups="base.group_user,hr.group_hr_manager",
            name="Payroll manager",
            email="hrm@example.com",
        )

    def test_hrm_access(self):
        """HRM only has read access"""

        # Create fails
        with self.assertRaises(AccessError):
            self.Policy.with_user(self.userHRM).create(
                {"name": "POLICY2", "date": date.today()}
            )
        with self.assertRaises(AccessError):
            self.PolicyLine.with_user(self.userHRM).create(
                {
                    "name": "line2",
                    "code": "L2",
                    "type": "paid",
                    "holiday_status_id": self.leave_type.id,
                }
            )
        # Unlink fails
        with self.assertRaises(AccessError):
            self.policy.with_user(self.userHRM).unlink()
        with self.assertRaises(AccessError):
            self.line.with_user(self.userHRM).unlink()
        # Read succeeds
        policy_data = (
            self.Policy.with_user(self.userHRM)
            .browse(self.policy.id)
            .read(["name", "date"])
        )
        self.assertEqual(policy_data[0]["name"], "POLICY1")
        line_data = (
            self.PolicyLine.with_user(self.userHRM)
            .browse(self.line.id)
            .read(["name", "code"])
        )
        self.assertEqual(line_data[0]["name"], "Line1")
        self.assertEqual(line_data[0]["code"], "L1")
        # Write fails
        with self.assertRaises(AccessError):
            self.Policy.with_user(self.userHRM).browse(self.policy.id).write(
                {"name": "POLICY3"}
            )
        with self.assertRaises(AccessError):
            self.PolicyLine.with_user(self.userHRM).browse(self.line.id).write(
                {"name": "line3"}
            )

    def test_payroll_user_access(self):
        """Payroll User only has read access"""

        # Create fails
        with self.assertRaises(AccessError):
            self.Policy.with_user(self.userPU).create(
                {"name": "POL2", "date": date.today()}
            )
        with self.assertRaises(AccessError):
            self.PolicyLine.with_user(self.userPU).create(
                {
                    "name": "line2",
                    "code": "L2",
                    "type": "paid",
                    "holiday_status_id": self.leave_type.id,
                }
            )
        # Unlink fails
        with self.assertRaises(AccessError):
            self.policy.with_user(self.userPU).unlink()
        with self.assertRaises(AccessError):
            self.line.with_user(self.userPU).unlink()
        # Read succeeds
        policy_data = (
            self.Policy.with_user(self.userPU).browse(self.policy.id).read(["name"])
        )
        self.assertEqual(policy_data[0]["name"], "POLICY1")
        line_data = (
            self.PolicyLine.with_user(self.userPU)
            .browse(self.line.id)
            .read(["name", "code"])
        )
        self.assertEqual(line_data[0]["name"], "Line1")
        self.assertEqual(line_data[0]["code"], "L1")
        # Write fails
        with self.assertRaises(AccessError):
            self.Policy.with_user(self.userPU).browse(self.policy.id).write(
                {"name": "POL3"}
            )
        with self.assertRaises(AccessError):
            self.PolicyLine.with_user(self.userPU).browse(self.line.id).write(
                {"name": "line3"}
            )

    def test_payroll_manager_access(self):
        """Payroll Manager has complete access"""

        # Read succeeds
        policy_data = (
            self.Policy.with_user(self.userPM).browse(self.policy.id).read(["name"])
        )
        self.assertEqual(policy_data[0]["name"], "POLICY1")
        line_data = (
            self.PolicyLine.with_user(self.userPM)
            .browse(self.line.id)
            .read(["name", "code"])
        )
        self.assertEqual(line_data[0]["name"], "Line1")
        self.assertEqual(line_data[0]["code"], "L1")
        # Write succeeds
        self.Policy.with_user(self.userPM).browse(self.policy.id).write({"name": "XX"})
        self.PolicyLine.with_user(self.userPM).browse(self.line.id).write(
            {"name": "XX"}
        )
        self.assertEqual(self.policy.name, "XX")
        self.assertEqual(self.line.name, "XX")
        # Create/Unlink succeeds
        pol = self.Policy.with_user(self.userPM).create(
            {"name": "Policy test pm", "date": date.today()}
        )
        pol.unlink()
        line = self.PolicyLine.with_user(self.userPM).create(
            {
                "name": "line test pm",
                "code": "A",
                "type": "paid",
                "holiday_status_id": self.leave_type.id,
            }
        )
        line.unlink()

    def test_onchange_holiday_generates_name_and_code(self):
        """Selecting a leave type fills the name and derives a default code"""

        leave = self.LeaveType.create({"name": "Compassionate"})
        with Form(self.PolicyLine) as form:
            form.holiday_status_id = leave
            form.type = "paid"
            self.assertEqual(form.name, "Compassionate")
            self.assertEqual(form.code, "COMPASSI")

    def test_onchange_holiday_keeps_existing_code(self):
        """An already set code is not overwritten by the onchange"""

        leave = self.LeaveType.create({"name": "Compassionate"})
        with Form(self.PolicyLine) as form:
            form.code = "KEEP"
            form.holiday_status_id = leave
            form.type = "paid"
            self.assertEqual(form.name, "Compassionate")
            self.assertEqual(form.code, "KEEP")
