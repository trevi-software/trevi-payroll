from odoo import fields, models


class PayslipMpesaEtResult(models.Model):

    _name = "payslip.mpesa_et.result"
    _description = "Safaricom Ethiopia M-PESA Payslip Integration Result"
    _order = "tx_completed_at desc"

    result_type = fields.Integer(readonly=True)

    result_code = fields.Integer(readonly=True)

    result_desc = fields.Text(readonly=True)

    originator_conversation = fields.Text(string="OriginatorConversationID", readonly=True)

    conversation = fields.Text(string="ConversationID", readonly=True)

    result_parameters = fields.Text(readonly=True)

    tx_amount = fields.Float(string="Transaction Amount", readonly=True)

    tx_receipt = fields.Text(string="Transaction Receipt", readonly=True)

    tx_completed_at = fields.Datetime(string="Transaction Completed At", readonly=True)

    recepient_public_name = fields.Char(readonly=True)
    
    recepient_is_registered_customer = fields.Boolean(readonly=True)

    raw = fields.Text("Raw Response", readonly=True)
