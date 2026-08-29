# Copyright (C) 2025 Trevi Software (https://trevi.et)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

{
    "name": "Payroll Salary Code",
    "summary": "Manage payroll salary codes.",
    "version": "18.0.1.0.0",
    "category": "Payroll",
    "author": "TREVI Software",
    "license": "AGPL-3",
    "website": "https://github.com/trevi-software/trevi-payroll",
    "depends": [
        "payroll",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/payroll_salary_code_views.xml",
    ],
    "installable": True,
    "application": False,
}
