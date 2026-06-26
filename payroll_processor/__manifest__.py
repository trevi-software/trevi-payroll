{
    "name": "Default Payroll Processor",
    "summary": "Base module for implementing salary payment processors",
    "version": "16.0.1.0.0",
    "author": "TREVI Software",
    "category": "Payroll",
    "license": "AGPL-3",
    "website": "https://github.com/trevi-software/trevi-payroll",
    "depends": ["payroll"],
    "data": [
        "security/ir.model.access.csv",
        "views/menus.xml",
        "views/hr_employee_view.xml",
        "views/hr_payslip_view.xml",
        "views/res_config_settings_view.xml",
    ],
    "post_init_hook": "post_init_hook",
    "installable": True,
}
