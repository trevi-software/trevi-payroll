from odoo import fields, models, _


class ResCompany(models.Model):

    _inherit="res.company"

    # should be in-sync with field in hr.employee -> payroll_payment_processor
    payroll_payment_processor = fields.Selection(
        selection=[
                ('none', _("None")),
                ('manual', _("Manual")),
        ],
        default='none',
        config_parameter="payroll.payroll_payment_processor",
        string="Payroll Payment Processor",
        help="The payment processor to use when processing a payslip for payment.",
    )