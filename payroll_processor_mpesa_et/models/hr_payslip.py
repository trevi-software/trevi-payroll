import logging

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class HrPayslip(models.Model):

     _inherit = "hr.payslip"

     # should be in-sync with field in res.company and hr.employee -> payroll_payment_processor
     payroll_payment_processor = fields.Selection(
          selection_add = [
               ('mpesa_et', "Safaricom M-PESA (ET)"),
          ]
     )
    
     paid_mpesa = fields.Boolean(
          string="M-PESA Payment",
          readonly=True,
          copy=False,
     )

     mpesa_et_payment_response = fields.Many2one("payslip.mpesa_et.response", string="M-Pesa (ET) API Response")

     mpesa_et_payment_result = fields.Many2one("payslip.mpesa_et.result", string="M-Pesa (ET) Transaction Result")

     @api.onchange("paid_mpesa")
     def onchange_paid_mpesa(self):
          self.paid = self.paid_mpesa

     def refund_sheet(self):
          
          return super(HrPayslip, self).refund_sheet()
     
     def payslip_cancel(self):
     
          if self.filtered(lambda slip: slip.paid_mpesa):
               raise ValidationError(_("Cannot cancel a payslip that is already paid through M-Pesa."))
     
          return super(HrPayslip, self).payslip_cancel()

     def unlink(self):
     
          if self.filtered(lambda slip: slip.paid_mpesa):
               raise ValidationError(_("Cannot delete a payslip that is already paid through M-Pesa."))

          return super(HrPayslip, self).unlink()

     def action_payslip_payment(self):
               
          for slip in self:
               if slip.payroll_payment_processor == 'mpesa_et':
                    gw = self.env["payroll.processor.mpesa_et"].search([("enabled", "=", True)]).browse()
                    if len(gw) == 0:
                         _logger.warning(
                              "Unable to find an appropriate M-PESA processor for payslip %s (%s)",
                              slip.name,
                              slip.number
                         )
                         continue
                    authorization = gw[0].get_authorization(gw[0].authenticate())
                    try:
                         res = gw[0].payout(authorization, slip.employee_id.mpesa_phone, slip.net_amount, slip.name)
                    except Exception as e:
                         _logger.warning(
                              "An error occurred during M-PESA payslip payment processing for %s (%s): %s",
                              slip.name,
                              slip.number,
                              e.message
                         )
                    else:
                         res = gw[0].translate_payment_response(res)
                         res["payslip_id"] = slip.id
                         slip.mpesa_et_payment_response = self.env["payslip.mpesa_et.response"].create(res)


          return super(HrPayslip, self).action_payslip_payment()
