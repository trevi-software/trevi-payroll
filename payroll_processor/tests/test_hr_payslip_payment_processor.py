# Copyright (C) 2024 Trevi Software (https://trevi.et)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo.addons.payroll.tests.common import TestPayslipBase


class TestPayslipPaymentProcessor(TestPayslipBase):
    """A server-side created payslip must honour the employee's processor.

    ``onchange_employee_id`` only runs in the form view, so an import or an RPC
    call that passes ``employee_id`` but no processor has to be handled at
    ``create`` time as well - otherwise it would default to the company's
    choice and could be auto-paid by ``action_payslip_payment``.
    """

    def setUp(self):
        super().setUp()
        self.Payslip = self.env["hr.payslip"]
        # The company pays automatically ...
        self.env.company.payroll_payment_processor = "none"
        # ... but Richard wants to be paid by hand.
        self.richard_emp.payroll_payment_processor = "manual"

    def test_create_copies_employee_processor(self):
        """An import/RPC create with no processor takes the employee's choice."""
        slip = self.Payslip.create({"employee_id": self.richard_emp.id})
        self.assertEqual(slip.payroll_payment_processor, "manual")

    def test_create_keeps_explicit_processor(self):
        """An explicitly supplied processor is not overwritten."""
        slip = self.Payslip.create(
            {
                "employee_id": self.richard_emp.id,
                "payroll_payment_processor": "none",
            }
        )
        self.assertEqual(slip.payroll_payment_processor, "none")

    def test_create_employee_overrides_company(self):
        """The employee's choice wins over the company default."""
        self.env.company.payroll_payment_processor = "manual"
        self.richard_emp.payroll_payment_processor = "none"
        slip = self.Payslip.create({"employee_id": self.richard_emp.id})
        self.assertEqual(slip.payroll_payment_processor, "none")

    def test_action_payslip_payment_respects_employee_processor(self):
        """A slip for a 'manual' employee is left for manual payment."""
        slip = self.Payslip.create({"employee_id": self.richard_emp.id})
        slip.action_payslip_payment()
        self.assertNotEqual(
            slip.state,
            "done",
            "The payslip must not be marked done when the employee is paid "
            "manually",
        )

    def test_action_payslip_payment_pays_none(self):
        """A slip for a 'none' employee is marked done."""
        self.richard_emp.payroll_payment_processor = "none"
        slip = self.Payslip.create({"employee_id": self.richard_emp.id})
        slip.action_payslip_payment()
        self.assertEqual(slip.state, "done")
