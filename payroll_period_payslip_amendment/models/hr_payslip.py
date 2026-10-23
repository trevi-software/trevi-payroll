# Copyright (C) 2022 Trevi Software (https://trevi.et)
# Copyright (C) 2013 Michael Telahun Makonnen <mmakonnen@gmail.com>.
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import api, models


class HrPayslip(models.Model):
    _inherit = "hr.payslip"

    @api.model
    def get_inputs(self, contracts, date_from, date_to):
        # Modify all the layers below to use the dates from the payroll period
        #
        # Only look at periods belonging to the payroll schedule(s) of the
        # contracts on the payslip. Several schedules can define periods that
        # overlap the same window; picking a period from another schedule would
        # widen the range to the wrong dates (e.g. a fortnightly period instead
        # of the monthly one) and silently drop an amendment dated at the end
        # of the real period.
        domain = [
            ("date_start", "<=", date_to),
            ("date_end", ">=", date_from),
        ]
        schedule_ids = contracts.mapped("pps_id")
        if schedule_ids:
            domain.append(("schedule_id", "in", schedule_ids.ids))
        periods = self.env["hr.payroll.period"].search(domain)
        if periods:
            date_from = periods[0].date_start
            date_to = periods[0].date_end

        return super().get_inputs(contracts, date_from, date_to)
