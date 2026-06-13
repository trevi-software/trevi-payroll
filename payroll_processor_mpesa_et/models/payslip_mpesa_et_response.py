from odoo import fields, models


class PayslipMpesaEtResponse(models.Model):

    _name = "payslip.mpesa_et.response"
    _description = "Safaricom Ethiopia M-PESA Payslip Integration Response"
    _order = "ok_conversation error_request"

    payslip_id = fields.Many2one("hr.payslip", string="Payslip", required=True)

    ok_conversation = fields.Char(string="Conversation ID", readonly=True)

    ok_originator_conversation = fields.Char(string="Originator Conversation ID", readonly=True)

    ok_response_code = fields.Char(string="Payment Response Code", readonly=True)

    ok_response_desc = fields.Char(string="Payment Response Description", readonly=True)

    error_request = fields.Char(string="Request ID", readonly=True)

    error_code = fields.Char(readonly=True)

    error_msg = fields.Char(string="Error Message", readonly=True)

    raw = fields.Text("Raw Response", readonly=True)
