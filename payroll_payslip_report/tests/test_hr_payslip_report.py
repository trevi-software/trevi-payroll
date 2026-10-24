# Copyright (C) 2022 Trevi Software (https://trevi.et)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo.addons.payroll.tests.common import TestPayslipBase
from odoo.tests import new_test_user


class TestHrPayslipReportView(TestPayslipBase):
    def _create_payslip(self, employee):
        # Create the payslip directly rather than through a Form: payroll_account,
        # when installed alongside, makes journal_id a required form field and it
        # is only ever filled in from the contract.
        payslip = self.Payslip.create({"employee_id": employee.id})
        payslip.onchange_employee()
        payslip.compute_sheet()
        payslip.write({"number": "SLIP/TEST"})
        return payslip

    def test_view_returns_payslip_lines(self):
        """The analysis view builds and exposes the payslips."""
        payslip = self._create_payslip(self.richard_emp)
        self.assertTrue(payslip.line_ids, "the payslip must have been computed")

        rows = self.env["hr.payslip.report.view"].search([])
        self.assertTrue(rows, "the analysis view must return the payslip lines")
        self.assertEqual(set(rows.mapped("name")), {self.richard_emp})
        self.assertEqual(
            set(rows.mapped("company_id")), {self.richard_emp.company_id}
        )
        self.assertEqual(set(rows.mapped("state")), {"draft"})

    def test_include_category_codes_single_category(self):
        """A single configured category code must not break the view.

        The HAVING clause used to interpolate the Python tuple of category ids
        directly, so a single category rendered as ``IN (5,)`` - invalid SQL
        that PostgreSQL rejects, taking the view (and every module upgrade that
        rebuilds it) down with it.
        """
        category = self.SalaryRuleCateg.create(
            {"name": "Report Only", "code": "PPRTEST"}
        )
        self._create_payslip(self.richard_emp)
        view = self.env["hr.payslip.report.view"]
        param = self.env["ir.config_parameter"].sudo()

        # Exactly one category matches this code: rebuilding the view must
        # succeed and must really filter on it.
        param.set_param(
            "payroll_payslip_report.include_category_codes", category.code
        )
        view.init()
        self.assertFalse(
            view.search([]),
            "no payslip line belongs to the selected category",
        )

        param.set_param(
            "payroll_payslip_report.include_category_codes",
            self.categ_basic.code,
        )
        view.init()
        rows = view.search([])
        self.assertTrue(rows)
        self.assertEqual(
            set(rows.mapped("rule_name")),
            {self.categ_basic},
            "only the selected category must be included in the analysis",
        )

    def test_company_record_rule(self):
        """A payroll user must not see other companies' payslips.

        The view is a standalone model, so the multi-company rule defined on
        hr.payslip does not protect reads through it.
        """
        self._create_payslip(self.richard_emp)
        view = self.env["hr.payslip.report.view"]
        self.assertTrue(view.search([]))

        other_company = self.env["res.company"].create({"name": "Other Company"})
        other_user = new_test_user(
            self.env,
            login="ppr_other_company",
            groups="payroll.group_payroll_user",
            company_id=other_company.id,
        )
        self.assertFalse(
            view.with_user(other_user).search([]),
            "another company's payroll user must not see these payslips",
        )
