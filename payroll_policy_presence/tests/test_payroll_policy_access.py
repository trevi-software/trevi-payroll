# Copyright (C) 2021 TREVI Software
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from datetime import date

from odoo.exceptions import AccessError
from odoo.tests import common, new_test_user


class TestPolicyAccess(common.TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.Policy = cls.env["hr.policy.presence"]
        cls.PolicyLine = cls.env["hr.policy.line.presence"]
        cls.policy = cls.Policy.create({"name": "POLICY1", "date": date.today()})
        cls.line = cls.PolicyLine.create(
            {
                "name": "Line1",
                "code": "L1",
                "type": "normal",
                "active_after": 8.0,
                "duration": 1.0,
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

    def _line_vals(self, name="line2", code="L2"):
        """Return a complete, valid set of values for a policy line.

        The values are valid on purpose: the create permission check must be
        the reason the call fails (or succeeds), not a missing required field.
        """
        return {
            "name": name,
            "code": code,
            "type": "normal",
            "active_after": 8.0,
            "duration": 1.0,
            "policy_id": self.policy.id,
        }

    def test_hrm_access(self):
        """HRM only has read access"""

        # Create policy fails
        with self.assertRaises(AccessError):
            self.Policy.with_user(self.userHRM).create(
                {"name": "POLICY2", "date": date.today()}
            )
        # Create line fails
        with self.assertRaises(AccessError):
            self.PolicyLine.with_user(self.userHRM).create(self._line_vals())
        # Unlink policy fails
        with self.assertRaises(AccessError):
            self.policy.with_user(self.userHRM).unlink()
        # Unlink line fails
        with self.assertRaises(AccessError):
            self.line.with_user(self.userHRM).unlink()
        # Read policy succeeds
        self.assertEqual(
            self.Policy.with_user(self.userHRM)
            .browse(self.policy.id)
            .read(["name"])[0]["name"],
            "POLICY1",
        )
        # Read line succeeds
        self.assertEqual(
            self.PolicyLine.with_user(self.userHRM)
            .browse(self.line.id)
            .read(["name"])[0]["name"],
            "Line1",
        )
        # Write policy fails
        with self.assertRaises(AccessError):
            self.policy.with_user(self.userHRM).write({"name": "POLICY3"})
        # Write line fails
        with self.assertRaises(AccessError):
            self.line.with_user(self.userHRM).write({"name": "line3"})

    def test_payroll_user_access(self):
        """Payroll User only has read access"""

        # Create policy fails
        with self.assertRaises(AccessError):
            self.Policy.with_user(self.userPU).create(
                {"name": "POL2", "date": date.today()}
            )
        # Create line fails
        with self.assertRaises(AccessError):
            self.PolicyLine.with_user(self.userPU).create(self._line_vals())
        # Unlink policy fails
        with self.assertRaises(AccessError):
            self.policy.with_user(self.userPU).unlink()
        # Unlink line fails
        with self.assertRaises(AccessError):
            self.line.with_user(self.userPU).unlink()
        # Read policy succeeds
        self.assertEqual(
            self.Policy.with_user(self.userPU)
            .browse(self.policy.id)
            .read(["name"])[0]["name"],
            "POLICY1",
        )
        # Read line succeeds
        self.assertEqual(
            self.PolicyLine.with_user(self.userPU)
            .browse(self.line.id)
            .read(["name"])[0]["name"],
            "Line1",
        )
        # Write policy fails
        with self.assertRaises(AccessError):
            self.policy.with_user(self.userPU).write({"name": "POL3"})
        # Write line fails
        with self.assertRaises(AccessError):
            self.line.with_user(self.userPU).write({"name": "line3"})

    def test_payroll_manager_access(self):
        """Payroll Manager has complete access"""

        # Read policy succeeds
        self.assertEqual(
            self.Policy.with_user(self.userPM)
            .browse(self.policy.id)
            .read(["name"])[0]["name"],
            "POLICY1",
        )
        # Read line succeeds
        self.assertEqual(
            self.PolicyLine.with_user(self.userPM)
            .browse(self.line.id)
            .read(["name"])[0]["name"],
            "Line1",
        )
        # Write policy succeeds
        self.policy.with_user(self.userPM).write({"name": "XX"})
        self.assertEqual(
            self.Policy.with_user(self.userPM).browse(self.policy.id).name, "XX"
        )
        # Write line succeeds
        self.line.with_user(self.userPM).write({"name": "XX"})
        self.assertEqual(
            self.PolicyLine.with_user(self.userPM).browse(self.line.id).name, "XX"
        )
        # Create/Unlink policy succeeds
        pol = self.Policy.with_user(self.userPM).create(
            {"name": "Policy test pm", "date": date.today()}
        )
        self.assertTrue(pol.exists())
        pol.unlink()
        self.assertFalse(pol.exists())
        # Create/Unlink line succeeds
        line = self.PolicyLine.with_user(self.userPM).create(
            self._line_vals(name="line test pm", code="A")
        )
        self.assertTrue(line.exists())
        line.unlink()
        self.assertFalse(line.exists())
