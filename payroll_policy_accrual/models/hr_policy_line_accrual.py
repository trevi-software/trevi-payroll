# Copyright (C) 2021 TREVI Software
# Copyright (C) 2013 Michael Telahun Makonnen <mmakonnen@gmail.com>.
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import calendar
from datetime import date

from odoo import api, fields, models
from odoo.exceptions import ValidationError

# Selection: day of month
SELECTION_DOM = [
    ("1", "1"),
    ("2", "2"),
    ("3", "3"),
    ("4", "4"),
    ("5", "5"),
    ("6", "6"),
    ("7", "7"),
    ("8", "8"),
    ("9", "9"),
    ("10", "10"),
    ("11", "11"),
    ("12", "12"),
    ("13", "13"),
    ("14", "14"),
    ("15", "15"),
    ("16", "16"),
    ("17", "17"),
    ("18", "18"),
    ("19", "19"),
    ("20", "20"),
    ("21", "21"),
    ("22", "22"),
    ("23", "23"),
    ("24", "24"),
    ("25", "25"),
    ("26", "26"),
    ("27", "27"),
    ("28", "28"),
    ("29", "29"),
    ("30", "30"),
    ("31", "31"),
]


class HrPolicyLine(models.Model):
    _name = "hr.policy.line.accrual"
    _description = "Accrual Policy Line"

    name = fields.Char(required=True)
    code = fields.Char(required=True)
    policy_id = fields.Many2one(
        comodel_name="hr.policy.accrual", string="Accrual Policy"
    )
    accrual_id = fields.Many2one(
        comodel_name="hr.accrual", string="Accrual Account", required=True
    )
    type = fields.Selection(
        selection=[
            ("standard", "Standard"),
            ("calendar", "Calendar"),
            ("hour", "Hour Based"),
        ],
        default="calendar",
        required=True,
    )
    balance_on_payslip = fields.Boolean(
        string="Display Balance on Pay Slip",
        help="The pay slip report must be modified to display this accrual for"
        "this setting to have any effect.",
    )
    calculation_frequency = fields.Selection(
        selection=[
            ("weekly", "Weekly"),
            ("monthly", "Monthly"),
            ("annual", "Annual"),
        ]
    )
    frequency_on_hire_date = fields.Boolean(string="Frequency Based on Hire Date")
    frequency_week_day = fields.Selection(
        string="Week Day",
        selection=[
            ("0", "Monday"),
            ("1", "Tuesday"),
            ("2", "Wednesday"),
            ("3", "Thursday"),
            ("4", "Friday"),
            ("5", "Saturday"),
            ("6", "Sunday"),
        ],
    )
    frequency_month_day = fields.Selection(
        string="Day of month",
        selection=SELECTION_DOM,
    )
    frequency_annual_month = fields.Selection(
        string="Month",
        selection=[
            ("1", "January"),
            ("2", "February"),
            ("3", "March"),
            ("4", "April"),
            ("5", "May"),
            ("6", "June"),
            ("7", "July"),
            ("8", "August"),
            ("9", "September"),
            ("10", "October"),
            ("11", "November"),
            ("12", "December"),
        ],
    )
    frequency_annual_day = fields.Selection(
        string="Day of Month",
        selection=SELECTION_DOM,
    )
    minimum_employed_days = fields.Integer()
    accrual_rate = fields.Float(help="The rate, in days, accrued per year.")
    accrual_rate_hour = fields.Float(
        string="Accrual Rate/Hour",
        default=0,
        help="The time accrued for every hour the employee works."
        " Available only when the policy type is Hour Based.",
    )
    accrual_rate_premium = fields.Float(
        help="The additional amount of time (beyond the standard rate)"
        "accrued per Premium Milestone of service."
    )
    accrual_rate_premium_minimum = fields.Integer(
        string="Months of Employment Before Premium",
        default=12,
        help="Minimum number of months the employee must be employed before"
        "the premium rate will start to accrue.",
    )
    accrual_rate_premium_milestone = fields.Integer(
        string="Accrual Premium Milestone",
        help="Number of milestone months after which the premium rate will be added.",
    )
    accrual_rate_max = fields.Float(
        string="Maximum Accrual Rate",
        required=True,
        default=0.0,
        help="The maximum amount of time that may accrue per year. Zero means the"
        "amount may keep increasing indefinitely.",
    )
    job_ids = fields.One2many(
        string="Jobs",
        comodel_name="hr.policy.line.accrual.job",
        inverse_name="policy_line_id",
        readonly=True,
        copy=False,
    )

    def pass_constraints(self, employee, dToday=None):
        self.ensure_one()
        if dToday is None:
            dToday = date.today()

        # Odoo 19 dropped the stored ``hr.employee.first_contract_date`` field;
        # a contract is an ``hr.version`` record now and the employee's
        # employment date is derived from the earliest ``contract_date_start``
        # (``get_employment_date`` comes from hr_employee_seniority_months).
        hireDate = employee.get_employment_date()
        delta = dToday - hireDate
        if abs(delta.days) > self.minimum_employed_days:
            return True
        return False

    @api.constrains("accrual_rate_premium", "accrual_rate_premium_milestone")
    def _check_premium_milestone(self):
        """A premium cannot be computed without a positive milestone.

        The premium rate is divided by ``accrual_rate_premium_milestone``, so a
        milestone of zero (the field default) would make the accrual job crash
        once an employee reaches ``accrual_rate_premium_minimum`` months.
        """

        for line in self:
            if line.accrual_rate_premium and line.accrual_rate_premium_milestone <= 0:
                raise ValidationError(
                    self.env._(
                        "A positive 'Accrual Premium Milestone' is required when"
                        " a premium rate is configured."
                    )
                )

    def get_last_job_date(self):
        """
        @return: a datetime.date object representing the time the last job ran.
        """

        self.ensure_one()
        job_ids = self.env["hr.policy.line.accrual.job"].search(
            [("policy_line_id", "=", self.id)], order="name desc", limit=1
        )
        if len(job_ids) == 0:
            return None

        return job_ids[0].name

    def calculate_and_deposit(self, employee, job=False, d_today=None, descr=None):
        for rec in self:
            amount = rec.do_calculation(employee, d_today)
            if amount is False:
                break
            name = self.env._("Calendar based accrual (%(name)s)", name=self.name)
            lines = self.accrual_id.deposit(
                employee.id,
                amount,
                d_today if d_today is not None else date.today(),
                name,
            )
            if job:
                for line in lines:
                    job.write(
                        {
                            "accrual_line_ids": [(4, line.id)],
                            "holiday_ids": [(4, line.leave_allocation_id.id)],
                        }
                    )

    def do_calculation(self, employee, dToday=None):
        self.ensure_one()

        if dToday is None:
            dToday = date.today()

        # The last day of each month for the year ``dToday`` falls in.
        # February depends on the year (a leap year has a 29th day), so it
        # cannot be hard-coded: an employee hired on the 30th or 31st must
        # still receive the February accrual in a leap year.
        month_last_day = {
            1: 31,
            2: calendar.monthrange(dToday.year, 2)[1],
            3: 31,
            4: 30,
            5: 31,
            6: 30,
            7: 31,
            8: 31,
            9: 30,
            10: 31,
            11: 30,
            12: 31,
        }

        dHire = employee.get_employment_date()
        srvc_months = employee.get_months_service_to_date(dToday=dToday)
        srvc_months = int(srvc_months)

        if self.type != "calendar" or not self.pass_constraints(employee, dToday):
            return False

        if self.frequency_on_hire_date:
            freq_week_day = dHire.weekday()
            freq_month_day = dHire.day
            freq_annual_month = dHire.month
            freq_annual_day = dHire.day
        else:
            # The selection fields are stored (and returned) as strings while
            # the date parts they are compared with are integers: convert them
            # or the comparisons never match (and the ``>``/``!=`` checks raise
            # TypeError on a string). An unset value must not match any date,
            # so it becomes -1 instead of 0 (0 is Monday and day 0 never
            # exists).
            freq_week_day = int(self.frequency_week_day or -1)
            freq_month_day = int(self.frequency_month_day or -1)
            freq_annual_month = int(self.frequency_annual_month or -1)
            freq_annual_day = int(self.frequency_annual_day or -1)

        premium_amount = 0
        if self.calculation_frequency == "weekly":
            if dToday.weekday() != freq_week_day:
                return False
            freq_amount = float(self.accrual_rate) / 52.0
            premium_amount = self._calculate_premium_weekly(srvc_months)
        elif self.calculation_frequency == "monthly":
            # When deciding to skip an employee account for actual month
            # lengths if the frequency date is 31 and this month only has 30
            # days, go ahead and do the accrual on the last day of the month
            # (i.e. the 30th). February uses its actual last day (28, or 29 in
            # a leap year) so employees hired on the 30th/31st are not skipped.
            #
            if (
                dToday.day == month_last_day[dToday.month]
                and freq_month_day > dToday.day
            ):
                freq_month_day = dToday.day

            if dToday.day != freq_month_day:
                return False

            freq_amount = float(self.accrual_rate) / 12.0
            premium_amount = self._calculate_premium_monthly(srvc_months)
        else:  # annual frequency
            # Execute a February accrual dated the 29th (or the 30th/31st) on
            # the last day the month actually has.
            #
            if (
                freq_annual_month == 2
                and dToday.month == 2
                and dToday.day == month_last_day[2]
                and freq_annual_day > dToday.day
            ):
                freq_annual_day = dToday.day

            # Both the month and the day must match, otherwise an annual rule
            # would pay the full yearly amount every day of the matching month
            # (and on the matching day of every other month).
            if dToday.month != freq_annual_month or dToday.day != freq_annual_day:
                return False

            freq_amount = self.accrual_rate
            premium_amount = self._calculate_premium_annual(srvc_months)

        if self.accrual_rate_max == 0:
            amount = freq_amount + premium_amount
        else:
            amount = min(freq_amount + premium_amount, self.accrual_rate_max)

        return amount

    def _calculate_premium_weekly(self, srvc_months):
        self.ensure_one()
        premium_amount = 0.0
        if (
            self.accrual_rate_premium
            and self.accrual_rate_premium_milestone > 0
            and self.accrual_rate_premium_minimum <= srvc_months
        ):
            premium_amount = (
                (
                    max(
                        0,
                        srvc_months
                        - self.accrual_rate_premium_minimum
                        + self.accrual_rate_premium_milestone,
                    )
                )
                // self.accrual_rate_premium_milestone
                * self.accrual_rate_premium
                / 52.0
            )
        return premium_amount

    def _calculate_premium_monthly(self, srvc_months):
        self.ensure_one()
        premium_amount = 0.0
        if (
            self.accrual_rate_premium
            and self.accrual_rate_premium_milestone > 0
            and self.accrual_rate_premium_minimum <= srvc_months
        ):
            premium_amount = (
                (
                    max(
                        0,
                        srvc_months
                        - self.accrual_rate_premium_minimum
                        + self.accrual_rate_premium_milestone,
                    )
                )
                // self.accrual_rate_premium_milestone
                * self.accrual_rate_premium
                / 12.0
            )
        return premium_amount

    def _calculate_premium_annual(self, srvc_months):
        self.ensure_one()
        premium_amount = 0.0
        if (
            self.accrual_rate_premium
            and self.accrual_rate_premium_milestone > 0
            and self.accrual_rate_premium_minimum <= srvc_months
        ):
            premium_amount = (
                (
                    max(
                        0,
                        srvc_months
                        - self.accrual_rate_premium_minimum
                        + self.accrual_rate_premium_milestone,
                    )
                )
                // self.accrual_rate_premium_milestone
                * self.accrual_rate_premium
            )
        return premium_amount
