# Copyright (C) 2026 TREVI Software
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from lxml import etree

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestResConfigSettings(TransactionCase):
    """Regression tests for the Payroll Codes settings block.

    The Gross/Net "single payslip line" settings must edit the salary *rule*
    code (``rule_gross``/``rule_net``) and not the salary *category* code
    (``categ_gross``/``categ_net``). Editing the category code from those two
    settings left the rule code unchanged.
    """

    def _get_payroll_codes_block(self):
        view = self.env.ref(
            "payroll_default_salary_rules.res_config_settings_view_form"
        )
        arch = self.env["res.config.settings"].get_view(
            view_id=view.id, view_type="form"
        )["arch"]
        root = etree.fromstring(arch.encode("utf-8"))
        blocks = root.xpath("//block[@title='Payroll Codes']")
        self.assertEqual(
            len(blocks), 1, "Expected exactly one 'Payroll Codes' settings block"
        )
        return blocks[0]

    def _field_name_for_help(self, block, help_prefix):
        for setting in block.xpath("./setting"):
            help_text = (setting.get("help") or "").strip()
            if help_text.startswith(help_prefix):
                field_names = setting.xpath("./field/@name")
                self.assertEqual(
                    len(field_names),
                    1,
                    f"Expected a single field in the {help_prefix!r} setting",
                )
                return field_names[0]
        self.fail(f"No setting found with help starting with {help_prefix!r}")

    def test_gross_rule_setting_binds_rule_field(self):
        """Gross Earnings rule setting edits the rule code, not the category."""
        block = self._get_payroll_codes_block()
        self.assertEqual(
            self._field_name_for_help(block, "Gross earnings payslip line"),
            "rule_gross",
        )

    def test_net_rule_setting_binds_rule_field(self):
        """Net Earnings rule setting edits the rule code, not the category."""
        block = self._get_payroll_codes_block()
        self.assertEqual(
            self._field_name_for_help(block, "Net earnings payslip line"),
            "rule_net",
        )

    def test_rule_settings_fields_exist(self):
        """The rule code settings expose dedicated res.config.settings fields."""
        settings = self.env["res.config.settings"]
        self.assertIn("rule_gross", settings._fields)
        self.assertIn("rule_net", settings._fields)
