import logging

from odoo import api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class HrPayslip(models.Model):
    _inherit = "hr.payslip"

    # should be in-sync with the payroll_payment_processor field in
    # res.company and hr.employee
    payroll_payment_processor = fields.Selection(
        selection_add=[
            ("mpesa_et", "Safaricom M-PESA (ET)"),
        ]
    )

    paid_mpesa = fields.Boolean(
        string="M-PESA Payment",
        readonly=True,
        copy=False,
    )

    mpesa_et_payment_response = fields.Many2one(
        "payslip.mpesa_et.response", string="M-Pesa (ET) API Response"
    )

    mpesa_et_payment_result = fields.Many2one(
        "payslip.mpesa_et.result", string="M-Pesa (ET) Transaction Result"
    )

    @api.onchange("paid_mpesa")
    def onchange_paid_mpesa(self):
        self.paid = self.paid_mpesa

    def refund_sheet(self):
        return super().refund_sheet()

    def action_payslip_cancel(self):
        if self.filtered(lambda slip: slip.paid_mpesa):
            raise ValidationError(
                self.env._(
                    "Cannot cancel a payslip that is already paid through M-Pesa."
                )
            )

        return super().action_payslip_cancel()

    def unlink(self):
        if self.filtered(lambda slip: slip.paid_mpesa):
            # An M-PESA payout cannot be reversed, so deleting an already paid
            # payslip would lose the payout record.
            raise ValidationError(  # pylint: disable=no-raise-unlink
                self.env._(
                    "Cannot delete a payslip that is already paid through M-Pesa."
                )
            )

        return super().unlink()

    def _mpesa_et_net_amount(self):
        """Return the amount to disburse for this payslip.

        payroll carries no net-pay field, so the net is the total of the lines
        computed from the structure's ``NET`` salary rule - the same convention
        ``payroll_register`` uses to read a payslip's net.
        """
        self.ensure_one()
        net_lines = self.line_ids.filtered(
            lambda line: line.salary_rule_id.code == "NET"
        )
        return sum(net_lines.mapped("total"))

    def action_payslip_payment(self):
        for slip in self:
            if slip.paid:
                # Already paid: never send a second payout for the same payslip.
                continue
            if slip.payroll_payment_processor == "mpesa_et":
                gw = self.env["payroll.processor.mpesa_et"].search(
                    [("enabled", "=", True)]
                )
                if len(gw) == 0:
                    _logger.warning(
                        "Unable to find an appropriate M-PESA processor "
                        "for payslip %s (%s)",
                        slip.name,
                        slip.number,
                    )
                    continue
                authorization = gw[0].get_authorization(gw[0].authenticate())
                try:
                    res = gw[0].payout(
                        authorization,
                        slip.employee_id.mpesa_phone,
                        slip._mpesa_et_net_amount(),
                        slip.name,
                    )
                except Exception as e:
                    _logger.warning(
                        "An error occurred during M-PESA payment for %s (%s):\n%s",
                        slip.name,
                        slip.number,
                        str(e),
                    )
                else:
                    res = gw[0].translate_payment_response(res)
                    res["payslip_id"] = slip.id
                    slip.mpesa_et_payment_response = self.env[
                        "payslip.mpesa_et.response"
                    ].create(res)

        return super().action_payslip_payment()
