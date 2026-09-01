# Copyright (C) 2022 Trevi Software (https://trevi.et)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import api, models


class HrPayslip(models.Model):
    _inherit = "hr.payslip"

    @api.model
    def get_worked_day_lines(self, contracts, date_from, date_to):
        """
        @param contracts: Browse record of contracts
        @return: returns a list of dict containing the input that should be
        applied for the given contract between date_from and date_to
        """

        res = super().get_worked_day_lines(contracts, date_from, date_to)

        leave_types = self.env["hr.leave.type"].search([])

        # Payroll names each leave worked_days record after the leave type but
        # codes it after that type's work entry type, falling back to 'GLOBAL'.
        # Use the leave type's own code instead.
        for r in res:
            if r["code"] == "WORK100":
                continue
            leave_type = leave_types.filtered(lambda lvt, r=r: lvt.name == r["name"])[
                :1
            ]
            if leave_type.code:
                r["code"] = leave_type.code

        return res
