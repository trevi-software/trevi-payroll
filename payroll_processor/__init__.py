from . import models
from . import wizard

from odoo.api import Environment, SUPERUSER_ID


def disable_payroll_prevent_compute_on_confirm(env):
    env["ir.config_parameter"].sudo().set_param(
        "payroll.prevent_compute_on_confirm", True
    )
