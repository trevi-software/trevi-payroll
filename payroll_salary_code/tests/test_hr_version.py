# Copyright (C) 2026 Trevi Software (https://trevi.et)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo.tests.common import TransactionCase


class TestHrVersion(TransactionCase):
    """Odoo 19 merged ``hr.contract`` into ``hr``, so the salary code now lives
    on ``hr.version``."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        cls.Version = cls.env["hr.version"]
        cls.Employee = cls.env["hr.employee"]
        cls.SalaryCode = cls.env["payroll.salary.code"]

        cls.code_tra = cls.SalaryCode.create(
            {
                "code": "TRA",
                "description": "Transport allowance",
            }
        )
        cls.code_hse = cls.SalaryCode.create(
            {
                "code": "HSE",
                "description": "Housing allowance",
            }
        )

        # An employee always owns a version dated today, and
        # (employee_id, date_version) is unique. Backdate that first version so
        # the versions created by the tests do not collide with it.
        cls.employee = cls.Employee.create(
            {"name": "Test Employee", "date_version": "2000-01-01"}
        )
        cls.calendar = cls.env["resource.calendar"].create({"name": "Test Calendar"})

    def setUp(self):
        super().setUp()
        self._date_seq = 0

    def _create_contract(self, name="Test Contract", wage=1000):
        self._date_seq += 1
        return self.Version.create(
            {
                "name": name,
                "employee_id": self.employee.id,
                "date_version": f"2010-01-{self._date_seq:02d}",
                "resource_calendar_id": self.calendar.id,
                "wage": wage,
            }
        )

    def test_field_present(self):
        """The many2one field exists on hr.version."""
        contract = self._create_contract()
        self.assertFalse(contract.payroll_salary_code)

    def test_assign_code(self):
        """A salary code can be assigned to and read back from a contract."""
        contract = self._create_contract()
        contract.payroll_salary_code = self.code_tra
        self.assertEqual(contract.payroll_salary_code.code, "TRA")

    def test_reassign_code(self):
        """Assigning a new code replaces the previous one."""
        contract = self._create_contract()
        contract.payroll_salary_code = self.code_tra
        contract.payroll_salary_code = self.code_hse
        self.assertEqual(contract.payroll_salary_code.code, "HSE")

    def test_multiple_contracts_share_code(self):
        """The same code can be linked to several contracts."""
        c1 = self._create_contract()
        c2 = self._create_contract(name="Test Contract 2", wage=2000)
        c1.payroll_salary_code = self.code_tra
        c2.payroll_salary_code = self.code_tra
        self.assertEqual(c1.payroll_salary_code, self.code_tra)
        self.assertEqual(c2.payroll_salary_code, self.code_tra)

    def test_unset_code(self):
        """Clearing the code from a contract doesn't delete the code itself."""
        contract = self._create_contract()
        contract.payroll_salary_code = self.code_tra
        contract.payroll_salary_code = False
        self.assertFalse(contract.payroll_salary_code)
        self.assertTrue(self.code_tra.exists())

    def test_contract_ids_one2many(self):
        """The one2many on payroll.salary.code reflects linked contracts."""
        self.assertFalse(self.code_tra.contract_ids)
        c1 = self._create_contract()
        c2 = self._create_contract(name="Test Contract 2", wage=2000)
        c1.payroll_salary_code = self.code_tra
        c2.payroll_salary_code = self.code_tra
        self.assertEqual(self.code_tra.contract_ids, c1 | c2)

    def test_one2many_unlink(self):
        """Clearing a contract's code removes it from the code's contracts."""
        contract = self._create_contract()
        contract.payroll_salary_code = self.code_tra
        self.assertIn(contract, self.code_tra.contract_ids)
        contract.payroll_salary_code = False
        self.assertNotIn(contract, self.code_tra.contract_ids)
