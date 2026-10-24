# Copyright (C) 2026 Trevi Software (https://trevi.et)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
"""Tests for the M-PESA (ET) behaviour of hr.payslip."""

from unittest.mock import patch

from odoo.exceptions import ValidationError

from odoo.addons.payroll.tests.common import TestPayslipBase

MPESA_PHONE = "+251911223344"


class TestMpesaEtPayslip(TestPayslipBase):
    def setUp(self):
        super().setUp()
        self.Payslip = self.env["hr.payslip"]
        self.Processor = self.env["payroll.processor.mpesa_et"]
        self.Response = self.env["payslip.mpesa_et.response"]
        self.richard_emp.write({"mpesa_phone": MPESA_PHONE})

    def _create_payslip(self, processor="mpesa_et"):
        slip = self.Payslip.create(
            {"name": "Payslip of Richard", "employee_id": self.richard_emp.id}
        )
        slip.onchange_employee()
        slip.compute_sheet()
        slip.payroll_payment_processor = processor
        return slip

    def _draft_payslip(self, processor="mpesa_et"):
        """A payslip that payroll itself still considers deletable."""
        return self.Payslip.create(
            {
                "name": "Draft payslip",
                "employee_id": self.richard_emp.id,
                "payroll_payment_processor": processor,
            }
        )

    def _create_processor(self):
        return self.Processor.create(
            {
                "name": "Safaricom ET",
                "enabled": True,
                "consumer_key": "key",
                "consumer_secret": "secret",
                "party_a": "123456",
                "api_user": "user",
                "api_password": "pass",
            }
        )

    def test_mpesa_et_is_offered_by_every_processor_field(self):
        """res.company, hr.employee and hr.payslip must offer the same choices."""
        for model in ("res.company", "hr.employee", "hr.payslip"):
            field = self.env[model]._fields["payroll_payment_processor"]
            keys = [key for key, _label in field.selection if isinstance(key, str)]
            self.assertIn("mpesa_et", keys, f"{model} offers the M-PESA processor")

    def test_net_amount_is_the_total_of_the_net_rule_lines(self):
        slip = self._create_payslip()
        net_lines = slip.line_ids.filtered(
            lambda line: line.salary_rule_id.code == "NET"
        )
        self.assertTrue(net_lines, "The payslip has a NET salary rule line")
        self.assertAlmostEqual(
            sum(net_lines.mapped("total")), slip._mpesa_et_net_amount()
        )
        self.assertGreater(slip._mpesa_et_net_amount(), 0.0)

    def test_onchange_paid_mpesa_marks_the_payslip_paid(self):
        slip = self._create_payslip()
        slip.paid_mpesa = True
        slip.onchange_paid_mpesa()
        self.assertTrue(slip.paid)

    def test_unlink_is_blocked_for_a_payslip_paid_through_mpesa(self):
        slip = self._draft_payslip()
        slip.paid_mpesa = True
        with self.assertRaises(ValidationError):
            slip.unlink()
        self.assertTrue(slip.exists(), "The paid payslip still exists")

    def test_unlink_is_allowed_for_an_unpaid_payslip(self):
        slip = self._draft_payslip()
        slip.unlink()
        self.assertFalse(slip.exists())

    def test_cancel_is_blocked_for_a_payslip_paid_through_mpesa(self):
        slip = self._create_payslip()
        slip.paid_mpesa = True
        with self.assertRaises(ValidationError):
            slip.action_payslip_cancel()

    def test_payment_without_an_enabled_processor_sends_nothing(self):
        slip = self._create_payslip()
        slip.action_payslip_payment()
        self.assertFalse(slip.mpesa_et_payment_response)
        self.assertEqual(0, self.Response.search_count([("payslip_id", "=", slip.id)]))

    def test_payment_sends_the_net_amount_to_the_employee_phone(self):
        processor = self._create_processor()
        self.assertTrue(
            self.Processor.search_count([("enabled", "=", True)]),
            "the enabled processor is visible to the acting user",
        )
        slip = self._create_payslip()
        api_response = {
            "ConversationId": "conv-9",
            "OriginatorConversationID": "orig-9",
            "ResponseCode": "0",
            "ResponseDescription": "Accepted",
        }
        model = type(processor)
        with (
            patch.object(model, "authenticate", return_value={"access_token": "tok"}),
            patch.object(model, "get_authorization", return_value="Bearer tok"),
            patch.object(model, "payout", return_value=api_response) as payout_mock,
        ):
            slip.action_payslip_payment()

        self.assertTrue(payout_mock.called, "The payout API was called")
        _auth, phone, amount, remarks = payout_mock.call_args[0]
        self.assertEqual(MPESA_PHONE, phone)
        self.assertAlmostEqual(slip._mpesa_et_net_amount(), amount)
        self.assertEqual(slip.name, remarks)

        self.assertTrue(
            slip.mpesa_et_payment_response,
            "The API response was stored against the payslip",
        )
        self.assertEqual("conv-9", slip.mpesa_et_payment_response.ok_conversation)
        self.assertEqual(
            "orig-9", slip.mpesa_et_payment_response.ok_originator_conversation
        )
        self.assertEqual("0", slip.mpesa_et_payment_response.ok_response_code)

    def test_payment_does_not_send_a_second_payout_for_a_paid_payslip(self):
        processor = self._create_processor()
        slip = self._create_payslip()
        # both fields as the form sets them: paid_mpesa is the module's flag,
        # paid is payroll's own "already paid" flag that gates the payment
        slip.paid_mpesa = True
        slip.paid = True
        model = type(processor)
        with (
            patch.object(model, "authenticate", return_value={"access_token": "tok"}),
            patch.object(model, "get_authorization", return_value="Bearer tok"),
            patch.object(model, "payout") as payout_mock,
        ):
            slip.action_payslip_payment()
        self.assertFalse(payout_mock.called, "A paid payslip is not paid again")

    def test_payment_survives_an_api_error(self):
        processor = self._create_processor()
        slip = self._create_payslip()
        model = type(processor)
        with (
            patch.object(model, "authenticate", return_value={"access_token": "tok"}),
            patch.object(model, "get_authorization", return_value="Bearer tok"),
            patch.object(model, "payout", side_effect=Exception("connection reset")),
        ):
            slip.action_payslip_payment()
        self.assertFalse(
            slip.mpesa_et_payment_response,
            "No response is stored when the request failed",
        )
        self.assertEqual(0, self.Response.search_count([("payslip_id", "=", slip.id)]))
