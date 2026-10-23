# Copyright (C) 2026 Trevi Software (https://trevi.et)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import fields, models


class HrVersion(models.Model):
    """Odoo 19 merged ``hr.contract`` into ``hr``: the contract data lives on
    ``hr.version`` now."""

    _inherit = "hr.version"

    payroll_salary_code = fields.Many2one(
        comodel_name="payroll.salary.code",
        help="Salary code assigned to this contract.",
    )
