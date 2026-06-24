from odoo import fields, models


class PayrollProcessor(models.Model):

    _name = "payroll.processor"
    _description = "Payroll Processor"

    enabled = fields.Boolean(
        copy=False,
        help="""* If the processor should process payslips the status should be \'Enabled\'.
        \n* If the processor should NOT process payslips the status should be \'Disabled\'.""",
    )

    name = fields.Char(readonly="enabled == True")
