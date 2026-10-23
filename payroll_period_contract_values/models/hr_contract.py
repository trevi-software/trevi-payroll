# Copyright (C) 2021 Trevi Software (https://trevi.et)
# Copyright (C) 2013 Michael Telahun Makonnen <mmakonnen@gmail.com>.
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import api, fields, models


class HrVersion(models.Model):
    """In Odoo 19 ``hr_contract`` was merged into ``hr`` and ``hr.contract``
    was renamed ``hr.version``, so the payroll period schedule default is set
    on the employee's contract version.
    """

    _inherit = "hr.version"

    @api.model
    def _get_pay_sched(self):
        iv = self.get_latest_initial_values()
        if iv is not None and iv.pay_sched_id:
            return iv.pay_sched_id.id
        return False

    pps_id = fields.Many2one(default=lambda self: self._get_pay_sched())
