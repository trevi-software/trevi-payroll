# Copyright (C) 2022 Trevi Software (https://trevi.et)
# Copyright (C) 2020-TODAY Cybrosys Technologies (<https://www.cybrosys.com>).
# Author: Anusha (<https://www.cybrosys.com>)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import SUPERUSER_ID, fields, models, tools


class PayrollReportView(models.Model):
    _name = "hr.payslip.report.view"
    _description = "Payslip Analysis View"
    _auto = False

    name = fields.Many2one("hr.employee", string="Employee")
    date_from = fields.Date(string="From")
    date_to = fields.Date(string="To")
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("verify", "Waiting"),
            ("done", "Done"),
            ("cancel", "Rejected"),
        ],
        string="Status",
    )
    job_id = fields.Many2one("hr.job", string="Job Title")
    company_id = fields.Many2one("res.company")
    department_id = fields.Many2one("hr.department")
    rule_name = fields.Many2one("hr.salary.rule.category", string="Rule Category")
    rule_amount = fields.Float(string="Amount")
    struct_id = fields.Many2one("hr.payroll.structure", string="Salary Structure")
    rule_id = fields.Many2one("hr.salary.rule", string="Salary Rule")

    def _select(self):
        select_str = """
            min(psl.id) as line_id,
            ps.id, ps.number,
            emp.id as name,
            dp.id as department_id,
            jb.id as job_id,
            cmp.id as company_id,
            ps.date_from, ps.date_to,
            ps.state as state,
            rl.id as rule_name,
            psl.total as rule_amount,
            ps.struct_id as struct_id,
            rlu.id as rule_id"""
        return select_str

    def _from(self):
        from_str = """
                hr_payslip_line psl
                join hr_payslip ps on ps.id=psl.slip_id
                join hr_salary_rule rlu on rlu.id = psl.salary_rule_id
                join hr_employee emp on ps.employee_id=emp.id
                join hr_version vrs on vrs.id = psl.contract_id
                join hr_salary_rule_category rl on rl.id = psl.category_id
                left join hr_department dp on vrs.department_id=dp.id
                left join hr_job jb on vrs.job_id=jb.id
                join res_company cmp on cmp.id=ps.company_id
             """
        return from_str

    def _group_by(self):
        group_by_str = """
            ps.number,
            ps.id,
            emp.id,
            dp.id,
            jb.id,
            cmp.id,
            ps.date_from,
            ps.date_to,
            ps.state,
            psl.total,
            psl.name,
            psl.category_id,
            rl.id,rlu.id"""
        return group_by_str

    def _having(self):
        ir_config = self.env["ir.config_parameter"].with_user(SUPERUSER_ID)
        include_category_codes = (
            ir_config.get_param("payroll_payslip_report.include_category_codes")
        ) or ""
        lst_inc_rulecateg = include_category_codes.split(",")
        inc_rulecateg_ids = False
        if len(lst_inc_rulecateg) > 0:
            inc_rulecateg_ids = self.env["hr.salary.rule.category"].search(
                [("code", "in", lst_inc_rulecateg)]
            )

        having_str = ""
        params = ()
        if inc_rulecateg_ids:
            # Bind the category ids as a query parameter instead of formatting
            # the Python tuple into the SQL: a single selected category used to
            # render as ``IN (5,)``, which PostgreSQL rejects, so the view (and
            # therefore every module upgrade) failed to build.
            having_str = "HAVING psl.category_id = ANY(%s)"
            params = (inc_rulecateg_ids.ids,)

        return having_str, params

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        having_str, params = self._having()
        query = f"""CREATE or REPLACE VIEW {self._table} as ( SELECT
                   {self._select()}
                   FROM {self._from()}
                   GROUP BY
                   {self._group_by()}
                   {having_str}
                   )"""
        self.env.cr.execute(query, params)
