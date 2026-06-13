from odoo import fields, models
from odoo.exceptions import UserError
from odoo.tools.translate import _


class HrPayslipChangeState(models.TransientModel):

    _inherit = "hr.payslip.change.state"
    
    state = fields.Selection(
        selection_add=[
            ("payment", "Payment"),
            ("done",)
        ],
        help="""* When the payslip is created the status is \'Draft\'
        \n* If the payslip is under verification, the status is \'Waiting\'.
        \n* If the payslip is in the process of being paid, the status is \'Payment\'.
        \n* If the payslip is paid then status is set to \'Done\'.
        \n* When user cancel payslip the status is \'Rejected\'.""",
    )

    def change_state_confirm(self):
        record_ids = self.env.context.get("active_ids", False)
        payslip_obj = self.env["hr.payslip"]
        new_state = self.state
        records = payslip_obj.browse(record_ids)

        for rec in records:
            if new_state == 'payment':
                if not rec.paid:
                    rec.action_payslip_payment()

        return super(HrPayslipChangeState, self).change_state_confirm()