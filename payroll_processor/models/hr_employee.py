from odoo import api, fields, models, _


class HrEmployee(models.Model):

    _inherit = "hr.employee"

    @api.model
    def _get_payroll_payment_processor(self):
        """ Return the default payment method chosen by the company. """
        return self.env.company.payroll_payment_processor
    
    # should be in-sync with field in res.company -> payroll_payment_processor
    payroll_payment_processor = fields.Selection(
        selection=[
                ('none', _("None")),
                ('manual', _("Manual")),
        ],
        default=_get_payroll_payment_processor,
        string="Payroll Payment Processor",
        help="The payment processor to use when processing the employee's payslips for payment.",
        index=True,
        tracking=True,
    )
