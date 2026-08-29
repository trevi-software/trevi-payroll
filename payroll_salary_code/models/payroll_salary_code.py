# Copyright (C) 2025 Trevi Software (https://trevi.et)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import fields, models


class PayrollSalaryCode(models.Model):
    _name = "payroll.salary.code"
    _description = "Payroll Salary Code"
    _order = "code"

    code = fields.Char(
        required=True,
        index=True,
        help="A unique salary code",
    )
    description = fields.Char(
        help="A short description of what the code represents.",
    )

    _sql_constraints = [
        ("code_uniq", "unique(code)", "The code must be unique."),
    ]
