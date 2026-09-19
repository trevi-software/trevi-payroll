# Copyright (C) 2026 Trevi Software (https://trevi.et)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import fields, models


class PayrollSalaryCode(models.Model):
    _name = "payroll.salary.code"
    _description = "Payroll Salary Code"
    _order = "code"

    _sql_constraints = [
        ("code_uniq", "unique(code)", "The code must be unique."),
    ]

    code = fields.Char(
        required=True,
        index=True,
        help="A unique salary code",
    )
    description = fields.Char(
        help="A short description of what the code represents.",
    )
    contract_ids = fields.One2many(
        string="Contracts",
        comodel_name="hr.contract",
        inverse_name="payroll_salary_code",
        help="Contracts the salary code is assigned to.",
    )
