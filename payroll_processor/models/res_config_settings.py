from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    payroll_payment_processor = fields.Selection(
        related='company_id.payroll_payment_processor',
        string="Default Payroll Payment Processor",
        readonly=False,
        default_model="res_company"
    )