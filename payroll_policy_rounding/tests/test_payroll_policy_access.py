# Copyright (C) 2021 TREVI Software
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from datetime import date

from odoo.exceptions import AccessError

from . import common


class TestPolicyAccess(common.TestPolicyCommon):
    def test_hrm_access(self):
        """HRM only has read access"""

        # Create fails
        with self.assertRaises(AccessError):
            self.Policy.with_user(self.userHRM).create(
                {"name": "POLICY2", "date": date.today(), "tz": "UTC"}
            )
        with self.assertRaises(AccessError):
            self.PolicyLine.with_user(self.userHRM).create(
                {"attendance_type": "in", "round_type": "down"}
            )
        # Unlink fails
        with self.assertRaises(AccessError):
            self.policy.with_user(self.userHRM).unlink()
        with self.assertRaises(AccessError):
            self.line.with_user(self.userHRM).unlink()
        # Read succeeds (read a field to actually exercise read access)
        try:
            self.Policy.with_user(self.userHRM).browse(self.policy.id).read(["name"])
        except AccessError:
            self.fail("Caught an unexpected exception reading hr.policy.rounding")
        try:
            self.PolicyLine.with_user(self.userHRM).browse(self.line.id).read(
                ["attendance_type"]
            )
        except AccessError:
            self.fail("Caught an unexpected exception reading hr.policy.line.rounding")
        # Write fails
        with self.assertRaises(AccessError):
            self.Policy.with_user(self.userHRM).browse(self.policy.id).write(
                {"name": "POLICY3"}
            )
        with self.assertRaises(AccessError):
            self.PolicyLine.with_user(self.userHRM).browse(self.line.id).write(
                {"round_type": "down"}
            )

    def test_payroll_user_access(self):
        """Payroll User only has read access"""

        # Create fails
        with self.assertRaises(AccessError):
            self.Policy.with_user(self.userPU).create(
                {"name": "POL2", "date": date.today(), "tz": "UTC"}
            )
        with self.assertRaises(AccessError):
            self.PolicyLine.with_user(self.userPU).create(
                {"attendance_type": "in", "round_type": "down"}
            )
        # Unlink fails
        with self.assertRaises(AccessError):
            self.policy.with_user(self.userPU).unlink()
        with self.assertRaises(AccessError):
            self.line.with_user(self.userPU).unlink()
        # Read succeeds (read a field to actually exercise read access)
        try:
            self.Policy.with_user(self.userPU).browse(self.policy.id).read(["name"])
        except AccessError:
            self.fail("Caught an unexpected exception reading hr.policy.rounding")
        try:
            self.PolicyLine.with_user(self.userPU).browse(self.line.id).read(
                ["attendance_type"]
            )
        except AccessError:
            self.fail("Caught an unexpected exception reading hr.policy.line.rounding")
        # Write fails
        with self.assertRaises(AccessError):
            self.Policy.with_user(self.userPU).browse(self.policy.id).write(
                {"name": "POL3"}
            )
        with self.assertRaises(AccessError):
            self.PolicyLine.with_user(self.userPU).browse(self.line.id).write(
                {"round_type": "down"}
            )

    def test_payroll_manager_access(self):
        """Payroll Manager has complete access"""

        # Read succeeds
        try:
            self.Policy.with_user(self.userPM).browse(self.policy.id).read(["name"])
        except AccessError:
            self.fail("Caught an unexpected exception reading hr.policy.rounding")
        try:
            self.PolicyLine.with_user(self.userPM).browse(self.line.id).read(
                ["attendance_type"]
            )
        except AccessError:
            self.fail("Caught an unexpected exception reading hr.policy.line.rounding")
        # Write succeeds
        try:
            self.Policy.with_user(self.userPM).browse(self.policy.id).write(
                {"name": "XXX"}
            )
        except AccessError:
            self.fail("Caught an unexpected exception writing hr.policy.rounding")
        try:
            self.PolicyLine.with_user(self.userPM).browse(self.line.id).write(
                {"round_type": "down"}
            )
        except AccessError:
            self.fail("Caught an unexpected exception writing hr.policy.line.rounding")
        # Create/Unlink succeeds
        try:
            pol = self.Policy.with_user(self.userPM).create(
                {"name": "Policy test pm", "date": date.today(), "tz": "UTC"}
            )
            pol.unlink()
        except AccessError:
            self.fail(
                "Caught unexpected exception creating/unlinking hr.policy.rounding"
            )
        try:
            line = self.PolicyLine.with_user(self.userPM).create(
                {
                    "attendance_type": "in",
                    "round_type": "avg",
                }
            )
            line.unlink()
        except AccessError:
            self.fail(
                "Caught unexpected exception creating/unlinking hr.policy.line.rounding"
            )
